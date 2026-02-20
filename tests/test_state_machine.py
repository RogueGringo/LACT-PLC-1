"""
Tests for the LACT State Machine.
"""

import time
import pytest

from plc.core.state_machine import LACTStateMachine, LACTState
from plc.core.data_store import DataStore
from plc.config.setpoints import Setpoints


class TestLACTStateMachine:
    """Test state transitions and state handler behavior."""

    def test_initial_state_is_idle(self, state_machine):
        assert state_machine.state == LACTState.IDLE

    def test_idle_to_startup_transition(self, state_machine, data_store):
        state_machine.request_transition(LACTState.STARTUP)
        state_machine.execute()  # Transitions (handler skipped)
        assert state_machine.state == LACTState.STARTUP

    def test_idle_to_running_is_illegal(self, state_machine):
        state_machine.request_transition(LACTState.RUNNING)
        state_machine.execute()
        # Should remain IDLE because IDLE->RUNNING is not allowed
        assert state_machine.state == LACTState.IDLE

    def test_estop_from_any_state(self, state_machine, data_store):
        # Go to STARTUP first
        state_machine.request_transition(LACTState.STARTUP)
        state_machine.execute()  # Transitions to STARTUP
        assert state_machine.state == LACTState.STARTUP

        # E-Stop should override
        data_store.write("DI_ESTOP", True)
        state_machine.execute()  # Transitions to E_STOP
        assert state_machine.state == LACTState.E_STOP

    def test_estop_clears_all_outputs(self, state_machine, data_store):
        data_store.write("DI_ESTOP", True)
        state_machine.request_transition(LACTState.E_STOP)
        state_machine.execute()  # Transitions
        state_machine.execute()  # Runs E_STOP handler
        # E-stop handler should clear pump
        assert data_store.read("DO_PUMP_START") is False
        assert data_store.read("DO_SAMPLE_SOL") is False

    def test_estop_recovery_to_idle(self, state_machine, data_store):
        # Enter E-Stop
        data_store.write("DI_ESTOP", True)
        state_machine.request_transition(LACTState.STARTUP)
        state_machine.execute()  # Goes to STARTUP, then E-Stop override
        # E-Stop check happens after transition, so state should be E_STOP
        # Since DI_ESTOP is True, the E-Stop override fires
        # The transition goes: request STARTUP → transition to STARTUP → skip handler
        # But E-Stop is checked too... let me just force E_STOP state
        state_machine.state = LACTState.E_STOP
        state_machine._state_entry_time = time.time() - 3.0

        # Release E-Stop
        data_store.write("DI_ESTOP", False)
        state_machine.execute()  # Runs handler, transitions to IDLE
        # After transition, one more execute to confirm
        state_machine.execute()
        assert state_machine.state == LACTState.IDLE

    def test_startup_aborts_without_valves(self, state_machine, data_store):
        # Valves are closed (default False)
        state_machine.request_transition(LACTState.STARTUP)
        state_machine.execute()  # Transition (handler skipped)
        assert state_machine.state == LACTState.STARTUP

        # Next scan: startup checks valves and aborts
        state_machine.execute()  # Handler runs, valves not open → IDLE
        # Transition back to IDLE (handler skipped), next scan confirms
        state_machine.execute()
        assert state_machine.state == LACTState.IDLE

    def test_idle_handler_clears_outputs(self, state_machine, data_store):
        data_store.write("DO_PUMP_START", True)
        data_store.write("DO_STATUS_GREEN", True)
        state_machine.execute()  # In IDLE state, handler runs
        assert data_store.read("DO_PUMP_START") is False
        assert data_store.read("DO_STATUS_GREEN") is False

    def test_state_writes_to_datastore(self, state_machine, data_store):
        assert data_store.read("LACT_STATE") == "IDLE"
        state_machine.request_transition(LACTState.STARTUP)
        state_machine.execute()  # Transition writes to DS
        assert data_store.read("LACT_STATE") == "STARTUP"

    def test_running_to_divert_transition(self, data_store, setpoints):
        sm = LACTStateMachine(data_store, setpoints)
        sm.state = LACTState.RUNNING
        sm._state_entry_time = time.time()

        sm.request_transition(LACTState.DIVERT)
        sm.execute()
        assert sm.state == LACTState.DIVERT

    def test_running_to_proving_transition(self, data_store, setpoints):
        sm = LACTStateMachine(data_store, setpoints)
        sm.state = LACTState.RUNNING
        sm._state_entry_time = time.time()

        sm.request_transition(LACTState.PROVING)
        sm.execute()
        assert sm.state == LACTState.PROVING

    def test_divert_clears_when_bsw_drops(self, data_store, setpoints):
        sm = LACTStateMachine(data_store, setpoints)
        sm.state = LACTState.DIVERT
        sm._state_entry_time = time.time() - 10.0  # Well past delay

        data_store.write("AI_BSW_PROBE", 0.1)  # Below divert setpoint
        sm.execute()  # Handler runs, transitions to RUNNING
        assert sm.state == LACTState.RUNNING

    def test_shutdown_sequence(self, data_store, setpoints):
        sm = LACTStateMachine(data_store, setpoints)
        sm.state = LACTState.RUNNING
        sm._state_entry_time = time.time()

        # Request shutdown
        sm.request_transition(LACTState.SHUTDOWN)
        sm.execute()  # Transitions (handler skipped)
        assert sm.state == LACTState.SHUTDOWN

        # Step 0: divert command issued
        sm.execute()  # Handler runs step 0
        assert data_store.read("DO_DIVERT_CMD") is True

        # Step 1->2: pump stops after delay
        sm._state_entry_time = time.time() - 10.0
        data_store.write("DI_PUMP_RUNNING", False)
        sm.execute()  # Step 1 -> step 2 (pump off)
        sm.execute()  # Step 2 -> transition to IDLE
        sm.execute()  # Confirm IDLE
        assert sm.state == LACTState.IDLE
