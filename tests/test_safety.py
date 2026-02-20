"""
Tests for the Safety Interlock Manager.
"""

import time
import pytest

from plc.core.safety import SafetyManager
from plc.core.data_store import DataStore
from plc.config.setpoints import Setpoints
from plc.config.alarms import AlarmConfig, AlarmPriority


class TestSafetyManager:
    """Test safety interlock evaluation and alarm management."""

    def test_no_alarms_on_init(self, safety_manager):
        safety_manager.execute()
        assert len(safety_manager.get_active_alarms()) == 0

    def test_estop_alarm(self, safety_manager, data_store):
        data_store.write("DI_ESTOP", True)
        safety_manager.execute()
        active = safety_manager.get_active_alarms()
        tags = [a.definition.tag for a in active]
        assert "ALM_ESTOP" in tags
        assert safety_manager.shutdown_requested

    def test_estop_clears(self, safety_manager, data_store):
        data_store.write("DI_ESTOP", True)
        safety_manager.execute()
        assert len(safety_manager.get_active_alarms()) > 0

        # Acknowledge and clear
        safety_manager.acknowledge_alarm("ALM_ESTOP")
        data_store.write("DI_ESTOP", False)
        safety_manager.execute()
        assert not any(
            a.definition.tag == "ALM_ESTOP"
            for a in safety_manager.get_active_alarms()
        )

    def test_pump_overload_alarm(self, safety_manager, data_store):
        data_store.write("DI_PUMP_OVERLOAD", True)
        safety_manager.execute()
        tags = [a.definition.tag for a in safety_manager.get_active_alarms()]
        assert "ALM_PUMP_OVERLOAD" in tags
        assert safety_manager.shutdown_requested

    def test_bsw_high_alarm(self, safety_manager, data_store, setpoints):
        data_store.write("AI_BSW_PROBE", setpoints.bsw_alarm_pct + 0.1)
        safety_manager.execute()
        tags = [a.definition.tag for a in safety_manager.get_active_alarms()]
        assert "ALM_BSW_HIGH" in tags

    def test_bsw_divert_alarm(self, safety_manager, data_store, setpoints):
        data_store.write("AI_BSW_PROBE", setpoints.bsw_divert_pct + 0.1)
        safety_manager.execute()
        tags = [a.definition.tag for a in safety_manager.get_active_alarms()]
        assert "ALM_BSW_DIVERT" in tags
        assert safety_manager.divert_requested

    def test_bsw_probe_failure(self, safety_manager, data_store):
        data_store.write("AI_BSW_PROBE", 0.5, quality="BAD")
        safety_manager.execute()
        tags = [a.definition.tag for a in safety_manager.get_active_alarms()]
        assert "ALM_BSW_PROBE_FAIL" in tags

    def test_inlet_pressure_low(self, safety_manager, data_store, setpoints):
        data_store.write("DI_PUMP_RUNNING", True)
        data_store.write("AI_INLET_PRESS", setpoints.inlet_press_lo_psi - 1)
        safety_manager.execute()
        tags = [a.definition.tag for a in safety_manager.get_active_alarms()]
        assert "ALM_INLET_PRESS_LO" in tags

    def test_inlet_pressure_high(self, safety_manager, data_store, setpoints):
        data_store.write("AI_INLET_PRESS", setpoints.inlet_press_hi_psi + 10)
        safety_manager.execute()
        tags = [a.definition.tag for a in safety_manager.get_active_alarms()]
        assert "ALM_INLET_PRESS_HI" in tags

    def test_temperature_alarms(self, safety_manager, data_store, setpoints):
        # Low temp
        data_store.write("AI_METER_TEMP", setpoints.temp_lo_alarm_f - 5)
        safety_manager.execute()
        tags = [a.definition.tag for a in safety_manager.get_active_alarms()]
        assert "ALM_TEMP_LO" in tags

    def test_temperature_delta_alarm(self, safety_manager, data_store, setpoints):
        data_store.write("AI_METER_TEMP", 80.0)
        data_store.write("AI_TEST_THERMO", 80.0 + setpoints.temp_max_delta_f + 1)
        safety_manager.execute()
        tags = [a.definition.tag for a in safety_manager.get_active_alarms()]
        assert "ALM_TEMP_DELTA" in tags

    def test_strainer_dp_alarm(self, safety_manager, data_store, setpoints):
        data_store.write("AI_STRAINER_DP", setpoints.strainer_dp_hi_psi + 5)
        safety_manager.execute()
        tags = [a.definition.tag for a in safety_manager.get_active_alarms()]
        assert "ALM_STRAINER_DP_HI" in tags

    def test_sample_pot_full_alarm(self, safety_manager, data_store):
        data_store.write("DI_SAMPLE_POT_HI", True)
        safety_manager.execute()
        tags = [a.definition.tag for a in safety_manager.get_active_alarms()]
        assert "ALM_SAMPLE_POT_FULL" in tags

    def test_gas_detected_alarm(self, safety_manager, data_store):
        data_store.write("DI_AIR_ELIM_FLOAT", True)
        safety_manager.execute()
        tags = [a.definition.tag for a in safety_manager.get_active_alarms()]
        assert "ALM_GAS_DETECTED" in tags

    def test_acknowledge_all(self, safety_manager, data_store):
        data_store.write("DI_ESTOP", True)
        data_store.write("DI_PUMP_OVERLOAD", True)
        safety_manager.execute()
        assert len(safety_manager.get_unacknowledged_alarms()) >= 2

        safety_manager.acknowledge_all()
        assert len(safety_manager.get_unacknowledged_alarms()) == 0

    def test_alarm_beacon_on_unack(self, safety_manager, data_store):
        data_store.write("DI_ESTOP", True)
        safety_manager.execute()
        assert data_store.read("DO_ALARM_BEACON") is True

    def test_horn_silence(self, safety_manager, data_store):
        data_store.write("DI_ESTOP", True)
        safety_manager.execute()
        assert data_store.read("DO_ALARM_HORN") is True

        safety_manager.silence_horn()
        safety_manager.execute()
        assert data_store.read("DO_ALARM_HORN") is False

    def test_alarm_summary_updates(self, safety_manager, data_store):
        data_store.write("DI_ESTOP", True)
        data_store.write("DI_PUMP_OVERLOAD", True)
        safety_manager.execute()
        assert data_store.read("ALARM_ACTIVE_COUNT") >= 2
        assert data_store.read("ALARM_UNACK_COUNT") >= 2
        assert data_store.read("HIGHEST_ALARM_PRI") >= AlarmPriority.CRITICAL
