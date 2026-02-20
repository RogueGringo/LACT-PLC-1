"""Tests for the configuration generator."""

import pytest
from plc.fleet.unit_profile import UnitProfile, ComponentSelection
from plc.fleet.config_generator import ConfigGenerator
from plc.config.io_map import SignalType


def _make_profile(
    meter="smith_e3s1_3in",
    pump="generic_centrifugal_480v",
    divert="hydromatic_3in",
    bsw="phase_dynamics_4528",
    sampler="clay_bailey_15gal",
    prover="none",
    **kwargs,
) -> UnitProfile:
    """Helper to create a test profile."""
    comp_kwargs = {
        "meter_key": meter,
        "pump_key": pump,
        "divert_valve_key": divert,
        "bsw_probe_key": bsw,
        "sampler_key": sampler,
        "prover_key": prover,
    }
    comp_kwargs.update(kwargs)
    return UnitProfile(
        unit_id="TEST-001",
        components=ComponentSelection(**comp_kwargs),
    )


class TestIOMapGeneration:
    def test_generates_io_map(self):
        profile = _make_profile()
        gen = ConfigGenerator(profile)
        io_map = gen.generate_io_map()
        assert len(io_map.digital_inputs) > 0
        assert len(io_map.digital_outputs) > 0
        assert len(io_map.analog_inputs) > 0

    def test_standard_di_tags_present(self):
        profile = _make_profile()
        gen = ConfigGenerator(profile)
        io_map = gen.generate_io_map()
        required_di = [
            "DI_INLET_VLV_OPEN", "DI_PUMP_RUNNING", "DI_PUMP_OVERLOAD",
            "DI_DIVERT_SALES", "DI_DIVERT_DIVERT", "DI_ESTOP",
            "DI_OUTLET_VLV_OPEN",
        ]
        for tag in required_di:
            assert tag in io_map.digital_inputs, f"Missing DI: {tag}"

    def test_standard_do_tags_present(self):
        profile = _make_profile()
        gen = ConfigGenerator(profile)
        io_map = gen.generate_io_map()
        required_do = [
            "DO_PUMP_START", "DO_DIVERT_CMD", "DO_SAMPLE_SOL",
            "DO_ALARM_BEACON", "DO_ALARM_HORN",
        ]
        for tag in required_do:
            assert tag in io_map.digital_outputs, f"Missing DO: {tag}"

    def test_standard_ai_tags_present(self):
        profile = _make_profile()
        gen = ConfigGenerator(profile)
        io_map = gen.generate_io_map()
        required_ai = ["AI_INLET_PRESS", "AI_BSW_PROBE", "AI_METER_TEMP"]
        for tag in required_ai:
            assert tag in io_map.analog_inputs, f"Missing AI: {tag}"

    def test_pulse_input_present(self):
        profile = _make_profile()
        gen = ConfigGenerator(profile)
        io_map = gen.generate_io_map()
        assert "PI_METER_PULSE" in io_map.pulse_inputs

    def test_no_strainer_removes_strainer_di(self):
        profile = _make_profile(has_strainer=False)
        gen = ConfigGenerator(profile)
        io_map = gen.generate_io_map()
        assert "DI_STRAINER_HI_DP" not in io_map.digital_inputs

    def test_no_air_eliminator(self):
        profile = _make_profile(has_air_eliminator=False)
        gen = ConfigGenerator(profile)
        io_map = gen.generate_io_map()
        assert "DI_AIR_ELIM_FLOAT" not in io_map.digital_inputs

    def test_prover_adds_io(self):
        profile = _make_profile(prover="portable_pipe")
        gen = ConfigGenerator(profile)
        io_map = gen.generate_io_map()
        assert "DI_PROVER_VLV_OPEN" in io_map.digital_inputs
        assert "DO_PROVER_VLV_CMD" in io_map.digital_outputs

    def test_no_prover_no_prover_io(self):
        profile = _make_profile(prover="none")
        gen = ConfigGenerator(profile)
        io_map = gen.generate_io_map()
        assert "DI_PROVER_VLV_OPEN" not in io_map.digital_inputs
        assert "DO_PROVER_VLV_CMD" not in io_map.digital_outputs

    def test_modbus_addresses_unique(self):
        profile = _make_profile()
        gen = ConfigGenerator(profile)
        io_map = gen.generate_io_map()
        all_points = io_map.get_all_points()
        addresses_by_type = {}
        for tag, point in all_points.items():
            key = point.signal_type
            addr = point.address
            addresses_by_type.setdefault(key, set())
            assert addr not in addresses_by_type[key], \
                f"Duplicate address {addr} for type {key}: {tag}"
            addresses_by_type[key].add(addr)

    def test_mixing_pump_included_when_sampler_has_it(self):
        profile = _make_profile(sampler="clay_bailey_15gal")
        gen = ConfigGenerator(profile)
        io_map = gen.generate_io_map()
        assert "DO_SAMPLE_MIX_PUMP" in io_map.digital_outputs

    def test_no_mixing_pump_when_sampler_lacks_it(self):
        profile = _make_profile(sampler="clay_bailey_5gal")
        gen = ConfigGenerator(profile)
        io_map = gen.generate_io_map()
        assert "DO_SAMPLE_MIX_PUMP" not in io_map.digital_outputs


