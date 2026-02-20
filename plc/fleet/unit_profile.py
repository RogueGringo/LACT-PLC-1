"""
LACT Unit Profile
==================
Data model representing a complete LACT unit configuration.
Each unit profile captures:

  - Identity: serial number, manufacturer, location, photos
  - Components: meter, pump, valves, probes, sampler, prover
  - Physical: pipe size, skid dimensions, orientation
  - Electrical: power supply ratings, I/O module configuration
  - Operational: setpoint overrides, custom alarms

A UnitProfile can be created manually, from an intake form,
or partially auto-populated from photo analysis. Once complete,
it drives configuration generation (io_map, setpoints, alarms).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import json
import time
from pathlib import Path


class UnitStatus(Enum):
    INTAKE = "intake"              # Gathering information
    CONFIGURED = "configured"      # Config generated, not deployed
    DEPLOYED = "deployed"          # Running in the field
    MAINTENANCE = "maintenance"    # Offline for maintenance
    DECOMMISSIONED = "decommissioned"


class PipeSize(Enum):
    TWO_INCH = 2.0
    THREE_INCH = 3.0
    FOUR_INCH = 4.0
    SIX_INCH = 6.0


@dataclass
class GeoLocation:
    """Physical location of the unit."""
    latitude: float = 0.0
    longitude: float = 0.0
    address: str = ""
    county: str = ""
    state: str = ""
    lease_name: str = ""
    well_id: str = ""


@dataclass
class ElectricalConfig:
    """Electrical system configuration."""
    main_power: str = "480VAC_3PH"
    control_power: str = "24VDC"
    io_bus: str = "modbus_rtu"       # modbus_rtu, modbus_tcp
    io_bus_address: str = ""          # /dev/ttyUSB0 or IP:port
    di_module_channels: int = 16
    do_module_channels: int = 8
    ai_module_channels: int = 8
    ao_module_channels: int = 2
    has_pulse_counter: bool = True
    has_ups: bool = False


@dataclass
class PhotoRecord:
    """Metadata about a unit photo used during intake."""
    file_path: str = ""
    timestamp: float = 0.0
    description: str = ""
    gps_lat: float = 0.0
    gps_lon: float = 0.0
    camera_model: str = ""
    orientation: int = 1
    tags: list = field(default_factory=list)

    @property
    def has_gps(self) -> bool:
        return self.gps_lat != 0.0 or self.gps_lon != 0.0


@dataclass
class ComponentSelection:
    """
    Selected components for a unit. Keys reference
    the component library (components.py catalogs).
    """
    meter_key: str = ""
    pump_key: str = ""
    divert_valve_key: str = ""
    bsw_probe_key: str = ""
    sampler_key: str = ""
    prover_key: str = ""
    # Extras not in standard catalog
    has_strainer: bool = True
    strainer_mesh: int = 4
    has_air_eliminator: bool = True
    has_static_mixer: bool = True
    has_test_thermowell: bool = True
    num_backpressure_valves: int = 2  # sales + divert lines
    num_pressure_transmitters: int = 3  # inlet, loop, outlet


@dataclass
class UnitProfile:
    """
    Complete profile of a LACT unit — everything needed to
    generate a working PLC configuration.
    """
    # ── Identity ─────────────────────────────────────────────
    unit_id: str = ""
    serial_number: str = ""
    manufacturer: str = ""
    model: str = ""
    pipe_size: float = 3.0
    year_built: int = 0
    source: str = ""           # Where acquired (e.g., "GovPlanet", "Ritchie Bros")
    source_listing_url: str = ""
    purchase_date: str = ""
    notes: str = ""

    # ── Status ───────────────────────────────────────────────
    status: UnitStatus = UnitStatus.INTAKE
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    # ── Location ─────────────────────────────────────────────
    location: GeoLocation = field(default_factory=GeoLocation)

    # ── Components ───────────────────────────────────────────
    components: ComponentSelection = field(default_factory=ComponentSelection)

    # ── Electrical ───────────────────────────────────────────
    electrical: ElectricalConfig = field(default_factory=ElectricalConfig)

    # ── Photos ───────────────────────────────────────────────
    photos: list = field(default_factory=list)

    # ── Setpoint Overrides ───────────────────────────────────
    # Keys are setpoint names, values override the defaults
    setpoint_overrides: dict = field(default_factory=dict)

    # ── Custom Tags ──────────────────────────────────────────
    # Additional I/O points not in the standard template
    custom_di: list = field(default_factory=list)
    custom_do: list = field(default_factory=list)
    custom_ai: list = field(default_factory=list)

    def save(self, path: str = None):
        """Persist unit profile to JSON."""
        filepath = Path(path or f"config/units/{self.unit_id}.json")
        filepath.parent.mkdir(parents=True, exist_ok=True)
        self.updated_at = time.time()
        filepath.write_text(json.dumps(self._to_dict(), indent=2))

    @classmethod
    def load(cls, path: str) -> "UnitProfile":
        """Load unit profile from JSON."""
        data = json.loads(Path(path).read_text())
        return cls._from_dict(data)

    def _to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "unit_id": self.unit_id,
            "serial_number": self.serial_number,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "pipe_size": self.pipe_size,
            "year_built": self.year_built,
            "source": self.source,
            "source_listing_url": self.source_listing_url,
            "purchase_date": self.purchase_date,
            "notes": self.notes,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "location": {
                "latitude": self.location.latitude,
                "longitude": self.location.longitude,
                "address": self.location.address,
                "county": self.location.county,
                "state": self.location.state,
                "lease_name": self.location.lease_name,
                "well_id": self.location.well_id,
            },
            "components": {
                "meter_key": self.components.meter_key,
                "pump_key": self.components.pump_key,
                "divert_valve_key": self.components.divert_valve_key,
                "bsw_probe_key": self.components.bsw_probe_key,
                "sampler_key": self.components.sampler_key,
                "prover_key": self.components.prover_key,
                "has_strainer": self.components.has_strainer,
                "strainer_mesh": self.components.strainer_mesh,
                "has_air_eliminator": self.components.has_air_eliminator,
                "has_static_mixer": self.components.has_static_mixer,
                "has_test_thermowell": self.components.has_test_thermowell,
                "num_backpressure_valves": self.components.num_backpressure_valves,
                "num_pressure_transmitters": self.components.num_pressure_transmitters,
            },
            "electrical": {
                "main_power": self.electrical.main_power,
                "control_power": self.electrical.control_power,
                "io_bus": self.electrical.io_bus,
                "io_bus_address": self.electrical.io_bus_address,
                "di_module_channels": self.electrical.di_module_channels,
                "do_module_channels": self.electrical.do_module_channels,
                "ai_module_channels": self.electrical.ai_module_channels,
                "ao_module_channels": self.electrical.ao_module_channels,
                "has_pulse_counter": self.electrical.has_pulse_counter,
                "has_ups": self.electrical.has_ups,
            },
            "photos": [
                {
                    "file_path": p.file_path,
                    "timestamp": p.timestamp,
                    "description": p.description,
                    "gps_lat": p.gps_lat,
                    "gps_lon": p.gps_lon,
                    "camera_model": p.camera_model,
                    "tags": p.tags,
                } for p in self.photos
            ],
            "setpoint_overrides": self.setpoint_overrides,
            "custom_di": self.custom_di,
            "custom_do": self.custom_do,
            "custom_ai": self.custom_ai,
        }

    @classmethod
    def _from_dict(cls, data: dict) -> "UnitProfile":
        """Deserialize from dict."""
        profile = cls()
        for key in ("unit_id", "serial_number", "manufacturer", "model",
                     "pipe_size", "year_built", "source", "source_listing_url",
                     "purchase_date", "notes", "created_at", "updated_at"):
            if key in data:
                setattr(profile, key, data[key])

        if "status" in data:
            profile.status = UnitStatus(data["status"])

        if "location" in data:
            loc = data["location"]
            profile.location = GeoLocation(**loc)

        if "components" in data:
            comp = data["components"]
            profile.components = ComponentSelection(**comp)

        if "electrical" in data:
            elec = data["electrical"]
            profile.electrical = ElectricalConfig(**elec)

        if "photos" in data:
            profile.photos = [
                PhotoRecord(**p) for p in data["photos"]
            ]

        if "setpoint_overrides" in data:
            profile.setpoint_overrides = data["setpoint_overrides"]
        for key in ("custom_di", "custom_do", "custom_ai"):
            if key in data:
                setattr(profile, key, data[key])

        return profile

    def validate(self) -> list:
        """
        Validate that the profile has enough information
        to generate a working configuration. Returns a list
        of missing/invalid fields.
        """
        issues = []
        if not self.unit_id:
            issues.append("unit_id is required")
        if not self.components.meter_key:
            issues.append("No meter selected")
        if not self.components.pump_key:
            issues.append("No pump selected")
        if not self.components.divert_valve_key:
            issues.append("No divert valve selected")
        if not self.components.bsw_probe_key:
            issues.append("No BS&W probe selected")
        if not self.components.sampler_key:
            issues.append("No sampler selected")
        if self.pipe_size not in (2.0, 3.0, 4.0, 6.0):
            issues.append(f"Unusual pipe size: {self.pipe_size}")
        return issues
