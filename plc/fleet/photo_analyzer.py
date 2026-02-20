"""
Photo Metadata Analyzer
=========================
Extracts EXIF metadata from field photos of LACT units.
Photos serve as a key input for:

  - GPS location of the unit
  - Timestamp of inspection/acquisition
  - Camera information for photo quality assessment
  - Image orientation for consistent display
  - Equipment identification tags (manually added or
    future ML-based detection)

Works with JPEG, PNG, HEIC, and TIFF formats.
Uses only the Python standard library for core metadata;
Pillow is optional for enhanced extraction.
"""

import os
import struct
import time
import logging
from pathlib import Path
from typing import Optional

from plc.fleet.unit_profile import PhotoRecord

logger = logging.getLogger(__name__)


class PhotoAnalyzer:
    """
    Extracts metadata from field photos.

    Primary extraction uses standard library struct parsing
    of EXIF headers. Falls back gracefully when images don't
    contain EXIF data.
    """

    def analyze(self, file_path: str) -> PhotoRecord:
        """
        Analyze a single photo and return a PhotoRecord
        with extracted metadata.
        """
        path = Path(file_path)
        record = PhotoRecord(file_path=str(path.absolute()))

        if not path.exists():
            logger.warning("Photo not found: %s", file_path)
            return record

        # File-level metadata
        stat = path.stat()
        record.timestamp = stat.st_mtime

        # Try to extract EXIF data
        suffix = path.suffix.lower()
        if suffix in (".jpg", ".jpeg"):
            self._extract_jpeg_exif(path, record)
        elif suffix == ".png":
            self._extract_png_metadata(path, record)
        elif suffix in (".heic", ".heif"):
            record.description = "HEIC format (metadata extraction requires pillow)"
        elif suffix in (".tif", ".tiff"):
            self._extract_tiff_exif(path, record)

        # Try Pillow as enhanced fallback
        self._try_pillow_extraction(path, record)

        return record

    def analyze_batch(self, directory: str, extensions: tuple = None) -> list:
        """
        Analyze all photos in a directory.
        Returns list of PhotoRecord objects sorted by timestamp.
        """
        if extensions is None:
            extensions = (".jpg", ".jpeg", ".png", ".heic", ".heif", ".tif", ".tiff")

        dir_path = Path(directory)
        if not dir_path.is_dir():
            return []

        records = []
        for entry in sorted(dir_path.iterdir()):
            if entry.suffix.lower() in extensions:
                record = self.analyze(str(entry))
                records.append(record)

        records.sort(key=lambda r: r.timestamp)
        return records

    def _extract_jpeg_exif(self, path: Path, record: PhotoRecord):
        """Extract EXIF from JPEG files using standard library."""
        try:
            with open(path, "rb") as f:
                # Check JPEG SOI marker
                if f.read(2) != b"\xff\xd8":
                    return

                # Scan for APP1 (EXIF) marker
                while True:
                    marker = f.read(2)
                    if len(marker) < 2:
                        break
                    if marker[0] != 0xFF:
                        break

                    # APP1 = 0xFFE1
                    if marker[1] == 0xE1:
                        length = struct.unpack(">H", f.read(2))[0]
                        exif_data = f.read(length - 2)
                        self._parse_exif_data(exif_data, record)
                        break

                    # Skip other markers
                    if marker[1] in (0xD0, 0xD1, 0xD2, 0xD3, 0xD4,
                                      0xD5, 0xD6, 0xD7, 0xD8, 0xD9):
                        continue
                    length = struct.unpack(">H", f.read(2))[0]
                    f.seek(length - 2, 1)
        except Exception:
            logger.debug("Failed to extract JPEG EXIF: %s", path)

    def _extract_png_metadata(self, path: Path, record: PhotoRecord):
        """Extract metadata from PNG text chunks."""
        try:
            with open(path, "rb") as f:
                sig = f.read(8)
                if sig != b"\x89PNG\r\n\x1a\n":
                    return

                while True:
                    header = f.read(8)
                    if len(header) < 8:
                        break
                    length = struct.unpack(">I", header[:4])[0]
                    chunk_type = header[4:8]

                    if chunk_type == b"tEXt":
                        text_data = f.read(length)
                        f.read(4)  # CRC
                        try:
                            decoded = text_data.decode("latin-1")
                            if "\x00" in decoded:
                                key, val = decoded.split("\x00", 1)
                                if key.lower() in ("description", "comment"):
                                    record.description = val
                        except Exception:
                            pass
                    else:
                        f.seek(length + 4, 1)  # data + CRC
        except Exception:
            logger.debug("Failed to extract PNG metadata: %s", path)

    def _extract_tiff_exif(self, path: Path, record: PhotoRecord):
        """Extract EXIF from TIFF files."""
        # TIFF files use the same IFD structure as EXIF
        try:
            with open(path, "rb") as f:
                header = f.read(8)
                if header[:2] == b"II":
                    endian = "<"
                elif header[:2] == b"MM":
                    endian = ">"
                else:
                    return
                # Simplified: just note it's a TIFF
                record.description = "TIFF image"
        except Exception:
            logger.debug("Failed to extract TIFF EXIF: %s", path)

    def _parse_exif_data(self, data: bytes, record: PhotoRecord):
        """Parse raw EXIF data to extract GPS and camera info."""
        if not data.startswith(b"Exif\x00\x00"):
            return

        tiff_data = data[6:]
        if len(tiff_data) < 8:
            return

        if tiff_data[:2] == b"II":
            endian = "<"
        elif tiff_data[:2] == b"MM":
            endian = ">"
        else:
            return

        try:
            ifd_offset = struct.unpack(f"{endian}I", tiff_data[4:8])[0]
            self._parse_ifd(tiff_data, ifd_offset, endian, record)
        except Exception:
            logger.debug("Failed to parse EXIF IFD")

    def _parse_ifd(self, data: bytes, offset: int, endian: str, record: PhotoRecord):
        """Parse a single IFD (Image File Directory)."""
        if offset + 2 > len(data):
            return

        num_entries = struct.unpack(f"{endian}H", data[offset:offset + 2])[0]
        pos = offset + 2

        gps_ifd_offset = None

        for _ in range(num_entries):
            if pos + 12 > len(data):
                break

            tag = struct.unpack(f"{endian}H", data[pos:pos + 2])[0]
            type_id = struct.unpack(f"{endian}H", data[pos + 2:pos + 4])[0]
            count = struct.unpack(f"{endian}I", data[pos + 4:pos + 8])[0]
            value_raw = data[pos + 8:pos + 12]

            # Tag 0x0110 = Camera Model
            if tag == 0x0110:
                str_offset = struct.unpack(f"{endian}I", value_raw)[0]
                if str_offset + count <= len(data):
                    record.camera_model = data[str_offset:str_offset + count].decode(
                        "ascii", errors="ignore"
                    ).rstrip("\x00")

            # Tag 0x0112 = Orientation
            elif tag == 0x0112:
                record.orientation = struct.unpack(f"{endian}H", value_raw[:2])[0]

            # Tag 0x8825 = GPS IFD pointer
            elif tag == 0x8825:
                gps_ifd_offset = struct.unpack(f"{endian}I", value_raw)[0]

            pos += 12

        # Parse GPS sub-IFD if present
        if gps_ifd_offset is not None:
            self._parse_gps_ifd(data, gps_ifd_offset, endian, record)

    def _parse_gps_ifd(self, data: bytes, offset: int, endian: str, record: PhotoRecord):
        """Parse GPS IFD to extract coordinates."""
        if offset + 2 > len(data):
            return

        num_entries = struct.unpack(f"{endian}H", data[offset:offset + 2])[0]
        pos = offset + 2

        lat_ref = "N"
        lon_ref = "W"
        lat_vals = None
        lon_vals = None

        for _ in range(num_entries):
            if pos + 12 > len(data):
                break

            tag = struct.unpack(f"{endian}H", data[pos:pos + 2])[0]
            type_id = struct.unpack(f"{endian}H", data[pos + 2:pos + 4])[0]
            count = struct.unpack(f"{endian}I", data[pos + 4:pos + 8])[0]
            value_raw = data[pos + 8:pos + 12]

            # GPS latitude reference (N/S)
            if tag == 1:
                lat_ref = value_raw[:1].decode("ascii", errors="ignore")
            # GPS latitude (rational x 3)
            elif tag == 2:
                val_offset = struct.unpack(f"{endian}I", value_raw)[0]
                lat_vals = self._read_gps_rational(data, val_offset, endian)
            # GPS longitude reference (E/W)
            elif tag == 3:
                lon_ref = value_raw[:1].decode("ascii", errors="ignore")
            # GPS longitude (rational x 3)
            elif tag == 4:
                val_offset = struct.unpack(f"{endian}I", value_raw)[0]
                lon_vals = self._read_gps_rational(data, val_offset, endian)

            pos += 12

        if lat_vals and lon_vals:
            lat = lat_vals[0] + lat_vals[1] / 60.0 + lat_vals[2] / 3600.0
            lon = lon_vals[0] + lon_vals[1] / 60.0 + lon_vals[2] / 3600.0
            if lat_ref == "S":
                lat = -lat
            if lon_ref == "W":
                lon = -lon
            record.gps_lat = round(lat, 6)
            record.gps_lon = round(lon, 6)

    def _read_gps_rational(self, data: bytes, offset: int, endian: str) -> list:
        """Read 3 RATIONAL values (degrees, minutes, seconds)."""
        values = []
        for i in range(3):
            pos = offset + i * 8
            if pos + 8 > len(data):
                values.append(0.0)
                continue
            num = struct.unpack(f"{endian}I", data[pos:pos + 4])[0]
            den = struct.unpack(f"{endian}I", data[pos + 4:pos + 8])[0]
            values.append(num / den if den else 0.0)
        return values

    def _try_pillow_extraction(self, path: Path, record: PhotoRecord):
        """Try Pillow for enhanced metadata extraction (optional dependency)."""
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS, GPSTAGS

            img = Image.open(str(path))
            exif_data = img.getexif()

            if not exif_data:
                return

            # Camera model
            if 272 in exif_data and not record.camera_model:
                record.camera_model = str(exif_data[272])

            # Orientation
            if 274 in exif_data and record.orientation == 1:
                record.orientation = int(exif_data[274])

            # GPS data
            gps_info = exif_data.get_ifd(0x8825)
            if gps_info and record.gps_lat == 0.0:
                lat = gps_info.get(2)
                lat_ref = gps_info.get(1, "N")
                lon = gps_info.get(4)
                lon_ref = gps_info.get(3, "W")

                if lat and lon:
                    lat_deg = float(lat[0]) + float(lat[1]) / 60 + float(lat[2]) / 3600
                    lon_deg = float(lon[0]) + float(lon[1]) / 60 + float(lon[2]) / 3600
                    if lat_ref == "S":
                        lat_deg = -lat_deg
                    if lon_ref == "W":
                        lon_deg = -lon_deg
                    record.gps_lat = round(lat_deg, 6)
                    record.gps_lon = round(lon_deg, 6)

        except ImportError:
            pass  # Pillow not installed — that's fine
        except Exception:
            logger.debug("Pillow extraction failed for: %s", path)