class TestSetpointsGeneration:
    def test_generates_setpoints(self):
        profile = _make_profile()
        gen = ConfigGenerator(profile)
        sp = gen.generate_setpoints()
        assert sp.meter_k_factor == 100.0  # Smith E3-S1 3" default

    def test_meter_specific_k_factor(self):
        profile = _make_profile(meter="smith_e3s1_4in")
        gen = ConfigGenerator(profile)
        sp = gen.generate_setpoints()
        assert sp.meter_k_factor == 50.0  # 4" meter default

    def test_meter_flow_range(self):
        profile = _make_profile(meter="smith_e3s1_3in")
        gen = ConfigGenerator(profile)
        sp = gen.generate_setpoints()
        assert sp.meter_min_flow_bph == 30.0
        assert sp.meter_max_flow_bph == 750.0

    def test_divert_travel_timeout(self):
        profile = _make_profile(divert="hydromatic_3in")
        gen = ConfigGenerator(profile)
        sp = gen.generate_setpoints()
        # Travel time (10s) + 5s buffer
        assert sp.divert_travel_timeout_sec == 15.0

    def test_sampler_pot_size(self):
        profile = _make_profile(sampler="clay_bailey_15gal")
        gen = ConfigGenerator(profile)
        sp = gen.generate_setpoints()
        assert sp.sample_pot_full_gal == 15.0

    def test_user_overrides_applied(self):
        profile = _make_profile()
        profile.setpoint_overrides = {
            "bsw_divert_pct": 0.8,
            "meter_k_factor": 105.2,
        }
        gen = ConfigGenerator(profile)
        sp = gen.generate_setpoints()
        assert sp.bsw_divert_pct == 0.8
        assert sp.meter_k_factor == 105.2


class TestAlarmGeneration:
    def test_generates_alarms(self):
        profile = _make_profile()
        gen = ConfigGenerator(profile)
        alarms = gen.generate_alarms()
        assert "ALM_ESTOP" in alarms.definitions
        assert "ALM_PUMP_OVERLOAD" in alarms.definitions

    def test_no_strainer_removes_strainer_alarm(self):
        profile = _make_profile(has_strainer=False)
        gen = ConfigGenerator(profile)
        alarms = gen.generate_alarms()
        assert "ALM_STRAINER_DP_HI" not in alarms.definitions

    def test_no_air_elim_removes_gas_alarm(self):
        profile = _make_profile(has_air_eliminator=False)
        gen = ConfigGenerator(profile)
        alarms = gen.generate_alarms()
        assert "ALM_GAS_DETECTED" not in alarms.definitions

    def test_no_prover_removes_proving_alarms(self):
        profile = _make_profile(prover="none")
        gen = ConfigGenerator(profile)
        alarms = gen.generate_alarms()
        assert "ALM_PROVE_REPEAT_FAIL" not in alarms.definitions
        assert "ALM_PROVE_MF_RANGE" not in alarms.definitions


class TestConfigSummary:
    def test_summary_returns_dict(self):
        profile = _make_profile()
        gen = ConfigGenerator(profile)
        summary = gen.summary()
        assert summary["unit_id"] == "TEST-001"
        assert summary["total_io_points"] > 20
        assert summary["meter"] == "smith_e3s1_3in"

    def test_generate_all_returns_tuple(self):
        profile = _make_profile()
        gen = ConfigGenerator(profile)
        io_map, setpoints, alarms = gen.generate_all()
        assert len(io_map.get_all_points()) > 0
        assert setpoints.meter_k_factor > 0
        assert len(alarms.definitions) > 0
