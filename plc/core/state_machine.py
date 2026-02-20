"""
LACT Unit State Machine
========================
Governs the operational states of the custody transfer process.

State Diagram:

    IDLE ──► STARTUP ──► RUNNING ──► SHUTDOWN ──► IDLE
                │            │
                │            ├──► DIVERT ──► RUNNING
                │            │
                │            └──► PROVING ──► RUNNING
                │
                └──► IDLE (on failure)

    Any State ──► E_STOP (emergency)
    E_STOP   ──► IDLE   (after reset)
"""

from enum import Enum
import time
import logging

from plc.core.data_store import DataStore
from plc.config.setpoints import Setpoints

logger = logging.getLogger(__name__)


class LACTState(Enum):
    IDLE = "IDLE"
    STARTUP = "STARTUP"
    RUNNING = "RUNNING"
    DIVERT = "DIVERT"
    PROVING = "PROVING"
    SHUTDOWN = "SHUTDOWN"
    E_STOP = "E_STOP"


# Permitted transitions
_TRANSITIONS = {
    LACTState.IDLE:     [LACTState.STARTUP, LACTState.E_STOP],
    LACTState.STARTUP:  [LACTState.RUNNING, LACTState.IDLE, LACTState.E_STOP],
    LACTState.RUNNING:  [LACTState.DIVERT, LACTState.PROVING,
                         LACTState.SHUTDOWN, LACTState.E_STOP],
    LACTState.DIVERT:   [LACTState.RUNNING, LACTState.SHUTDOWN, LACTState.E_STOP],
    LACTState.PROVING:  [LACTState.RUNNING, LACTState.SHUTDOWN, LACTState.E_STOP],
    LACTState.SHUTDOWN: [LACTState.IDLE, LACTState.E_STOP],
    LACTState.E_STOP:   [LACTState.IDLE],
}


