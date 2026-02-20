"""Tests for the photo metadata analyzer."""

import pytest
import struct
import tempfile
import os
from plc.fleet.photo_analyzer import PhotoAnalyzer
from plc.fleet.unit_profile import PhotoRecord


class TestPhotoAnalyzer:
    @pytest.fixture
    def analyzer(self):
        return PhotoAnalyzer()

    def test_analyze_nonexistent_file(self, analyzer):
        record = analyzer.analyze("/nonexistent/photo.jpg")
        assert record.file_path == "/nonexistent/photo.jpg"
        assert record.camera_model == ""

    def test_analyze_returns_photo_record(self, analyzer, tmp_path):
        # Create a minimal file
        test_file = tmp_path / "test.txt"
        test_file.write_text("not a photo")
        record = analyzer.analyze(str(test_file))
        assert isinstance(record, PhotoRecord)
        assert record.timestamp > 0

    def test_analyze_png_file(self, analyzer, tmp_path):
        # Create a minimal valid PNG
        png_file = tmp_path / "test.png"
        # PNG signature + IHDR chunk + IEND chunk
        sig = b"\x89PNG\r\n\x1a\n"
        # Minimal IHDR
        ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
        ihdr_crc = b"\x00" * 4
        ihdr = struct.pack(">I", len(ihdr_data)) + b"IHDR" + ihdr_data + ihdr_crc
        # IEND
        iend = struct.pack(">I", 0) + b"IEND" + b"\x00" * 4
        png_file.write_bytes(sig + ihdr + iend)

        record = analyzer.analyze(str(png_file))
        assert record.timestamp > 0

    def test_analyze_jpeg_without_exif(self, analyzer, tmp_path):
        # Minimal JPEG: SOI + EOI markers only
        jpeg_file = tmp_path / "test.jpg"
        jpeg_file.write_bytes(b"\xff\xd8\xff\xd9")
        record = analyzer.analyze(str(jpeg_file))
        assert record.camera_model == ""

    def test_analyze_batch_empty_dir(self, analyzer, tmp_path):
        records = analyzer.analyze_batch(str(tmp_path))
        assert len(records) == 0

    def test_analyze_batch_with_files(self, analyzer, tmp_path):
        # Create some dummy image files
        (tmp_path / "photo1.jpg").write_bytes(b"\xff\xd8\xff\xd9")
        (tmp_path / "photo2.jpg").write_bytes(b"\xff\xd8\xff\xd9")
        (tmp_path / "notes.txt").write_text("not a photo")
        records = analyzer.analyze_batch(str(tmp_path))
        assert len(records) == 2  # Only jpg files

    def test_analyze_batch_nonexistent_dir(self, analyzer):
        records = analyzer.analyze_batch("/nonexistent/dir")
        assert records == []

    def test_analyze_heic_file(self, analyzer, tmp_path):
        heic_file = tmp_path / "test.heic"
        heic_file.write_bytes(b"heic data")
        record = analyzer.analyze(str(heic_file))
        assert "HEIC" in record.description

    def test_gps_parsing_from_rational(self, analyzer):
        """Test GPS rational number parsing."""
        # Build synthetic EXIF with GPS data
        # This tests the rational math: 32° 18' 18" N, 101° 55' 12" W
        values = analyzer._read_gps_rational(
            struct.pack(">IIIIIIII",
                        32, 1,   # 32 degrees
                        18, 1,   # 18 minutes
                        18, 1,   # 18 seconds
                        0, 0),   # padding
            0, ">"
        )
        assert values[0] == 32.0
        assert values[1] == 18.0
        assert values[2] == 18.0
