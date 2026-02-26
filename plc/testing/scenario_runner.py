"""
Scenario Runner — Declarative PLC Integration Testing
=======================================================
Script multi-step operational sequences against the simulator
and assert expected behavior at each stage.

Usage::

    runner = ScenarioRunner()
    runner.start_unit()
    runner.run_scans(50)
    runner.inject("bsw", 1.5)
    runner.run_scans(10)
    runner.assert_state(LACTState.DIVERT)
    runner.inject("bsw", 0.3)
    runner.run_scans(50)
    runner.assert_state(LACTState.RUNNING)
    runner.shutdown()
"""

from __future__ import annotations

import time
from typing import Callable, Optional

from plc.config.io_map import IOMap
from plc.config.setpoints import Setpoints
from plc.config.alarms import AlarmConfig
from plc.core.controller import PLCController
from plc.core.state_machine import LACTState
from plc.drivers.io_handler import IOHandler
from plc.drivers.simulator import HardwareSimulator


class ScenarioError(Exception):
    """Raised when a scenario assertion fails."""


def fast_setpoints(**overrides) -> Setpoints:
    """Return setpoints tuned for fast test execution (~100x faster)."""
    sp = Setpoints(
        pump_start_delay_sec=0.05,
        pump_stop_delay_sec=0.05,
        pump_restart_lockout_sec=0.1,
        bsw_sample_delay_sec=0.05,
        bsw_divert_delay_sec=0.05,
        divert_travel_timeout_sec=2.0,
        divert_confirm_delay_sec=0.02,
        meter_no_flow_timeout_sec=1.0,
        scan_rate_ms=10,
    )
    for key, value in overrides.items():
        sp.update(key, value)
    return sp


