"""
Unit Intake Form System
=========================
Structured intake processor for bringing new LACT units into
the fleet. Guides the operator through identification, component
selection, photo analysis, and configuration generation.

The intake process:
  1. Basic identification (serial, manufacturer, source)
  2. Photo upload and metadata extraction
  3. Component identification (from photos or manual selection)
  4. Location and electrical configuration
  5. Validation and config generation

Can be driven interactively (CLI) or programmatically (API).
"""

import json
import time
from pathlib import Path
from typing import Optional

from plc.fleet.unit_profile import (
    UnitProfile, UnitStatus, GeoLocation,
    ElectricalConfig, ComponentSelection, PhotoRecord,
)
from plc.fleet.components import (
    KNOWN_METERS, KNOWN_PUMPS, KNOWN_DIVERT_VALVES,
    KNOWN_BSW_PROBES, KNOWN_SAMPLERS, KNOWN_PROVERS,
)
from plc.fleet.photo_analyzer import PhotoAnalyzer


class IntakeForm:
    """
    Manages the intake process for a new LACT unit.

    Provides structured methods for each intake step plus
    validation and finalization.
    """

    def __init__(self, unit_id: str = ""):
        self.profile = UnitProfile()
        if unit_id:
            self.profile.unit_id = unit_id
        self.profile.status = UnitStatus.INTAKE
        self._photo_analyzer = PhotoAnalyzer()
        self._step_log: list = []

    @property
    def unit_id(self) -> str:
        return self.profile.unit_id

    def log_step(self, step: str, detail: str = ""):
        """Record an intake step for audit trail."""
        self._step_log.append({
            "timestamp": time.time(),
            "step": step,
            "detail": detail,
        })

    # ── Step 1: Basic Identification ─────────────────────────

    def set_identity(
        self,
        unit_id: str,
        serial_number: str = "",
        manufacturer: str = "",
        model: str = "",
        pipe_size: float = 3.0,
        year_built: int = 0,
        source: str = "",
        source_listing_url: str = "",
        notes: str = "",
    ):
        """Set the basic identity fields."""
        self.profile.unit_id = unit_id
        self.profile.serial_number = serial_number
        self.profile.manufacturer = manufacturer
        self.profile.model = model
        self.profile.pipe_size = pipe_size
        self.profile.year_built = year_built
        self.profile.source = source
        self.profile.source_listing_url = source_listing_url
        self.profile.notes = notes
        self.log_step("identity", f"ID={unit_id}, MFG={manufacturer}")

    # ── Step 2: Photo Processing ─────────────────────────────

    def add_photos(self, photo_paths: list) -> list:
        """
        Add photos and extract metadata. Returns list of
        PhotoRecord objects with extracted EXIF data.
        """
        records = []
        for path in photo_paths:
            record = self._photo_analyzer.analyze(path)
            self.profile.photos.append(record)
            records.append(record)

        self.log_step("photos", f"Added {len(records)} photos")

        # Auto-detect GPS location from first photo with GPS
        for rec in records:
            if rec.has_gps and self.profile.location.latitude == 0:
                self.profile.location.latitude = rec.gps_lat
                self.profile.location.longitude = rec.gps_lon
                self.log_step("auto_location", f"GPS from photo: {rec.gps_lat}, {rec.gps_lon}")
                break

        return records

    def get_photo_suggestions(self) -> dict:
        """
        Analyze all photos and return component identification
        suggestions based on visible nameplates, equipment, etc.
        """
        suggestions = {}
        all_tags = set()
        for photo in self.profile.photos:
            all_tags.update(photo.tags)

        # Tag-based component suggestions
        tag_mappings = {
            "smith": {"meter": ["smith_e3s1_3in", "smith_e3s1_4in", "smith_g6_2in"]},
            "e3": {"meter": ["smith_e3s1_3in", "smith_e3s1_4in"]},
            "hydromatic": {"divert_valve": ["hydromatic_3in", "hydromatic_4in"]},
            "clay_bailey": {"sampler": ["clay_bailey_15gal", "clay_bailey_5gal"]},
            "welker": {"sampler": ["welker_piston"]},
            "phase_dynamics": {"bsw_probe": ["phase_dynamics_4528", "phase_dynamics_analyzer"]},
            "4528": {"bsw_probe": ["phase_dynamics_4528"]},
        }

        for tag in all_tags:
            tag_lower = tag.lower()
            for keyword, mappings in tag_mappings.items():
                if keyword in tag_lower:
                    for component_type, keys in mappings.items():
                        suggestions.setdefault(component_type, []).extend(keys)

        # Deduplicate
        for key in suggestions:
            suggestions[key] = list(dict.fromkeys(suggestions[key]))

        return suggestions

    # ── Step 3: Component Selection ──────────────────────────

    def select_components(
        self,
        meter_key: str = "",
        pump_key: str = "",
        divert_valve_key: str = "",
        bsw_probe_key: str = "",
        sampler_key: str = "",
        prover_key: str = "none",
        has_strainer: bool = True,
        has_air_eliminator: bool = True,
        has_static_mixer: bool = True,
        has_test_thermowell: bool = True,
        num_backpressure_valves: int = 2,
        num_pressure_transmitters: int = 3,
    ):
        """Set component selections."""
        self.profile.components = ComponentSelection(
            meter_key=meter_key,
            pump_key=pump_key,
            divert_valve_key=divert_valve_key,
            bsw_probe_key=bsw_probe_key,
            sampler_key=sampler_key,
            prover_key=prover_key,
            has_strainer=has_strainer,
            has_air_eliminator=has_air_eliminator,
            has_static_mixer=has_static_mixer,
            has_test_thermowell=has_test_thermowell,
            num_backpressure_valves=num_backpressure_valves,
            num_pressure_transmitters=num_pressure_transmitters,
        )
        self.log_step("components", f"meter={meter_key}, pump={pump_key}")

    # ── Step 4: Location & Electrical ────────────────────────

    def set_location(
        self,
        latitude: float = 0.0,
        longitude: float = 0.0,
        address: str = "",
        county: str = "",
        state: str = "",
        lease_name: str = "",
        well_id: str = "",
    ):
        """Set the deployment location."""
        self.profile.location = GeoLocation(
            latitude=latitude,
            longitude=longitude,
            address=address,
            county=county,
            state=state,
            lease_name=lease_name,
            well_id=well_id,
        )
        self.log_step("location", f"Lease={lease_name}, {county} Co, {state}")

    def set_electrical(
        self,
        main_power: str = "480VAC_3PH",
        io_bus: str = "modbus_rtu",
        io_bus_address: str = "/dev/ttyUSB0",
        has_ups: bool = False,
    ):
        """Set electrical configuration."""
        self.profile.electrical = ElectricalConfig(
            main_power=main_power,
            io_bus=io_bus,
            io_bus_address=io_bus_address,
            has_ups=has_ups,
        )
        self.log_step("electrical", f"bus={io_bus}, power={main_power}")

    # ── Step 5: Setpoint Overrides ───────────────────────────

    def set_overrides(self, overrides: dict):
        """Set setpoint overrides from defaults."""
        self.profile.setpoint_overrides = overrides
        self.log_step("overrides", f"{len(overrides)} overrides set")

    # ── Validation & Finalization ────────────────────────────

    def validate(self) -> list:
        """Validate the intake form. Returns list of issues."""
        issues = self.profile.validate()

        # Check component keys exist in catalogs
        comp = self.profile.components
        if comp.meter_key and comp.meter_key not in KNOWN_METERS:
            issues.append(f"Unknown meter: {comp.meter_key}")
        if comp.pump_key and comp.pump_key not in KNOWN_PUMPS:
            issues.append(f"Unknown pump: {comp.pump_key}")
        if comp.divert_valve_key and comp.divert_valve_key not in KNOWN_DIVERT_VALVES:
            issues.append(f"Unknown divert valve: {comp.divert_valve_key}")
        if comp.bsw_probe_key and comp.bsw_probe_key not in KNOWN_BSW_PROBES:
            issues.append(f"Unknown BS&W probe: {comp.bsw_probe_key}")
        if comp.sampler_key and comp.sampler_key not in KNOWN_SAMPLERS:
            issues.append(f"Unknown sampler: {comp.sampler_key}")

        return issues

    def finalize(self) -> UnitProfile:
        """
        Finalize the intake and mark the profile as configured.
        Raises ValueError if validation fails.
        """
        issues = self.validate()
        if issues:
            raise ValueError(f"Intake validation failed: {'; '.join(issues)}")

        self.profile.status = UnitStatus.CONFIGURED
        self.profile.updated_at = time.time()
        self.log_step("finalized", "Profile validated and marked configured")
        return self.profile

    def get_audit_log(self) -> list:
        """Return the intake step log for audit purposes."""
        return self._step_log.copy()

    def save_progress(self, directory: str = "config/units"):
        """Save the current intake state (even if incomplete)."""
        self.profile.save(
            f"{directory}/{self.profile.unit_id or 'draft'}.json"
        )
        self.log_step("saved", f"Progress saved to {directory}")

    @classmethod
    def resume(cls, path: str) -> "IntakeForm":
        """Resume an incomplete intake from saved profile."""
        form = cls()
        form.profile = UnitProfile.load(path)
        form.log_step("resumed", f"Loaded from {path}")
        return form


