"""
Scenario-based integration tests for LACT operational sequences.

These exercise the full control stack (controller + state machine +
safety + modules + simulator) through realistic multi-step sequences.
Each test uses the ScenarioRunner with fast setpoints, so wall-clock
startup takes ~10-12 seconds per scenario.
"""

import pytest

from plc.core.state_machine import LACTState
from plc.testing import ScenarioRunner, fast_setpoints


class TestOperationalScenarios:
    """End-to-end operational sequences."""

    @pytest.fixture
    def runner(self):
        return ScenarioRunner()

    def test_normal_operation_cycle(self, runner):
        """Start → RUNNING → steady state → Shutdown → IDLE."""
        runner.start_unit()
        runner.assert_state(LACTState.RUNNING)
        runner.run_scans(100)
        runner.assert_state(LACTState.RUNNING)
        runner.assert_output("DO_PUMP_START", True)
        runner.assert_output("DO_STATUS_GREEN", True)
        runner.shutdown()
        runner.assert_state(LACTState.IDLE)
        runner.assert_output("DO_PUMP_START", False)

    def test_bsw_divert_and_recovery(self, runner):
        """High BSW triggers divert; clearing BSW recovers to RUNNING."""
        runner.start_unit()
        runner.assert_state(LACTState.RUNNING)

        # Inject high BSW → should divert
        runner.inject("bsw", 1.5)
        runner.run_scans(10)
        runner.assert_state(LACTState.DIVERT)
        runner.assert_alarm_active("ALM_BSW_DIVERT")
        runner.assert_output("DO_DIVERT_CMD", True)

        # Clear BSW → should recover
        runner.inject("bsw", 0.3)
        runner.run_scans(30)
        runner.assert_state(LACTState.RUNNING)

        runner.shutdown()
        runner.assert_state(LACTState.IDLE)

    def test_estop_from_running(self, runner):
        """E-Stop halts all outputs; release returns to IDLE."""
        runner.start_unit()
        runner.assert_state(LACTState.RUNNING)

        runner.estop()
        runner.assert_state(LACTState.E_STOP)
        runner.assert_output("DO_PUMP_START", False)
        runner.assert_output("DO_DIVERT_CMD", True)
        runner.assert_output("DO_STATUS_GREEN", False)

        runner.estop_reset()
        runner.assert_state(LACTState.IDLE)

    def test_pump_overload_during_operation(self, runner):
        """Pump overload triggers alarm and shutdown."""
        runner.start_unit()
        runner.assert_state(LACTState.RUNNING)

        runner.inject("pump_overload", 1)
        runner.run_scans(10)
        runner.assert_alarm_active("ALM_PUMP_OVERLOAD")

    def test_high_temperature_alarm(self):
        """Temperature above setpoint triggers alarm.

        The simulator clamps temperature to [40, 120], so we lower the
        alarm setpoint to 100 to make the alarm reachable in simulation.
        """
        r = ScenarioRunner(setpoints=fast_setpoints(temp_hi_alarm_f=100.0))
        r.start_unit()
        r.assert_state(LACTState.RUNNING)

        r.inject("temperature", 115.0)
        r.run_scans(5)
        r.assert_alarm_active("ALM_TEMP_HI")

        # Clear condition + acknowledge (alarm is latching)
        r.inject("temperature", 85.0)
        r.controller.cmd_ack_alarms()
        r.run_scans(5)
        r.assert_alarm_clear("ALM_TEMP_HI")

    def test_multiple_fault_sequence(self):
        """Multiple faults in sequence: BSW divert → clear → temp alarm → clear."""
        r = ScenarioRunner(setpoints=fast_setpoints(temp_hi_alarm_f=100.0))
        r.start_unit()

        # Fault 1: BSW divert
        r.inject("bsw", 1.5)
        r.run_scans(10)
        r.assert_state(LACTState.DIVERT)

        # Clear fault 1
        r.inject("bsw", 0.3)
        r.run_scans(30)
        r.assert_state(LACTState.RUNNING)

        # Fault 2: temperature (115 > lowered setpoint of 100)
        r.inject("temperature", 115.0)
        r.run_scans(5)
        r.assert_alarm_active("ALM_TEMP_HI")

        # Clear fault 2 + acknowledge (alarm is latching)
        r.inject("temperature", 85.0)
        r.controller.cmd_ack_alarms()
        r.run_scans(5)
        r.assert_alarm_clear("ALM_TEMP_HI")

        r.shutdown()
        r.assert_state(LACTState.IDLE)

    def test_snapshot_during_operation(self, runner):
        """Snapshot returns meaningful data while running."""
        runner.start_unit()
        runner.run_scans(50)

        snap = runner.snapshot()
        assert snap["state"] == "RUNNING"
        assert snap["scan_count"] > 0
        assert isinstance(snap["bsw_pct"], (int, float))
        assert isinstance(snap["flow_rate_bph"], (int, float))

    def test_start_from_non_idle_fails(self, runner):
        """Starting when not IDLE raises ScenarioError."""
        runner.start_unit()
        from plc.testing.scenario_runner import ScenarioError
        with pytest.raises(ScenarioError, match="Start failed"):
            runner.start_unit()
