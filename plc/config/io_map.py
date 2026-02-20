"""
I/O Point Mapping for SCS Technologies 3" LACT Unit
====================================================
Maps physical I/O terminals to logical tag names.

Hardware Reference:
  - SCS Technologies 3" LACT unit (Serial: 6113-045 / 19713-03)
  - Smith E3-S1 3" Positive Displacement Meter
  - Located: Lenorah, Texas 79749

I/O Architecture:
  - Modbus RTU/TCP expansion modules
  - Analog inputs:  4-20mA, 12-bit resolution
  - Analog outputs: 4-20mA
  - Digital I/O:    24VDC sink/source
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SignalType(Enum):
    DIGITAL_IN = "DI"
    DIGITAL_OUT = "DO"
    ANALOG_IN = "AI"
    ANALOG_OUT = "AO"
    PULSE_IN = "PI"


@dataclass(frozen=True)
class IOPoint:
    """Single I/O point definition."""
    tag: str
    signal_type: SignalType
    address: int
    description: str
    unit: str = ""
    # Analog scaling (4-20mA to engineering units)
    raw_min: float = 0.0
    raw_max: float = 4095.0  # 12-bit ADC
    eng_min: float = 0.0
    eng_max: float = 100.0
    # For Modbus
    modbus_unit_id: int = 1
    modbus_register: int = 0


@dataclass
class IOMap:
    """
    Complete I/O map for the SCS Technologies 3" LACT unit.

    Organized by signal type and process section. Each IOPoint
    maps a physical terminal to a logical tag used throughout
    the control logic.
    """

    # ── Digital Inputs ───────────────────────────────────────
    digital_inputs: dict = field(default_factory=lambda: {
        # Inlet Section
        "DI_INLET_VLV_OPEN": IOPoint(
            tag="DI_INLET_VLV_OPEN",
            signal_type=SignalType.DIGITAL_IN,
            address=0,
            description="Inlet 3\" ball valve - open limit switch",
            modbus_register=0,
        ),
        "DI_INLET_VLV_CLOSED": IOPoint(
            tag="DI_INLET_VLV_CLOSED",
            signal_type=SignalType.DIGITAL_IN,
            address=1,
            description="Inlet 3\" ball valve - closed limit switch",
            modbus_register=1,
        ),

        # Strainer
        "DI_STRAINER_HI_DP": IOPoint(
            tag="DI_STRAINER_HI_DP",
            signal_type=SignalType.DIGITAL_IN,
            address=2,
            description="Strainer high differential pressure switch (4 mesh screen)",
            modbus_register=2,
        ),

        # Transfer Pump (480 VAC, 3-phase TEFC motor + ANSI pump)
        "DI_PUMP_RUNNING": IOPoint(
            tag="DI_PUMP_RUNNING",
            signal_type=SignalType.DIGITAL_IN,
            address=3,
            description="Transfer pump motor running feedback (aux contact)",
            modbus_register=3,
        ),
        "DI_PUMP_OVERLOAD": IOPoint(
            tag="DI_PUMP_OVERLOAD",
            signal_type=SignalType.DIGITAL_IN,
            address=4,
            description="Transfer pump motor overload relay trip",
            modbus_register=4,
        ),

        # Divert Valve (3\" electric hydromatic)
        "DI_DIVERT_SALES": IOPoint(
            tag="DI_DIVERT_SALES",
            signal_type=SignalType.DIGITAL_IN,
            address=5,
            description="Divert valve position - SALES (normal flow)",
            modbus_register=5,
        ),
        "DI_DIVERT_DIVERT": IOPoint(
            tag="DI_DIVERT_DIVERT",
            signal_type=SignalType.DIGITAL_IN,
            address=6,
            description="Divert valve position - DIVERT (reject flow)",
            modbus_register=6,
        ),

        # Sampler
        "DI_SAMPLE_POT_HI": IOPoint(
            tag="DI_SAMPLE_POT_HI",
            signal_type=SignalType.DIGITAL_IN,
            address=7,
            description="Sample receiver pot high level (15/20 gal)",
            modbus_register=7,
        ),
        "DI_SAMPLE_POT_LO": IOPoint(
            tag="DI_SAMPLE_POT_LO",
            signal_type=SignalType.DIGITAL_IN,
            address=8,
            description="Sample receiver pot low level",
            modbus_register=8,
        ),

        # Prover
        "DI_PROVER_VLV_OPEN": IOPoint(
            tag="DI_PROVER_VLV_OPEN",
            signal_type=SignalType.DIGITAL_IN,
            address=9,
            description="Franklin DuraSeal DBB prover valve - open",
            modbus_register=9,
        ),

        # Air Eliminator
        "DI_AIR_ELIM_FLOAT": IOPoint(
            tag="DI_AIR_ELIM_FLOAT",
            signal_type=SignalType.DIGITAL_IN,
            address=10,
            description="Air eliminator float switch (gas detected)",
            modbus_register=10,
        ),

        # Outlet
        "DI_OUTLET_VLV_OPEN": IOPoint(
            tag="DI_OUTLET_VLV_OPEN",
            signal_type=SignalType.DIGITAL_IN,
            address=11,
            description="Outlet 3\" ball valve - open limit switch",
            modbus_register=11,
        ),

        # Safety
        "DI_ESTOP": IOPoint(
            tag="DI_ESTOP",
            signal_type=SignalType.DIGITAL_IN,
            address=12,
            description="Emergency stop pushbutton (NC contact)",
            modbus_register=12,
        ),
    })

    # ── Digital Outputs ──────────────────────────────────────
    digital_outputs: dict = field(default_factory=lambda: {
        # Transfer Pump
        "DO_PUMP_START": IOPoint(
            tag="DO_PUMP_START",
            signal_type=SignalType.DIGITAL_OUT,
            address=0,
            description="Transfer pump motor contactor coil (480V starter)",
            modbus_register=100,
        ),

        # Divert Valve
        "DO_DIVERT_CMD": IOPoint(
            tag="DO_DIVERT_CMD",
            signal_type=SignalType.DIGITAL_OUT,
            address=1,
            description="Divert valve command (0=SALES, 1=DIVERT)",
            modbus_register=101,
        ),

        # Sampling System
        "DO_SAMPLE_SOL": IOPoint(
            tag="DO_SAMPLE_SOL",
            signal_type=SignalType.DIGITAL_OUT,
            address=2,
            description="Sample 3-way solenoid valve (SS, XP 120 VAC coil)",
            modbus_register=102,
        ),
        "DO_SAMPLE_MIX_PUMP": IOPoint(
            tag="DO_SAMPLE_MIX_PUMP",
            signal_type=SignalType.DIGITAL_OUT,
            address=3,
            description="Sample pot mixing pump (TEFC motor)",
            modbus_register=103,
        ),

        # Prover
        "DO_PROVER_VLV_CMD": IOPoint(
            tag="DO_PROVER_VLV_CMD",
            signal_type=SignalType.DIGITAL_OUT,
            address=4,
            description="Prover DBB valve open command",
            modbus_register=104,
        ),

        # Annunciation
        "DO_ALARM_BEACON": IOPoint(
            tag="DO_ALARM_BEACON",
            signal_type=SignalType.DIGITAL_OUT,
            address=5,
            description="Alarm beacon (visual)",
            modbus_register=105,
        ),
        "DO_ALARM_HORN": IOPoint(
            tag="DO_ALARM_HORN",
            signal_type=SignalType.DIGITAL_OUT,
            address=6,
            description="Alarm horn (audible)",
            modbus_register=106,
        ),
        "DO_STATUS_GREEN": IOPoint(
            tag="DO_STATUS_GREEN",
            signal_type=SignalType.DIGITAL_OUT,
            address=7,
            description="Status light - running (green)",
            modbus_register=107,
        ),
    })

    # ── Analog Inputs ────────────────────────────────────────
    analog_inputs: dict = field(default_factory=lambda: {
        # Pressures
        "AI_INLET_PRESS": IOPoint(
            tag="AI_INLET_PRESS",
            signal_type=SignalType.ANALOG_IN,
            address=0,
            description="Inlet pressure gauge (after inlet ball valve)",
            unit="PSI",
            eng_min=0.0,
            eng_max=300.0,
            modbus_register=200,
        ),
        "AI_LOOP_HI_PRESS": IOPoint(
            tag="AI_LOOP_HI_PRESS",
            signal_type=SignalType.ANALOG_IN,
            address=1,
            description="Loop high-point pressure (highest point on loop)",
            unit="PSI",
            eng_min=0.0,
            eng_max=300.0,
            modbus_register=201,
        ),
        "AI_STRAINER_DP": IOPoint(
            tag="AI_STRAINER_DP",
            signal_type=SignalType.ANALOG_IN,
            address=2,
            description="Strainer differential pressure (DPI gauge, 4 mesh)",
            unit="PSI",
            eng_min=0.0,
            eng_max=50.0,
            modbus_register=202,
        ),

        # BS&W
        "AI_BSW_PROBE": IOPoint(
            tag="AI_BSW_PROBE",
            signal_type=SignalType.ANALOG_IN,
            address=3,
            description="BS&W capacitance probe (4528-5 detector card)",
            unit="%",
            eng_min=0.0,
            eng_max=5.0,
            modbus_register=203,
        ),

        # Temperature
        "AI_METER_TEMP": IOPoint(
            tag="AI_METER_TEMP",
            signal_type=SignalType.ANALOG_IN,
            address=4,
            description="TA probe in Smith E3-S1 meter",
            unit="°F",
            eng_min=-20.0,
            eng_max=200.0,
            modbus_register=204,
        ),
        "AI_TEST_THERMO": IOPoint(
            tag="AI_TEST_THERMO",
            signal_type=SignalType.ANALOG_IN,
            address=5,
            description="Test thermowell downstream of meter (API spec)",
            unit="°F",
            eng_min=-20.0,
            eng_max=200.0,
            modbus_register=205,
        ),

        # Flow / Meter
        "AI_OUTLET_PRESS": IOPoint(
            tag="AI_OUTLET_PRESS",
            signal_type=SignalType.ANALOG_IN,
            address=6,
            description="Outlet pressure (downstream of meter)",
            unit="PSI",
            eng_min=0.0,
            eng_max=300.0,
            modbus_register=206,
        ),
    })

    # ── Pulse Inputs ─────────────────────────────────────────
    pulse_inputs: dict = field(default_factory=lambda: {
        "PI_METER_PULSE": IOPoint(
            tag="PI_METER_PULSE",
            signal_type=SignalType.PULSE_IN,
            address=0,
            description="Smith E3-S1 PD meter pulse output (right angle drive)",
            unit="pulses",
            eng_min=0.0,
            eng_max=1.0,  # pulses per unit volume, set via k-factor
            modbus_register=300,
        ),
    })

    # ── Analog Outputs ───────────────────────────────────────
    analog_outputs: dict = field(default_factory=lambda: {
        "AO_BP_SALES_SP": IOPoint(
            tag="AO_BP_SALES_SP",
            signal_type=SignalType.ANALOG_OUT,
            address=0,
            description="Backpressure valve setpoint - sales line",
            unit="PSI",
            eng_min=0.0,
            eng_max=150.0,
            modbus_register=400,
        ),
        "AO_BP_DIVERT_SP": IOPoint(
            tag="AO_BP_DIVERT_SP",
            signal_type=SignalType.ANALOG_OUT,
            address=1,
            description="Backpressure valve setpoint - divert line",
            unit="PSI",
            eng_min=0.0,
            eng_max=150.0,
            modbus_register=401,
        ),
    })

    def get_all_points(self) -> dict:
        """Return a flat dictionary of all I/O points keyed by tag."""
        all_points = {}
        all_points.update(self.digital_inputs)
        all_points.update(self.digital_outputs)
        all_points.update(self.analog_inputs)
        all_points.update(self.pulse_inputs)
        all_points.update(self.analog_outputs)
        return all_points

    def get_point(self, tag: str) -> Optional[IOPoint]:
        """Look up an I/O point by tag name."""
        return self.get_all_points().get(tag)

    def get_points_by_type(self, signal_type: SignalType) -> dict:
        """Return all points of a given signal type."""
        attr_map = {
            SignalType.DIGITAL_IN: self.digital_inputs,
            SignalType.DIGITAL_OUT: self.digital_outputs,
            SignalType.ANALOG_IN: self.analog_inputs,
            SignalType.ANALOG_OUT: self.analog_outputs,
            SignalType.PULSE_IN: self.pulse_inputs,
        }
        return attr_map.get(signal_type, {})
