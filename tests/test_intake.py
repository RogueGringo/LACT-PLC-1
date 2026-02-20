"""Tests for the unit intake form system."""

import pytest
from plc.fleet.intake import (
    IntakeForm, quick_intake_scs_3inch, quick_intake_4inch,
)
from plc.fleet.unit_profile import UnitStatus


class TestIntakeForm:
    def test_create_intake(self):
        form = IntakeForm(unit_id="LACT-001")
        assert form.unit_id == "LACT-001"
        assert form.profile.status == UnitStatus.INTAKE

    def test_set_identity(self):
        form = IntakeForm()
        form.set_identity(
            unit_id="LACT-001",
            serial_number="6113-045",
            manufacturer="SCS Technologies",
            model='3" LACT Unit',
            pipe_size=3.0,
            source="GovPlanet",
        )
        assert form.profile.unit_id == "LACT-001"
        assert form.profile.manufacturer == "SCS Technologies"
        assert form.profile.source == "GovPlanet"

    def test_select_components(self):
        form = IntakeForm(unit_id="LACT-001")
        form.select_components(
            meter_key="smith_e3s1_3in",
            pump_key="generic_centrifugal_480v",
            divert_valve_key="hydromatic_3in",
            bsw_probe_key="phase_dynamics_4528",
            sampler_key="clay_bailey_15gal",
        )
        assert form.profile.components.meter_key == "smith_e3s1_3in"
        assert form.profile.components.pump_key == "generic_centrifugal_480v"

    def test_set_location(self):
        form = IntakeForm(unit_id="LACT-001")
        form.set_location(
            latitude=32.305,
            longitude=-101.920,
            state="TX",
            county="Martin",
            lease_name="Smith Ranch",
        )
        assert form.profile.location.state == "TX"
        assert form.profile.location.lease_name == "Smith Ranch"

    def test_set_electrical(self):
        form = IntakeForm(unit_id="LACT-001")
        form.set_electrical(
            main_power="480VAC_3PH",
            io_bus="modbus_rtu",
            io_bus_address="/dev/ttyUSB0",
        )
        assert form.profile.electrical.io_bus == "modbus_rtu"

    def test_validate_incomplete(self):
        form = IntakeForm(unit_id="LACT-001")
        issues = form.validate()
        assert len(issues) > 0

    def test_validate_invalid_component(self):
        form = IntakeForm(unit_id="LACT-001")
        form.select_components(
            meter_key="nonexistent_meter",
            pump_key="generic_centrifugal_480v",
            divert_valve_key="hydromatic_3in",
            bsw_probe_key="phase_dynamics_4528",
            sampler_key="clay_bailey_15gal",
        )
        issues = form.validate()
        assert any("nonexistent_meter" in i for i in issues)

    def test_finalize_valid(self):
        form = IntakeForm()
        form.set_identity(unit_id="LACT-001", manufacturer="SCS")
        form.select_components(
            meter_key="smith_e3s1_3in",
            pump_key="generic_centrifugal_480v",
            divert_valve_key="hydromatic_3in",
            bsw_probe_key="phase_dynamics_4528",
            sampler_key="clay_bailey_15gal",
        )
        profile = form.finalize()
        assert profile.status == UnitStatus.CONFIGURED

    def test_finalize_invalid_raises(self):
        form = IntakeForm()
        with pytest.raises(ValueError):
            form.finalize()

    def test_audit_log(self):
        form = IntakeForm(unit_id="LACT-001")
        form.set_identity(unit_id="LACT-001", manufacturer="SCS")
        form.select_components(
            meter_key="smith_e3s1_3in",
            pump_key="generic_centrifugal_480v",
            divert_valve_key="hydromatic_3in",
            bsw_probe_key="phase_dynamics_4528",
            sampler_key="clay_bailey_15gal",
        )
        log = form.get_audit_log()
        assert len(log) >= 2
        assert log[0]["step"] == "identity"
        assert log[1]["step"] == "components"

    def test_setpoint_overrides(self):
        form = IntakeForm(unit_id="LACT-001")
        form.set_overrides({"bsw_divert_pct": 0.8, "meter_k_factor": 105.0})
        assert form.profile.setpoint_overrides["bsw_divert_pct"] == 0.8


class TestQuickIntake:
    def test_scs_3inch_template(self):
        form = quick_intake_scs_3inch("LACT-SCS-001", serial="6113-045")
        assert form.profile.manufacturer == "SCS Technologies"
        assert form.profile.components.meter_key == "smith_e3s1_3in"
        assert form.profile.pipe_size == 3.0
        issues = form.validate()
        assert len(issues) == 0

    def test_4inch_template(self):
        form = quick_intake_4inch("LACT-4IN-001")
        assert form.profile.pipe_size == 4.0
        assert form.profile.components.meter_key == "smith_e3s1_4in"
        issues = form.validate()
        assert len(issues) == 0

    def test_quick_intake_is_finalizable(self):
        form = quick_intake_scs_3inch("LACT-QUICK")
        profile = form.finalize()
        assert profile.status == UnitStatus.CONFIGURED
