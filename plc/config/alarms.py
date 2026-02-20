"""
Alarm Configuration for SCS Technologies 3" LACT Unit
======================================================
Defines alarm tags, priorities, and response actions.
"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional
import time


class AlarmPriority(IntEnum):
    INFO = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class AlarmAction(IntEnum):
    LOG_ONLY = 0
    ANNUNCIATE = 1        # Beacon + horn
    DIVERT = 2            # Divert flow
    SHUTDOWN = 3          # Stop pump, divert, alarm
    EMERGENCY_STOP = 4    # Immediate full stop


@dataclass
class AlarmDefinition:
    """Definition of a single alarm point."""
    tag: str
    description: str
    priority: AlarmPriority
    action: AlarmAction
    auto_acknowledge: bool = False
    latching: bool = True  # Stays active until acknowledged


@dataclass
class AlarmState:
    """Runtime state of a single alarm."""
    definition: AlarmDefinition
    active: bool = False
    acknowledged: bool = False
    timestamp: float = 0.0
    value: float = 0.0

    def activate(self, value: float = 0.0):
        if not self.active:
            self.active = True
            self.acknowledged = False
            self.timestamp = time.time()
            self.value = value

    def deactivate(self):
        if not self.definition.latching or self.acknowledged:
            self.active = False
            self.acknowledged = False

    def acknowledge(self):
        self.acknowledged = True
        if not self.active or not self.definition.latching:
            self.active = False


@dataclass
class AlarmConfig:
    """Complete alarm configuration for the LACT unit."""

    definitions: dict = field(default_factory=lambda: {
        # ── Emergency / Safety ───────────────────────────────
        "ALM_ESTOP": AlarmDefinition(
            tag="ALM_ESTOP",
            description="Emergency stop activated",
            priority=AlarmPriority.CRITICAL,
            action=AlarmAction.EMERGENCY_STOP,
        ),

        # ── Pump Alarms ─────────────────────────────────────
        "ALM_PUMP_OVERLOAD": AlarmDefinition(
            tag="ALM_PUMP_OVERLOAD",
            description="Transfer pump motor overload trip",
            priority=AlarmPriority.CRITICAL,
            action=AlarmAction.SHUTDOWN,
        ),
        "ALM_PUMP_FAIL_START": AlarmDefinition(
            tag="ALM_PUMP_FAIL_START",
            description="Pump failed to start (no run feedback)",
            priority=AlarmPriority.HIGH,
            action=AlarmAction.SHUTDOWN,
        ),
        "ALM_PUMP_MAX_STARTS": AlarmDefinition(
            tag="ALM_PUMP_MAX_STARTS",
            description="Pump exceeded maximum starts per hour",
            priority=AlarmPriority.HIGH,
            action=AlarmAction.ANNUNCIATE,
        ),

        # ── BS&W Alarms ─────────────────────────────────────
        "ALM_BSW_HIGH": AlarmDefinition(
            tag="ALM_BSW_HIGH",
            description="BS&W high alarm (approaching divert)",
            priority=AlarmPriority.MEDIUM,
            action=AlarmAction.ANNUNCIATE,
        ),
        "ALM_BSW_DIVERT": AlarmDefinition(
            tag="ALM_BSW_DIVERT",
            description="BS&W exceeded divert setpoint",
            priority=AlarmPriority.HIGH,
            action=AlarmAction.DIVERT,
        ),
        "ALM_BSW_PROBE_FAIL": AlarmDefinition(
            tag="ALM_BSW_PROBE_FAIL",
            description="BS&W probe signal out of range (4528-5 detector)",
            priority=AlarmPriority.HIGH,
            action=AlarmAction.DIVERT,
        ),

        # ── Pressure Alarms ─────────────────────────────────
        "ALM_INLET_PRESS_LO": AlarmDefinition(
            tag="ALM_INLET_PRESS_LO",
            description="Inlet pressure low (loss of feed)",
            priority=AlarmPriority.HIGH,
            action=AlarmAction.SHUTDOWN,
        ),
        "ALM_INLET_PRESS_HI": AlarmDefinition(
            tag="ALM_INLET_PRESS_HI",
            description="Inlet pressure high",
            priority=AlarmPriority.HIGH,
            action=AlarmAction.SHUTDOWN,
        ),
        "ALM_LOOP_PRESS_HI": AlarmDefinition(
            tag="ALM_LOOP_PRESS_HI",
            description="Loop high-point pressure high",
            priority=AlarmPriority.HIGH,
            action=AlarmAction.SHUTDOWN,
        ),
        "ALM_OUTLET_PRESS_LO": AlarmDefinition(
            tag="ALM_OUTLET_PRESS_LO",
            description="Outlet pressure low",
            priority=AlarmPriority.MEDIUM,
            action=AlarmAction.ANNUNCIATE,
        ),
        "ALM_STRAINER_DP_HI": AlarmDefinition(
            tag="ALM_STRAINER_DP_HI",
            description="Strainer differential pressure high (plugged screen)",
            priority=AlarmPriority.MEDIUM,
            action=AlarmAction.ANNUNCIATE,
        ),

        # ── Temperature Alarms ──────────────────────────────
        "ALM_TEMP_LO": AlarmDefinition(
            tag="ALM_TEMP_LO",
            description="Process temperature low",
            priority=AlarmPriority.MEDIUM,
            action=AlarmAction.ANNUNCIATE,
        ),
        "ALM_TEMP_HI": AlarmDefinition(
            tag="ALM_TEMP_HI",
            description="Process temperature high",
            priority=AlarmPriority.MEDIUM,
            action=AlarmAction.ANNUNCIATE,
        ),
        "ALM_TEMP_DELTA": AlarmDefinition(
            tag="ALM_TEMP_DELTA",
            description="TA probe / test thermowell delta exceeded",
            priority=AlarmPriority.LOW,
            action=AlarmAction.ANNUNCIATE,
        ),

        # ── Flow Alarms ─────────────────────────────────────
        "ALM_FLOW_LO": AlarmDefinition(
            tag="ALM_FLOW_LO",
            description="Flow rate below minimum (Smith E3-S1)",
            priority=AlarmPriority.MEDIUM,
            action=AlarmAction.ANNUNCIATE,
        ),
        "ALM_FLOW_HI": AlarmDefinition(
            tag="ALM_FLOW_HI",
            description="Flow rate above maximum (Smith E3-S1)",
            priority=AlarmPriority.HIGH,
            action=AlarmAction.ANNUNCIATE,
        ),
        "ALM_NO_FLOW": AlarmDefinition(
            tag="ALM_NO_FLOW",
            description="No flow detected with pump running",
            priority=AlarmPriority.HIGH,
            action=AlarmAction.SHUTDOWN,
        ),

        # ── Divert Valve Alarms ─────────────────────────────
        "ALM_DIVERT_FAIL": AlarmDefinition(
            tag="ALM_DIVERT_FAIL",
            description="Divert valve failed to travel within timeout",
            priority=AlarmPriority.CRITICAL,
            action=AlarmAction.SHUTDOWN,
        ),

        # ── Sampler Alarms ──────────────────────────────────
        "ALM_SAMPLE_POT_FULL": AlarmDefinition(
            tag="ALM_SAMPLE_POT_FULL",
            description="Sample receiver pot full (15/20 gal)",
            priority=AlarmPriority.LOW,
            action=AlarmAction.ANNUNCIATE,
        ),

        # ── Air Eliminator ──────────────────────────────────
        "ALM_GAS_DETECTED": AlarmDefinition(
            tag="ALM_GAS_DETECTED",
            description="Air eliminator float switch - gas in liquid",
            priority=AlarmPriority.MEDIUM,
            action=AlarmAction.ANNUNCIATE,
        ),

        # ── Proving ─────────────────────────────────────────
        "ALM_PROVE_REPEAT_FAIL": AlarmDefinition(
            tag="ALM_PROVE_REPEAT_FAIL",
            description="Proving runs failed repeatability check",
            priority=AlarmPriority.LOW,
            action=AlarmAction.ANNUNCIATE,
        ),
        "ALM_PROVE_MF_RANGE": AlarmDefinition(
            tag="ALM_PROVE_MF_RANGE",
            description="Meter factor outside acceptable range",
            priority=AlarmPriority.MEDIUM,
            action=AlarmAction.ANNUNCIATE,
        ),
    })

    def get_alarm(self, tag: str) -> Optional[AlarmDefinition]:
        return self.definitions.get(tag)

    def get_alarms_by_priority(
        self, min_priority: AlarmPriority
    ) -> list:
        return [
            a for a in self.definitions.values()
            if a.priority >= min_priority
        ]

    def get_alarms_by_action(self, action: AlarmAction) -> list:
        return [
            a for a in self.definitions.values()
            if a.action == action
        ]
