"""
PLC Controller — Main Scan Loop
================================
Orchestrates the entire control system. Each scan cycle:

    1. Read physical I/O into DataStore
    2. Execute safety interlocks
    3. Execute state machine
    4. Execute process modules
    5. Write DataStore outputs to physical I/O
    6. Log / communicate

Designed for deterministic cycle times on a Linux SBC
(Raspberry Pi 4/5 or equivalent).
"""

import time
import logging
import signal
import threading
from typing import Optional

from plc.config.io_map import IOMap
from plc.config.setpoints import Setpoints
from plc.config.alarms import AlarmConfig
from plc.core.data_store import DataStore
from plc.core.state_machine import LACTStateMachine, LACTState
from plc.core.safety import SafetyManager
from plc.drivers.io_handler import IOHandler
from plc.modules.flow_measurement import FlowMeasurement
from plc.modules.bsw_monitor import BSWMonitor
from plc.modules.sampler import Sampler
from plc.modules.divert_valve import DivertValve
from plc.modules.pump_control import PumpControl
from plc.modules.proving import ProvingManager
from plc.modules.pressure_monitor import PressureMonitor
from plc.modules.temperature import TemperatureMonitor

logger = logging.getLogger(__name__)


class PLCController:
    """
    Main PLC controller.

    Runs the deterministic scan loop that coordinates all
    subsystems: I/O, safety, state machine, and process modules.
    """

    def __init__(
        self,
        io_handler: IOHandler,
        io_map: Optional[IOMap] = None,
        setpoints: Optional[Setpoints] = None,
        alarm_config: Optional[AlarmConfig] = None,
    ):
        self.io_map = io_map or IOMap()
        self.sp = setpoints or Setpoints()
        self.alarm_config = alarm_config or AlarmConfig()

        # Core components
        self.ds = DataStore()
        self.io = io_handler
        self.safety = SafetyManager(self.ds, self.sp, self.alarm_config)
        self.state_machine = LACTStateMachine(self.ds, self.sp)

        # Process modules
        self.flow = FlowMeasurement(self.ds, self.sp)
        self.bsw = BSWMonitor(self.ds, self.sp)
        self.sampler = Sampler(self.ds, self.sp)
        self.divert = DivertValve(self.ds, self.sp)
        self.pump = PumpControl(self.ds, self.sp)
        self.proving = ProvingManager(self.ds, self.sp)
        self.pressure = PressureMonitor(self.ds, self.sp)
        self.temperature = TemperatureMonitor(self.ds, self.sp)

        # Runtime state
        self._running = False
        self._scan_count = 0
        self._scan_time_ms = 0.0
        self._max_scan_time_ms = 0.0
        self._thread: Optional[threading.Thread] = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def scan_count(self) -> int:
        return self._scan_count

    @property
    def scan_time_ms(self) -> float:
        return self._scan_time_ms

    @property
    def max_scan_time_ms(self) -> float:
        return self._max_scan_time_ms

    def start(self, blocking: bool = True):
        """Start the PLC scan loop."""
        self._running = True
        logger.info(
            "PLC Controller starting (scan rate: %d ms)",
            self.sp.scan_rate_ms,
        )

        if blocking:
            self._scan_loop()
        else:
            self._thread = threading.Thread(
                target=self._scan_loop, daemon=True
            )
            self._thread.start()

    def stop(self):
        """Stop the PLC scan loop gracefully."""
        logger.info("PLC Controller stopping...")
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
        # Force all outputs off
        self._safe_state()
        logger.info("PLC Controller stopped. Total scans: %d", self._scan_count)

    def single_scan(self):
        """Execute exactly one scan cycle (for testing)."""
        self._execute_scan()

    def _scan_loop(self):
        """Main deterministic scan loop."""
        cycle_sec = self.sp.scan_rate_ms / 1000.0

        while self._running:
            t_start = time.monotonic()

            try:
                self._execute_scan()
            except Exception:
                logger.exception("Scan cycle exception")
                self._safe_state()

            # Maintain cycle time
            elapsed = time.monotonic() - t_start
            self._scan_time_ms = elapsed * 1000.0
            self._max_scan_time_ms = max(self._max_scan_time_ms, self._scan_time_ms)

            sleep_time = cycle_sec - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                logger.warning(
                    "Scan overrun: %.1f ms (target: %d ms)",
                    self._scan_time_ms, self.sp.scan_rate_ms,
                )

        self._safe_state()

    def _execute_scan(self):
        """One complete scan cycle."""
        self._scan_count += 1

        # Phase 1: Read all physical inputs
        self.io.read_inputs(self.ds, self.io_map)

        # Phase 2: Safety interlocks (always runs first)
        self.safety.execute()

        # Phase 3: Handle safety actions
        if self.safety.shutdown_requested:
            current = self.state_machine.state
            if current not in (LACTState.E_STOP, LACTState.SHUTDOWN, LACTState.IDLE):
                self.state_machine.request_transition(LACTState.SHUTDOWN)
        elif self.safety.divert_requested:
            if self.state_machine.state == LACTState.RUNNING:
                self.state_machine.request_transition(LACTState.DIVERT)

        # Phase 4: State machine
        self.state_machine.execute()

        # Phase 5: Process modules
        current_state = self.state_machine.state
        self.pressure.execute()
        self.temperature.execute()
        self.flow.execute()
        self.bsw.execute()

        if current_state in (LACTState.RUNNING, LACTState.DIVERT):
            self.sampler.execute(current_state)

        if current_state == LACTState.PROVING:
            self.proving.execute()

        self.divert.execute()
        self.pump.execute()

        # Phase 6: Write outputs to physical I/O
        self.io.write_outputs(self.ds, self.io_map)

    def _safe_state(self):
        """Force all outputs to safe state."""
        self.ds.write("DO_PUMP_START", False)
        self.ds.write("DO_DIVERT_CMD", True)  # Divert = safe
        self.ds.write("DO_SAMPLE_SOL", False)
        self.ds.write("DO_SAMPLE_MIX_PUMP", False)
        self.ds.write("DO_PROVER_VLV_CMD", False)
        self.ds.write("DO_ALARM_BEACON", False)
        self.ds.write("DO_ALARM_HORN", False)
        self.ds.write("DO_STATUS_GREEN", False)
        try:
            self.io.write_outputs(self.ds, self.io_map)
        except Exception:
            logger.exception("Failed to write safe state to I/O")

    # ── Operator Commands ────────────────────────────────────

    def cmd_start(self) -> str:
        """Operator: Start the LACT unit."""
        if self.state_machine.state != LACTState.IDLE:
            return f"Cannot start: currently in {self.state_machine.state.value}"
        self.state_machine.request_transition(LACTState.STARTUP)
        return "Start command issued"

    def cmd_stop(self) -> str:
        """Operator: Normal shutdown."""
        state = self.state_machine.state
        if state in (LACTState.IDLE, LACTState.SHUTDOWN, LACTState.E_STOP):
            return f"Already in {state.value}"
        self.state_machine.request_transition(LACTState.SHUTDOWN)
        return "Shutdown command issued"

    def cmd_estop(self) -> str:
        """Operator: Emergency stop."""
        self.ds.write("DI_ESTOP", True)
        return "EMERGENCY STOP activated"

    def cmd_estop_reset(self) -> str:
        """Operator: Reset E-Stop."""
        self.ds.write("DI_ESTOP", False)
        return "E-STOP reset"

    def cmd_prove(self) -> str:
        """Operator: Initiate meter proving."""
        if self.state_machine.state != LACTState.RUNNING:
            return "Cannot prove: unit must be RUNNING"
        self.proving.start_proving()
        self.state_machine.request_transition(LACTState.PROVING)
        return "Proving initiated"

    def cmd_ack_alarms(self) -> str:
        """Operator: Acknowledge all alarms."""
        self.safety.acknowledge_all()
        return "All alarms acknowledged"

    def cmd_silence_horn(self) -> str:
        """Operator: Silence alarm horn."""
        self.safety.silence_horn()
        return "Horn silenced"

    def cmd_update_setpoint(self, key: str, value) -> str:
        """Operator: Update a process setpoint."""
        if self.sp.update(key, value):
            return f"Setpoint {key} updated to {value}"
        return f"Invalid setpoint: {key}"

    def cmd_save_setpoints(self, path: str = None) -> str:
        """Persist setpoints to disk."""
        self.sp.save(path)
        return "Setpoints saved"

    def get_status(self) -> dict:
        """Return comprehensive status snapshot."""
        return {
            "state": self.state_machine.state.value,
            "scan_count": self._scan_count,
            "scan_time_ms": round(self._scan_time_ms, 1),
            "max_scan_time_ms": round(self._max_scan_time_ms, 1),
            "flow_rate_bph": self.ds.read("FLOW_RATE_BPH"),
            "flow_total_bbl": self.ds.read("FLOW_TOTAL_BBL"),
            "bsw_pct": self.ds.read("BSW_PCT"),
            "meter_temp_f": self.ds.read("AI_METER_TEMP"),
            "inlet_press_psi": self.ds.read("AI_INLET_PRESS"),
            "outlet_press_psi": self.ds.read("AI_OUTLET_PRESS"),
            "meter_factor": self.ds.read("METER_FACTOR"),
            "batch_gross_bbl": self.ds.read("BATCH_GROSS_BBL"),
            "batch_net_bbl": self.ds.read("BATCH_NET_BBL"),
            "batch_elapsed_sec": self.ds.read("BATCH_ELAPSED_SEC"),
            "pump_running": self.ds.read("DI_PUMP_RUNNING"),
            "divert_active": self.ds.read("DO_DIVERT_CMD"),
            "active_alarms": len(self.safety.get_active_alarms()),
            "unack_alarms": len(self.safety.get_unacknowledged_alarms()),
        }