# ── Quick Intake Templates ───────────────────────────────────

def quick_intake_scs_3inch(
    unit_id: str,
    serial: str = "",
    location_state: str = "TX",
) -> IntakeForm:
    """
    Pre-filled intake for the common SCS Technologies 3" LACT.
    These are the most common surplus units on the market.
    """
    form = IntakeForm(unit_id=unit_id)
    form.set_identity(
        unit_id=unit_id,
        serial_number=serial,
        manufacturer="SCS Technologies",
        model='3" LACT Unit',
        pipe_size=3.0,
        source="Surplus Market",
    )
    form.select_components(
        meter_key="smith_e3s1_3in",
        pump_key="generic_centrifugal_480v",
        divert_valve_key="hydromatic_3in",
        bsw_probe_key="phase_dynamics_4528",
        sampler_key="clay_bailey_15gal",
        prover_key="none",
    )
    form.set_location(state=location_state)
    return form


def quick_intake_4inch(
    unit_id: str,
    serial: str = "",
    location_state: str = "TX",
) -> IntakeForm:
    """
    Pre-filled intake for 4" LACT units.
    """
    form = IntakeForm(unit_id=unit_id)
    form.set_identity(
        unit_id=unit_id,
        serial_number=serial,
        manufacturer="Generic",
        model='4" LACT Unit',
        pipe_size=4.0,
        source="Surplus Market",
    )
    form.select_components(
        meter_key="smith_e3s1_4in",
        pump_key="generic_centrifugal_480v",
        divert_valve_key="hydromatic_4in",
        bsw_probe_key="phase_dynamics_4528",
        sampler_key="welker_piston",
        prover_key="none",
    )
    form.set_location(state=location_state)
    return form
