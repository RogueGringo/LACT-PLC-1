"""
Fleet Manager
===============
Manages multiple LACT units across a fleet. Provides:

  - Unit registry (add, remove, list, search)
  - Status overview across all units
  - Configuration deployment tracking
  - Comparative analysis between units
  - Fleet-wide statistics

This is the top-level orchestrator for multi-unit operations.
"""

import json
import time
import logging
from pathlib import Path
from typing import Optional

from plc.fleet.unit_profile import UnitProfile, UnitStatus
from plc.fleet.config_generator import ConfigGenerator
from plc.fleet.flow_graph import FlowGraph, build_flow_graph
from plc.fleet.intake import IntakeForm

logger = logging.getLogger(__name__)


class FleetManager:
    """
    Central registry and manager for all LACT units in the fleet.
    """

    def __init__(self, fleet_dir: str = "config/fleet"):
        self.fleet_dir = Path(fleet_dir)
        self.fleet_dir.mkdir(parents=True, exist_ok=True)
        self._units: dict = {}  # unit_id → UnitProfile
        self._load_fleet()

    # ── Unit Registry ────────────────────────────────────────

    @property
    def unit_count(self) -> int:
        return len(self._units)

    def register_unit(self, profile: UnitProfile):
        """Add a unit to the fleet."""
        if not profile.unit_id:
            raise ValueError("Unit must have an ID")
        self._units[profile.unit_id] = profile
        self._save_unit(profile)
        logger.info("Registered unit: %s", profile.unit_id)

    def remove_unit(self, unit_id: str) -> bool:
        """Remove a unit from the fleet."""
        if unit_id not in self._units:
            return False
        del self._units[unit_id]
        unit_file = self.fleet_dir / f"{unit_id}.json"
        if unit_file.exists():
            unit_file.unlink()
        logger.info("Removed unit: %s", unit_id)
        return True

    def get_unit(self, unit_id: str) -> Optional[UnitProfile]:
        """Get a unit profile by ID."""
        return self._units.get(unit_id)

    def list_units(self, status: UnitStatus = None) -> list:
        """List all units, optionally filtered by status."""
        units = list(self._units.values())
        if status:
            units = [u for u in units if u.status == status]
        return sorted(units, key=lambda u: u.unit_id)

    def search_units(self, query: str) -> list:
        """Search units by ID, manufacturer, model, or location."""
        query_lower = query.lower()
        results = []
        for unit in self._units.values():
            searchable = " ".join([
                unit.unit_id,
                unit.manufacturer,
                unit.model,
                unit.serial_number,
                unit.location.state,
                unit.location.lease_name,
            ]).lower()
            if query_lower in searchable:
                results.append(unit)
        return results

    # ── Intake Processing ────────────────────────────────────

    def start_intake(self, unit_id: str) -> IntakeForm:
        """Start the intake process for a new unit."""
        form = IntakeForm(unit_id=unit_id)
        return form

    def complete_intake(self, form: IntakeForm) -> UnitProfile:
        """Finalize an intake form and register the unit."""
        profile = form.finalize()
        self.register_unit(profile)
        return profile

    # ── Configuration ────────────────────────────────────────

    def generate_config(self, unit_id: str) -> tuple:
        """
        Generate PLC configuration for a unit.
        Returns (IOMap, Setpoints, AlarmConfig).
        """
        profile = self.get_unit(unit_id)
        if not profile:
            raise ValueError(f"Unit not found: {unit_id}")
        gen = ConfigGenerator(profile)
        return gen.generate_all()

    def get_config_summary(self, unit_id: str) -> dict:
        """Get a summary of what config will be generated."""
        profile = self.get_unit(unit_id)
        if not profile:
            return {}
        gen = ConfigGenerator(profile)
        return gen.summary()

    # ── Flow Graphs ──────────────────────────────────────────

    def build_flow_graph(self, unit_id: str) -> FlowGraph:
        """Build the topological flow graph for a unit."""
        profile = self.get_unit(unit_id)
        if not profile:
            raise ValueError(f"Unit not found: {unit_id}")
        return build_flow_graph(profile)

    def compare_units(self, unit_id_a: str, unit_id_b: str) -> dict:
        """Compare the topological structure of two units."""
        graph_a = self.build_flow_graph(unit_id_a)
        graph_b = self.build_flow_graph(unit_id_b)
        return graph_a.compare(graph_b)

    # ── Fleet Statistics ─────────────────────────────────────

    def fleet_summary(self) -> dict:
        """Return fleet-wide statistics."""
        units = list(self._units.values())
        if not units:
            return {"total_units": 0}

        status_counts = {}
        for status in UnitStatus:
            count = sum(1 for u in units if u.status == status)
            if count > 0:
                status_counts[status.value] = count

        manufacturers = {}
        for u in units:
            mfg = u.manufacturer or "Unknown"
            manufacturers[mfg] = manufacturers.get(mfg, 0) + 1

        pipe_sizes = {}
        for u in units:
            ps = f'{u.pipe_size}"'
            pipe_sizes[ps] = pipe_sizes.get(ps, 0) + 1

        states = {}
        for u in units:
            st = u.location.state or "Unknown"
            states[st] = states.get(st, 0) + 1

        return {
            "total_units": len(units),
            "by_status": status_counts,
            "by_manufacturer": manufacturers,
            "by_pipe_size": pipe_sizes,
            "by_state": states,
        }

    # ── Persistence ──────────────────────────────────────────

    def _save_unit(self, profile: UnitProfile):
        """Save a single unit profile to the fleet directory."""
        profile.save(str(self.fleet_dir / f"{profile.unit_id}.json"))

    def _load_fleet(self):
        """Load all unit profiles from the fleet directory."""
        for path in self.fleet_dir.glob("*.json"):
            try:
                profile = UnitProfile.load(str(path))
                if profile.unit_id:
                    self._units[profile.unit_id] = profile
            except Exception:
                logger.warning("Failed to load unit profile: %s", path)

    def save_all(self):
        """Save all unit profiles."""
        for profile in self._units.values():
            self._save_unit(profile)

    def export_fleet(self, path: str):
        """Export the entire fleet to a single JSON file."""
        data = {
            "fleet_export_time": time.time(),
            "units": {
                uid: profile._to_dict()
                for uid, profile in self._units.items()
            },
        }
        Path(path).write_text(json.dumps(data, indent=2))

    def import_fleet(self, path: str):
        """Import units from a fleet export file."""
        data = json.loads(Path(path).read_text())
        for uid, unit_data in data.get("units", {}).items():
            profile = UnitProfile._from_dict(unit_data)
            self._units[profile.unit_id] = profile
            self._save_unit(profile)
