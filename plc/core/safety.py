"""
Safety Interlock Manager
========================
Evaluates all safety conditions each scan cycle and triggers
appropriate alarm/shutdown actions. Runs independently of the
state machine to ensure safety logic is never bypassed.
"""

import time
import logging
from typing import Optional

from plc.core.data_store import DataStore
from plc.config.setpoints import Setpoints
from plc.config.alarms import (
    AlarmConfig, AlarmState, AlarmAction, AlarmPriority,
)

logger = logging.getLogger(__name__)


class SafetyManager:
    """
    Evaluates safety interlocks and manages alarm states.

    The safety manager runs every scan cycle AFTER I/O reads
    and BEFORE module logic, so that alarm flags are available
    to all downstream modules and the state machine.
    """

    def __init__(
        self,
        data_store: DataStore,
        setpoints: Setpoints,
        alarm_config: AlarmConfig,
    ):
        self.ds = data_store
        self.sp = setpoints
        self.alarm_config = alarm_config

        # Runtime alarm states
        self.alarm_states: dict[str, AlarmState] = {
            tag: AlarmState(definition=defn)
            for tag, defn in alarm_config.definitions.items()
        }

        self._horn_silence_time: Optional[float] = None
        self._shutdown_requested = False
        self._divert_requested = False

    @property
    def shutdown_requested(self) -> bool:
        return self._shutdown_requested

    @property
    def divert_requested(self) -> bool:
        return self._divert_requested

    def execute(self):
        """Run all safety evaluations for this scan cycle."""
        self._shutdown_requested = False
        self._divert_requested = False

        self._check_estop()
        self._check_pump()
        self._check_bsw()
        self._check_pressures()
        self._check_temperatures()
        self._check_flow()
        self._check_divert_valve()
        self._check_sampler()
        self._check_air_eliminator()

        self._update_alarm_summary()
        self._drive_annunciators()

    def acknowledge_alarm(self, tag: str) -> bool:
        """Acknowledge a specific alarm."""
        state = self.alarm_states.get(tag)
        if state and state.active:
            state.acknowledge()
            logger.info("Alarm acknowledged: %s", tag)
            return True
        return False

    def acknowledge_all(self):
        """Acknowledge all active alarms."""
        for state in self.alarm_states.values():
            if state.active:
                state.acknowledge()

    def silence_horn(self):
        """Silence the alarm horn (beacon stays on)."""
        self._horn_silence_time = time.time()

    def get_active_alarms(self) -> list[AlarmState]:
        """Return list of currently active alarms."""
        return [s for s in self.alarm_states.values() if s.active]

    def get_unacknowledged_alarms(self) -> list[AlarmState]:
        """Return alarms that are active but not acknowledged."""
        return [
            s for s in self.alarm_states.values()
            if s.active and not s.acknowledged
        ]

    # ── Safety Check Functions ───────────────────────────────

    def _activate(self, tag: str, value: float = 0.0):
        """Activate an alarm and check its action."""
        state = self.alarm_states.get(tag)
        if state is None:
            return
        state.activate(value)
        action = state.definition.action
        if action == AlarmAction.SHUTDOWN or action == AlarmAction.EMERGENCY_STOP:
            self._shutdown_requested = True
        elif action == AlarmAction.DIVERT:
            self._divert_requested = True

    def _deactivate(self, tag: str):
        """Clear an alarm condition."""
        state = self.alarm_states.get(tag)
        if state:
            state.deactivate()

    def _check_estop(self):
        if self.ds.read("DI_ESTOP"):
            self._activate("ALM_ESTOP")
        else:
            self._deactivate("ALM_ESTOP")

    def _check_pump(self):
        # Overload
        if self.ds.read("DI_PUMP_OVERLOAD"):
            self._activate("ALM_PUMP_OVERLOAD")
        else:
            self._deactivate("ALM_PUMP_OVERLOAD")

        # Fail to start: commanded on but no run feedback
        pump_cmd = self.ds.read("DO_PUMP_START")
        pump_run = self.ds.read("DI_PUMP_RUNNING")
        if pump_cmd and not pump_run:
            # Allow time for motor to start
            cmd_tag = self.ds.read_with_quality("DO_PUMP_START")
            if cmd_tag and (time.time() - cmd_tag.timestamp) > 10.0:
                self._activate("ALM_PUMP_FAIL_START")
        else:
            self._deactivate("ALM_PUMP_FAIL_START")

    def _check_bsw(self):
        bsw = self.ds.read("AI_BSW_PROBE")
        bsw_quality = self.ds.read_with_quality("AI_BSW_PROBE")

        # Probe failure (signal out of range)
        if bsw_quality and bsw_quality.quality == "BAD":
            self._activate("ALM_BSW_PROBE_FAIL")
        else:
            self._deactivate("ALM_BSW_PROBE_FAIL")

        # High alarm
        if bsw >= self.sp.bsw_alarm_pct:
            self._activate("ALM_BSW_HIGH", bsw)
        else:
            self._deactivate("ALM_BSW_HIGH")

        # Divert threshold
        if bsw >= self.sp.bsw_divert_pct:
            self._activate("ALM_BSW_DIVERT", bsw)
            self._divert_requested = True
        else:
            self._deactivate("ALM_BSW_DIVERT")

    def _check_pressures(self):
        inlet_p = self.ds.read("AI_INLET_PRESS")
        loop_p = self.ds.read("AI_LOOP_HI_PRESS")
        outlet_p = self.ds.read("AI_OUTLET_PRESS")
        strainer_dp = self.ds.read("AI_STRAINER_DP")

        # Only check pressures when pump is running
        pump_running = self.ds.read("DI_PUMP_RUNNING")

        if pump_running:
            if inlet_p < self.sp.inlet_press_lo_psi:
                self._activate("ALM_INLET_PRESS_LO", inlet_p)
            else:
                self._deactivate("ALM_INLET_PRESS_LO")

        if inlet_p > self.sp.inlet_press_hi_psi:
            self._activate("ALM_INLET_PRESS_HI", inlet_p)
        else:
            self._deactivate("ALM_INLET_PRESS_HI")

        if loop_p > self.sp.loop_press_hi_psi:
            self._activate("ALM_LOOP_PRESS_HI", loop_p)
        else:
            self._deactivate("ALM_LOOP_PRESS_HI")

        if pump_running:
            if outlet_p < self.sp.outlet_press_lo_psi:
                self._activate("ALM_OUTLET_PRESS_LO", outlet_p)
            else:
                self._deactivate("ALM_OUTLET_PRESS_LO")

        if strainer_dp > self.sp.strainer_dp_hi_psi:
            self._activate("ALM_STRAINER_DP_HI", strainer_dp)
        else:
            self._deactivate("ALM_STRAINER_DP_HI")

    def _check_temperatures(self):
        meter_temp = self.ds.read("AI_METER_TEMP")
        test_temp = self.ds.read("AI_TEST_THERMO")

        if meter_temp < self.sp.temp_lo_alarm_f:
            self._activate("ALM_TEMP_LO", meter_temp)
        else:
            self._deactivate("ALM_TEMP_LO")

        if meter_temp > self.sp.temp_hi_alarm_f:
            self._activate("ALM_TEMP_HI", meter_temp)
        else:
            self._deactivate("ALM_TEMP_HI")

        delta = abs(meter_temp - test_temp)
        if delta > self.sp.temp_max_delta_f:
            self._activate("ALM_TEMP_DELTA", delta)
        else:
            self._deactivate("ALM_TEMP_DELTA")

    def _check_flow(self):
        flow_rate = self.ds.read("FLOW_RATE_BPH")
        pump_running = self.ds.read("DI_PUMP_RUNNING")

        if not pump_running:
            self._deactivate("ALM_FLOW_LO")
            self._deactivate("ALM_FLOW_HI")
            self._deactivate("ALM_NO_FLOW")
            return

        if flow_rate < self.sp.meter_min_flow_bph and flow_rate > 0:
            self._activate("ALM_FLOW_LO", flow_rate)
        else:
            self._deactivate("ALM_FLOW_LO")

        if flow_rate > self.sp.meter_max_flow_bph:
            self._activate("ALM_FLOW_HI", flow_rate)
        else:
            self._deactivate("ALM_FLOW_HI")

        # No flow with pump running
        if flow_rate == 0 and pump_running:
            pump_tag = self.ds.read_with_quality("DI_PUMP_RUNNING")
            if pump_tag and (time.time() - pump_tag.timestamp) > self.sp.meter_no_flow_timeout_sec:
                self._activate("ALM_NO_FLOW")
        else:
            self._deactivate("ALM_NO_FLOW")

    def _check_divert_valve(self):
        cmd = self.ds.read("DO_DIVERT_CMD")
        at_sales = self.ds.read("DI_DIVERT_SALES")
        at_divert = self.ds.read("DI_DIVERT_DIVERT")

        # Check for travel timeout (only when command has been actively written)
        cmd_tag = self.ds.read_with_quality("DO_DIVERT_CMD")
        if cmd_tag and cmd_tag.timestamp > 0:
            elapsed = time.time() - cmd_tag.timestamp
            if cmd and not at_divert and elapsed > self.sp.divert_travel_timeout_sec:
                self._activate("ALM_DIVERT_FAIL")
            elif not cmd and not at_sales and elapsed > self.sp.divert_travel_timeout_sec:
                self._activate("ALM_DIVERT_FAIL")
            else:
                self._deactivate("ALM_DIVERT_FAIL")
        else:
            self._deactivate("ALM_DIVERT_FAIL")

    def _check_sampler(self):
        if self.ds.read("DI_SAMPLE_POT_HI"):
            self._activate("ALM_SAMPLE_POT_FULL")
        else:
            self._deactivate("ALM_SAMPLE_POT_FULL")

    def _check_air_eliminator(self):
        if self.ds.read("DI_AIR_ELIM_FLOAT"):
            self._activate("ALM_GAS_DETECTED")
        else:
            self._deactivate("ALM_GAS_DETECTED")

    # ── Alarm Summary & Annunciators ─────────────────────────

    def _update_alarm_summary(self):
        active = self.get_active_alarms()
        unack = self.get_unacknowledged_alarms()
        highest = max(
            (a.definition.priority for a in active),
            default=AlarmPriority.INFO,
        )
        self.ds.write("ALARM_ACTIVE_COUNT", len(active))
        self.ds.write("ALARM_UNACK_COUNT", len(unack))
        self.ds.write("HIGHEST_ALARM_PRI", int(highest))

    def _drive_annunciators(self):
        """Control beacon and horn based on alarm state."""
        unack = self.get_unacknowledged_alarms()
        has_annunciate = any(
            a.definition.action.value >= AlarmAction.ANNUNCIATE.value
            for a in unack
        )

        self.ds.write("DO_ALARM_BEACON", has_annunciate)

        # Horn with auto-silence
        horn_on = has_annunciate
        if self._horn_silence_time:
            horn_on = False
            # Reset silence if new alarm arrives
            newest = max(
                (a.timestamp for a in unack),
                default=0.0,
            )
            if newest > self._horn_silence_time:
                self._horn_silence_time = None
                horn_on = has_annunciate

        self.ds.write("DO_ALARM_HORN", horn_on)
