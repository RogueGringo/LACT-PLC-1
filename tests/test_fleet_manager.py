"""Tests for the fleet manager."""

import pytest
import tempfile
import os
from plc.fleet.fleet_manager import FleetManager
from plc.fleet.unit_profile import UnitProfile, UnitStatus, ComponentSelection
from plc.fleet.intake import quick_intake_scs_3inch


def _make_unit(unit_id, manufacturer="SCS", state="TX", **kwargs) -> UnitProfile:
    comp = ComponentSelection(
        meter_key="smith_e3s1_3in",
        pump_key="generic_centrifugal_480v",
        divert_valve_key="hydromatic_3in",
        bsw_probe_key="phase_dynamics_4528",
        sampler_key="clay_bailey_15gal",
        **kwargs,
    )
    profile = UnitProfile(
        unit_id=unit_id,
        manufacturer=manufacturer,
        status=UnitStatus.CONFIGURED,
        components=comp,
    )
    profile.location.state = state
    return profile


class TestFleetManager:
    @pytest.fixture
    def fleet(self, tmp_path):
        return FleetManager(fleet_dir=str(tmp_path / "fleet"))

    def test_empty_fleet(self, fleet):
        assert fleet.unit_count == 0

    def test_register_unit(self, fleet):
        unit = _make_unit("LACT-001")
        fleet.register_unit(unit)
        assert fleet.unit_count == 1

    def test_get_unit(self, fleet):
        unit = _make_unit("LACT-001", manufacturer="SCS Technologies")
        fleet.register_unit(unit)
        retrieved = fleet.get_unit("LACT-001")
        assert retrieved.manufacturer == "SCS Technologies"

    def test_remove_unit(self, fleet):
        unit = _make_unit("LACT-001")
        fleet.register_unit(unit)
        assert fleet.remove_unit("LACT-001") is True
        assert fleet.unit_count == 0

    def test_remove_nonexistent(self, fleet):
        assert fleet.remove_unit("NOPE") is False

    def test_list_units(self, fleet):
        fleet.register_unit(_make_unit("LACT-002"))
        fleet.register_unit(_make_unit("LACT-001"))
        units = fleet.list_units()
        assert len(units) == 2
        # Sorted by ID
        assert units[0].unit_id == "LACT-001"

    def test_list_by_status(self, fleet):
        u1 = _make_unit("LACT-001")
        u1.status = UnitStatus.DEPLOYED
        u2 = _make_unit("LACT-002")
        u2.status = UnitStatus.CONFIGURED
        fleet.register_unit(u1)
        fleet.register_unit(u2)
        deployed = fleet.list_units(status=UnitStatus.DEPLOYED)
        assert len(deployed) == 1
        assert deployed[0].unit_id == "LACT-001"

    def test_search_units(self, fleet):
        fleet.register_unit(_make_unit("LACT-001", manufacturer="SCS Technologies"))
        fleet.register_unit(_make_unit("LACT-002", manufacturer="Generic"))
        results = fleet.search_units("SCS")
        assert len(results) == 1
        assert results[0].unit_id == "LACT-001"

    def test_generate_config(self, fleet):
        fleet.register_unit(_make_unit("LACT-001"))
        io_map, setpoints, alarms = fleet.generate_config("LACT-001")
        assert len(io_map.get_all_points()) > 20
        assert setpoints.meter_k_factor == 100.0

    def test_generate_config_unknown_unit(self, fleet):
        with pytest.raises(ValueError):
            fleet.generate_config("NOPE")

    def test_build_flow_graph(self, fleet):
        fleet.register_unit(_make_unit("LACT-001"))
        graph = fleet.build_flow_graph("LACT-001")
        assert len(graph.nodes) > 10

    def test_compare_units(self, fleet):
        fleet.register_unit(_make_unit("LACT-001"))
        fleet.register_unit(_make_unit("LACT-002"))
        diff = fleet.compare_units("LACT-001", "LACT-002")
        assert diff["topologically_equivalent"] is True

    def test_fleet_summary(self, fleet):
        fleet.register_unit(_make_unit("LACT-001", state="TX"))
        fleet.register_unit(_make_unit("LACT-002", state="NM"))
        fleet.register_unit(_make_unit("LACT-003", state="TX"))
        summary = fleet.fleet_summary()
        assert summary["total_units"] == 3
        assert summary["by_state"]["TX"] == 2
        assert summary["by_state"]["NM"] == 1

    def test_persistence(self, tmp_path):
        fleet_dir = str(tmp_path / "fleet_persist")
        fleet1 = FleetManager(fleet_dir=fleet_dir)
        fleet1.register_unit(_make_unit("LACT-001"))
        fleet1.register_unit(_make_unit("LACT-002"))

        # Create a new fleet manager loading from same dir
        fleet2 = FleetManager(fleet_dir=fleet_dir)
        assert fleet2.unit_count == 2
        assert fleet2.get_unit("LACT-001") is not None

    def test_export_and_import(self, fleet, tmp_path):
        fleet.register_unit(_make_unit("LACT-001"))
        fleet.register_unit(_make_unit("LACT-002"))

        export_path = str(tmp_path / "export.json")
        fleet.export_fleet(export_path)

        fleet2 = FleetManager(fleet_dir=str(tmp_path / "fleet2"))
        fleet2.import_fleet(export_path)
        assert fleet2.unit_count == 2

    def test_intake_to_registration(self, fleet):
        form = quick_intake_scs_3inch("LACT-INTAKE-001", serial="6113-045")
        profile = fleet.complete_intake(form)
        assert profile.status == UnitStatus.CONFIGURED
        assert fleet.unit_count == 1
        assert fleet.get_unit("LACT-INTAKE-001") is not None

    def test_config_summary(self, fleet):
        fleet.register_unit(_make_unit("LACT-001"))
        summary = fleet.get_config_summary("LACT-001")
        assert summary["unit_id"] == "LACT-001"
        assert summary["total_io_points"] > 0

    def test_empty_fleet_summary(self, fleet):
        summary = fleet.fleet_summary()
        assert summary["total_units"] == 0

    def test_register_requires_id(self, fleet):
        with pytest.raises(ValueError):
            fleet.register_unit(UnitProfile())