class ScenarioRunner:
    """
    Drives a PLCController through scripted operational sequences.

    Creates its own controller + simulator stack so each scenario
    is fully isolated. All time-dependent logic in the simulator
    uses real wall-clock time, so ``run_scans`` calls
    ``time.sleep`` between scans to advance the simulation clock.

    By default, uses ``fast_setpoints()`` with shortened delays
    so scenarios complete in seconds, not minutes. Pass custom
    setpoints to override.
    """

    DEFAULT_MAX_SCANS = 1000  # Safety limit for start/stop waits

    def __init__(
        self,
        setpoints: Optional[Setpoints] = None,
        scan_sleep: float = 0.02,
    ):
        self.sp = setpoints or fast_setpoints()
        self.simulator = HardwareSimulator()
        self.io_handler = IOHandler(backend=self.simulator)
        self.controller = PLCController(
            io_handler=self.io_handler,
            io_map=IOMap(),
            setpoints=self.sp,
            alarm_config=AlarmConfig(),
        )
        self._scan_sleep = scan_sleep
        self._history: list[dict] = []

    # ── Core Execution ────────────────────────────────────────

    @property
    def state(self) -> LACTState:
        return self.controller.state_machine.state

    @property
    def scan_count(self) -> int:
        return self.controller.scan_count

    def run_scans(self, n: int) -> "ScenarioRunner":
        """Execute *n* scan cycles with inter-scan sleep for sim clock."""
        for _ in range(n):
            self.controller.single_scan()
            if self._scan_sleep > 0:
                time.sleep(self._scan_sleep)
        return self

    def run_until(
        self,
        predicate: Callable[["ScenarioRunner"], bool],
        max_scans: int = DEFAULT_MAX_SCANS,
        label: str = "condition",
    ) -> "ScenarioRunner":
        """Run scans until *predicate* returns True or *max_scans* exceeded."""
        for i in range(max_scans):
            self.controller.single_scan()
            if self._scan_sleep > 0:
                time.sleep(self._scan_sleep)
            if predicate(self):
                return self
        raise ScenarioError(
            f"Timed out waiting for {label} after {max_scans} scans "
            f"(state={self.state.value})"
        )

    # ── High-Level Operations ─────────────────────────────────

    def start_unit(self, max_scans: int = DEFAULT_MAX_SCANS) -> "ScenarioRunner":
        """Issue start command and run until RUNNING (or DIVERT)."""
        result = self.controller.cmd_start()
        if "Cannot" in result:
            raise ScenarioError(f"Start failed: {result}")
        self.run_until(
            lambda r: r.state in (LACTState.RUNNING, LACTState.DIVERT),
            max_scans=max_scans,
            label="RUNNING",
        )
        return self

    def shutdown(self, max_scans: int = DEFAULT_MAX_SCANS) -> "ScenarioRunner":
        """Issue stop command and run until IDLE."""
        result = self.controller.cmd_stop()
        if "Already" in result:
            return self
        self.run_until(
            lambda r: r.state == LACTState.IDLE,
            max_scans=max_scans,
            label="IDLE",
        )
        return self

    def estop(self) -> "ScenarioRunner":
        """Trigger E-Stop (drives both DataStore and simulator)."""
        self.simulator.set_estop(True)
        self.controller.cmd_estop()
        self.run_scans(2)
        return self

    def estop_reset(self, max_scans: int = DEFAULT_MAX_SCANS) -> "ScenarioRunner":
        """Release E-Stop and wait for IDLE."""
        self.controller.cmd_estop_reset()
        self.simulator.set_estop(False)
        self.run_until(
            lambda r: r.state == LACTState.IDLE,
            max_scans=max_scans,
            label="IDLE after E-Stop reset",
        )
        return self

    def prove(self, max_scans: int = DEFAULT_MAX_SCANS) -> "ScenarioRunner":
        """Initiate proving and wait for return to RUNNING."""
        result = self.controller.cmd_prove()
        if "Cannot" in result:
            raise ScenarioError(f"Prove failed: {result}")
        self.run_until(
            lambda r: r.state == LACTState.RUNNING,
            max_scans=max_scans,
            label="RUNNING after proving",
        )
        return self

    # ── Fault Injection ───────────────────────────────────────

    _INJECT_MAP = {
        "bsw": "set_bsw",
        "temperature": "set_temperature",
        "temp": "set_temperature",
        "inlet_pressure": "set_inlet_pressure",
        "pressure": "set_inlet_pressure",
    }

    _INJECT_DEFAULTS = {
        "bsw": 0.3,
        "temperature": 85.0,
        "temp": 85.0,
        "inlet_pressure": 45.0,
        "pressure": 45.0,
    }

    def inject(self, signal: str, value: float) -> "ScenarioRunner":
        """Inject a simulated process value."""
        if signal == "pump_overload":
            self.simulator.trigger_pump_overload()
            return self
        if signal == "estop":
            self.simulator.set_estop(bool(value))
            return self

        method_name = self._INJECT_MAP.get(signal)
        if method_name is None:
            raise ScenarioError(
                f"Unknown signal '{signal}'. "
                f"Valid: {list(self._INJECT_MAP.keys()) + ['pump_overload', 'estop']}"
            )
        getattr(self.simulator, method_name)(value)
        return self

    def clear(self, signal: str) -> "ScenarioRunner":
        """Reset an injected signal to its default value."""
        if signal == "pump_overload":
            self.simulator.clear_pump_overload()
            return self
        if signal == "estop":
            self.simulator.set_estop(False)
            return self

        default = self._INJECT_DEFAULTS.get(signal)
        if default is None:
            raise ScenarioError(f"Unknown signal '{signal}'")
        return self.inject(signal, default)

    # ── Assertions ────────────────────────────────────────────

    def assert_state(self, expected: LACTState) -> "ScenarioRunner":
        """Assert the current FSM state."""
        if self.state != expected:
            raise ScenarioError(
                f"Expected state {expected.value}, got {self.state.value} "
                f"(scan {self.scan_count})"
            )
        return self

    def assert_alarm_active(self, tag: str) -> "ScenarioRunner":
        """Assert that a specific alarm is currently active."""
        active_tags = {a.definition.tag for a in self.controller.safety.get_active_alarms()}
        if tag not in active_tags:
            raise ScenarioError(
                f"Alarm {tag} not active. Active: {active_tags or 'none'}"
            )
        return self

    def assert_alarm_clear(self, tag: str) -> "ScenarioRunner":
        """Assert that a specific alarm is NOT active."""
        active_tags = {a.definition.tag for a in self.controller.safety.get_active_alarms()}
        if tag in active_tags:
            raise ScenarioError(f"Alarm {tag} is still active")
        return self

    def assert_tag(
        self,
        tag: str,
        predicate: Callable,
        description: str = "",
    ) -> "ScenarioRunner":
        """Assert a DataStore tag value satisfies a predicate."""
        value = self.controller.ds.read(tag)
        if not predicate(value):
            desc = description or f"predicate failed for {tag}"
            raise ScenarioError(f"{desc} (value={value})")
        return self

    def assert_output(self, tag: str, expected: bool) -> "ScenarioRunner":
        """Assert a digital output state."""
        actual = self.controller.ds.read(tag)
        if actual != expected:
            raise ScenarioError(
                f"Output {tag}: expected {expected}, got {actual}"
            )
        return self

    # ── Snapshots & Debugging ─────────────────────────────────

    def snapshot(self) -> dict:
        """Return a process snapshot for inspection."""
        snap = self.controller.get_status()
        snap["scan_count"] = self.scan_count
        return snap

    def record(self) -> "ScenarioRunner":
        """Append a snapshot to the history log."""
        self._history.append(self.snapshot())
        return self

    @property
    def history(self) -> list[dict]:
        """Return recorded snapshot history."""
        return list(self._history)
