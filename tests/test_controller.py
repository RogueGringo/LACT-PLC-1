"""
Tests for the main PLC Controller.
"""

import time
import pytest

from plc.core.controller import PLCController
from plc.core.state_machine import LACTState
from plc.drivers.simulator import HardwareSimulator
from plc.drivers.io_handler import IOHandler


class TestPLCController:
    """Integration tests for the PLC scan loop."""

    def test_controller_creation(self, controller):
        assert controller.state_machine.state == LACTState.IDLE
        assert controller.scan_count == 0

    def test_single_scan(self, controller):
        controller.single_scan()
        assert controller.scan_count == 1

    def test_multiple_scans(self, controller):
        for _ in range(10):
            controller.single_scan()
        assert controller.scan_count == 10

    def test_status_report(self, controller):
        controller.single_scan()
        status = controller.get_status()
        assert "state" in status
        assert "flow_rate_bph" in status
        assert "bsw_pct" in status

    def test_cmd_start(self, controller):
        result = controller.cmd_start()
        assert "Start" in result
        controller.single_scan()
        assert controller.state_machine.state == LACTState.STARTUP

    def test_cmd_start_when_not_idle(self, controller):
        controller.cmd_start()
        controller.single_scan()
        result = controller.cmd_start()
        assert "Cannot" in result

    def test_cmd_stop(self, controller):
        # Get into running-ish state first
        controller.state_machine.state = LACTState.RUNNING
        controller.state_machine._state_entry_time = time.time()
        result = controller.cmd_stop()
        assert "Shutdown" in result

    def test_cmd_estop(self, controller):
        result = controller.cmd_estop()
        assert "EMERGENCY" in result
        assert controller.ds.read("DI_ESTOP") is True

    def test_cmd_estop_reset(self, controller):
        controller.cmd_estop()
        result = controller.cmd_estop_reset()
        assert "reset" in result
        assert controller.ds.read("DI_ESTOP") is False

    def test_cmd_ack_alarms(self, controller):
        result = controller.cmd_ack_alarms()
        assert "acknowledged" in result

    def test_cmd_update_setpoint(self, controller):
        result = controller.cmd_update_setpoint("bsw_divert_pct", 0.8)
        assert "updated" in result
        assert controller.sp.bsw_divert_pct == 0.8

    def test_cmd_update_invalid_setpoint(self, controller):
        result = controller.cmd_update_setpoint("nonexistent", 42)
        assert "Invalid" in result

    def test_background_start_stop(self, controller):
        controller.start(blocking=False)
        time.sleep(0.3)
        assert controller.is_running
        assert controller.scan_count > 0

        controller.stop()
        assert not controller.is_running

    def test_safe_state_on_stop(self, controller):
        controller.ds.write("DO_PUMP_START", True)
        controller.stop()
        assert controller.ds.read("DO_PUMP_START") is False

    def test_io_reads_during_scan(self, controller, simulator):
        # Simulator has inlet valve open by default
        controller.single_scan()
        assert controller.ds.read("DI_INLET_VLV_OPEN") is True

    def test_simulator_bsw_override(self, controller, simulator):
        simulator.set_bsw(2.5)
        controller.single_scan()
        bsw = controller.ds.read("AI_BSW_PROBE")
        assert bsw > 2.0  # Approximate due to noise

    def test_prove_command_requires_running(self, controller):
        result = controller.cmd_prove()
        assert "must be RUNNING" in result
