"""Tests for the unit profile data model."""

import pytest
import json
import tempfile
import os
from plc.fleet.unit_profile import (
    UnitProfile, UnitStatus, GeoLocation,
    ElectricalConfig, ComponentSelection, PhotoRecord,
)


class TestUnitProfile:
    def test_default_profile(self):
        profile = UnitProfile()
        assert profile.status == UnitStatus.INTAKE
        assert profile.pipe_size == 3.0
        assert profile.created_at > 0

    def test_set_identity(self):
        profile = UnitProfile()
        profile.unit_id = "LACT-001"
        profile.manufacturer = "SCS Technologies"
        profile.model = '3" LACT'
        assert profile.unit_id == "LACT-001"
        assert profile.manufacturer == "SCS Technologies"

    def test_component_selection(self):
        comp = ComponentSelection(
            meter_key="smith_e3s1_3in",
            pump_key="generic_centrifugal_480v",
            divert_valve_key="hydromatic_3in",
            bsw_probe_key="phase_dynamics_4528",
            sampler_key="clay_bailey_15gal",
        )
        assert comp.meter_key == "smith_e3s1_3in"
        assert comp.has_strainer is True
        assert comp.has_air_eliminator is True

    def test_geo_location(self):
        loc = GeoLocation(
            latitude=32.305,
            longitude=-101.920,
            state="TX",
            county="Martin",
            lease_name="Test Lease",
        )
        assert loc.state == "TX"
        assert loc.latitude == 32.305

    def test_photo_record_has_gps(self):
        rec = PhotoRecord(gps_lat=32.0, gps_lon=-101.0)
        assert rec.has_gps is True

    def test_photo_record_no_gps(self):
        rec = PhotoRecord()
        assert rec.has_gps is False

    def test_validate_complete_profile(self):
        profile = UnitProfile(
            unit_id="LACT-001",
            components=ComponentSelection(
                meter_key="smith_e3s1_3in",
                pump_key="generic_centrifugal_480v",
                divert_valve_key="hydromatic_3in",
                bsw_probe_key="phase_dynamics_4528",
                sampler_key="clay_bailey_15gal",
            ),
        )
        issues = profile.validate()
        assert len(issues) == 0

    def test_validate_missing_meter(self):
        profile = UnitProfile(unit_id="LACT-001")
        issues = profile.validate()
        assert any("meter" in i.lower() for i in issues)

    def test_validate_missing_unit_id(self):
        profile = UnitProfile()
        issues = profile.validate()
        assert any("unit_id" in i for i in issues)

    def test_save_and_load(self):
        profile = UnitProfile(
            unit_id="LACT-TEST",
            manufacturer="Test MFG",
            serial_number="SN-123",
            pipe_size=3.0,
        )
        profile.components = ComponentSelection(
            meter_key="smith_e3s1_3in",
            pump_key="generic_centrifugal_480v",
        )
        profile.location = GeoLocation(state="TX", county="Martin")
        profile.photos.append(PhotoRecord(
            file_path="/tmp/test.jpg",
            gps_lat=32.0,
            gps_lon=-101.0,
        ))

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_unit.json")
            profile.save(path)

            loaded = UnitProfile.load(path)
            assert loaded.unit_id == "LACT-TEST"
            assert loaded.manufacturer == "Test MFG"
            assert loaded.components.meter_key == "smith_e3s1_3in"
            assert loaded.location.state == "TX"
            assert len(loaded.photos) == 1
            assert loaded.photos[0].gps_lat == 32.0

    def test_setpoint_overrides(self):
        profile = UnitProfile(unit_id="LACT-001")
        profile.setpoint_overrides = {
            "bsw_divert_pct": 0.8,
            "meter_k_factor": 105.0,
        }
        assert profile.setpoint_overrides["bsw_divert_pct"] == 0.8

    def test_status_transitions(self):
        profile = UnitProfile()
        assert profile.status == UnitStatus.INTAKE
        profile.status = UnitStatus.CONFIGURED
        assert profile.status == UnitStatus.CONFIGURED
        profile.status = UnitStatus.DEPLOYED
        assert profile.status == UnitStatus.DEPLOYED
