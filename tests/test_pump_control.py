"""
Tests for the Transfer Pump Control module.
"""

import time
import pytest

from plc.modules.pump_control import PumpControl
from plc.core.data_store import DataStore
from plc.config.setpoints import Setpoints


class TestPumpControl:
    """Test pump motor protection and control logic."""

    @pytest.fixture
    def pump(self, data_store, setpoints):
        return PumpControl(data_store, setpoints)

    def test_initial_state(self, pump):
        assert not pump.is_running
        assert not pump.is_locked_out

    def test_overload_stops_pump(self, pump, data_store):
        data_store.write("DO_PUMP_START", True)
        data_store.write("DI_PUMP_OVERLOAD", True)
        pump.execute()
        assert data_store.read("DO_PUMP_START") is False
        assert pump.is_locked_out

    def test_lockout_prevents_restart(self, pump, data_store, setpoints):
        setpoints.pump_restart_lockout_sec = 30.0
        data_store.write("DO_PUMP_START", True)
        data_store.write("DI_PUMP_OVERLOAD", True)
        pump.execute()

        # Clear overload but try to restart
        data_store.write("DI_PUMP_OVERLOAD", False)
        data_store.write("DO_PUMP_START", True)
        pump.execute()
        # Should still be off during lockout
        assert data_store.read("DO_PUMP_START") is False

    def test_lockout_expires(self, pump, data_store, setpoints):
        setpoints.pump_restart_lockout_sec = 0.0  # Immediate expiry
        data_store.write("DO_PUMP_START", True)
        data_store.write("DI_PUMP_OVERLOAD", True)
        pump.execute()

        data_store.write("DI_PUMP_OVERLOAD", False)
        pump._last_trip_time = time.time() - 1.0
        pump.execute()
        assert not pump.is_locked_out

    def test_max_starts_protection(self, pump, setpoints):
        setpoints.pump_max_starts_per_hour = 4
        assert pump.record_start()  # 1st: count=1 < 4, OK
        assert pump.record_start()  # 2nd: count=2 < 4, OK
        assert pump.record_start()  # 3rd: count=3 < 4, OK
        assert not pump.record_start()  # 4th: count=4 >= 4, BLOCKED

    def test_starts_this_hour(self, pump):
        pump.record_start()
        pump.record_start()
        assert pump.starts_this_hour == 2

    def test_running_status(self, pump, data_store):
        assert not pump.is_running
        data_store.write("DI_PUMP_RUNNING", True)
        assert pump.is_running