class LACTStateMachine:
    """
    Manages LACT operational state transitions.

    Enforces legal transitions and runs entry/exit logic for each
    state. The main PLC scan loop calls `execute()` every cycle,
    which dispatches to the handler for the current state.
    """

    def __init__(self, data_store: DataStore, setpoints: Setpoints):
        self.ds = data_store
        self.sp = setpoints
        self.state = LACTState.IDLE
        self._state_entry_time = time.time()
        self._startup_step = 0
        self._shutdown_step = 0
        self._request_state: LACTState = None

    @property
    def time_in_state(self) -> float:
        return time.time() - self._state_entry_time

    def request_transition(self, target: LACTState):
        """Request a state change (validated on next scan)."""
        self._request_state = target

    def _transition(self, target: LACTState) -> bool:
        """Execute a validated state transition."""
        if target not in _TRANSITIONS.get(self.state, []):
            logger.warning(
                "Illegal transition %s -> %s", self.state.value, target.value
            )
            return False

        prev = self.state
        logger.info("State transition: %s -> %s", prev.value, target.value)
        self.ds.write("PREV_STATE", prev.value)

        self.state = target
        self._state_entry_time = time.time()
        self._startup_step = 0
        self._shutdown_step = 0

        self.ds.write("LACT_STATE", target.value)
        return True

    def execute(self):
        """
        Run one scan cycle of the state machine.
        Called by PLCController on every scan.
        """
        # Handle pending transition request
        transitioned = False
        if self._request_state is not None:
            transitioned = self._transition(self._request_state)
            self._request_state = None

        # E-Stop override from any state
        if self.ds.read("DI_ESTOP") and self.state != LACTState.E_STOP:
            transitioned = self._transition(LACTState.E_STOP)

        # Skip handler on the scan where we just transitioned,
        # so the new state begins executing on the next scan.
        if transitioned:
            return

        # Dispatch to state handler
        handler = {
            LACTState.IDLE: self._handle_idle,
            LACTState.STARTUP: self._handle_startup,
            LACTState.RUNNING: self._handle_running,
            LACTState.DIVERT: self._handle_divert,
            LACTState.PROVING: self._handle_proving,
            LACTState.SHUTDOWN: self._handle_shutdown,
            LACTState.E_STOP: self._handle_estop,
        }.get(self.state)

        if handler:
            handler()

    # ── State Handlers ───────────────────────────────────────

    def _handle_idle(self):
        """IDLE: All outputs off, waiting for start command."""
        self.ds.write("DO_PUMP_START", False)
        self.ds.write("DO_SAMPLE_SOL", False)
        self.ds.write("DO_SAMPLE_MIX_PUMP", False)
        self.ds.write("DO_STATUS_GREEN", False)

    def _handle_startup(self):
        """
        STARTUP: Sequential pre-checks and valve alignment.

        Step 0: Verify inlet/outlet valves open
        Step 1: Set divert valve to DIVERT (safe position)
        Step 2: Verify divert valve position
        Step 3: Start transfer pump
        Step 4: Verify pump running, wait for flow stabilization
        Step 5: Check BS&W, if OK switch divert to SALES → RUNNING
        """
        if self._startup_step == 0:
            # Verify valve alignment
            inlet_open = self.ds.read("DI_INLET_VLV_OPEN")
            outlet_open = self.ds.read("DI_OUTLET_VLV_OPEN")
            if not inlet_open or not outlet_open:
                logger.warning("Startup aborted: valves not aligned")
                self._transition(LACTState.IDLE)
                return
            self._startup_step = 1

        elif self._startup_step == 1:
            # Command divert to DIVERT position (safe start)
            self.ds.write("DO_DIVERT_CMD", True)
            self._startup_step = 2

        elif self._startup_step == 2:
            # Wait for divert valve confirmation
            if self.ds.read("DI_DIVERT_DIVERT"):
                self._startup_step = 3
            elif self.time_in_state > self.sp.divert_travel_timeout_sec:
                logger.error("Startup aborted: divert valve timeout")
                self._transition(LACTState.IDLE)

        elif self._startup_step == 3:
            # Start pump after valve alignment delay
            if self.time_in_state > self.sp.pump_start_delay_sec:
                self.ds.write("DO_PUMP_START", True)
                self._startup_step = 4

        elif self._startup_step == 4:
            # Verify pump is running
            if self.ds.read("DI_PUMP_RUNNING"):
                self._startup_step = 5
            elif self.time_in_state > self.sp.pump_start_delay_sec + 10.0:
                logger.error("Startup aborted: pump failed to start")
                self.ds.write("DO_PUMP_START", False)
                self._transition(LACTState.IDLE)

        elif self._startup_step == 5:
            # Wait for BS&W stabilization then switch to sales
            if self.time_in_state > (self.sp.pump_start_delay_sec +
                                     self.sp.bsw_sample_delay_sec + 10.0):
                bsw = self.ds.read("AI_BSW_PROBE")
                if bsw < self.sp.bsw_divert_pct:
                    self.ds.write("DO_DIVERT_CMD", False)  # Switch to SALES
                    self.ds.write("DO_STATUS_GREEN", True)
                    self.ds.write("BATCH_START_TIME", time.time())
                    self._transition(LACTState.RUNNING)
                else:
                    logger.warning("Startup: BS&W too high (%.2f%%), staying diverted", bsw)
                    self._transition(LACTState.DIVERT)

    def _handle_running(self):
        """RUNNING: Normal custody transfer operation."""
        self.ds.write("DO_STATUS_GREEN", True)

        # Update batch elapsed time
        batch_start = self.ds.read("BATCH_START_TIME")
        if batch_start:
            self.ds.write("BATCH_ELAPSED_SEC", time.time() - batch_start)

    def _handle_divert(self):
        """DIVERT: Flow diverted due to BS&W or other condition."""
        self.ds.write("DO_DIVERT_CMD", True)
        self.ds.write("DO_STATUS_GREEN", False)

        # Check if BS&W has cleared
        bsw = self.ds.read("AI_BSW_PROBE")
        if bsw < self.sp.bsw_divert_pct:
            if self.time_in_state > self.sp.bsw_divert_delay_sec:
                self.ds.write("DO_DIVERT_CMD", False)
                self._transition(LACTState.RUNNING)

    def _handle_proving(self):
        """PROVING: Meter proving in progress (managed by ProvingManager)."""
        # ProvingManager module handles proving logic
        # This state just keeps the pump running and sampler paused
        self.ds.write("DO_STATUS_GREEN", True)

    def _handle_shutdown(self):
        """
        SHUTDOWN: Orderly process shutdown.

        Step 0: Switch divert valve to DIVERT
        Step 1: Stop sampler
        Step 2: Stop pump
        Step 3: Confirm pump stopped → IDLE
        """
        if self._shutdown_step == 0:
            self.ds.write("DO_DIVERT_CMD", True)
            self.ds.write("DO_SAMPLE_SOL", False)
            self.ds.write("DO_SAMPLE_MIX_PUMP", False)
            self._shutdown_step = 1

        elif self._shutdown_step == 1:
            if self.time_in_state > self.sp.pump_stop_delay_sec:
                self.ds.write("DO_PUMP_START", False)
                self._shutdown_step = 2

        elif self._shutdown_step == 2:
            if not self.ds.read("DI_PUMP_RUNNING"):
                self.ds.write("DO_STATUS_GREEN", False)
                self._transition(LACTState.IDLE)
            elif self.time_in_state > self.sp.pump_stop_delay_sec + 15.0:
                # Pump didn't stop — force to idle anyway
                logger.error("Pump did not confirm stop during shutdown")
                self.ds.write("DO_STATUS_GREEN", False)
                self._transition(LACTState.IDLE)

    def _handle_estop(self):
        """E_STOP: Immediate halt of all outputs."""
        self.ds.write("DO_PUMP_START", False)
        self.ds.write("DO_DIVERT_CMD", True)  # Divert for safety
        self.ds.write("DO_SAMPLE_SOL", False)
        self.ds.write("DO_SAMPLE_MIX_PUMP", False)
        self.ds.write("DO_PROVER_VLV_CMD", False)
        self.ds.write("DO_STATUS_GREEN", False)
        self.ds.write("DO_ALARM_BEACON", True)
        self.ds.write("DO_ALARM_HORN", True)

        # Reset only when E-STOP is released
        if not self.ds.read("DI_ESTOP"):
            if self.time_in_state > 2.0:  # Debounce
                self._transition(LACTState.IDLE)
