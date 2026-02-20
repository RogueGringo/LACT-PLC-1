"""
Configuration Generator
=========================
Transforms a UnitProfile into a complete PLC configuration:
  - IOMap with all I/O points for the unit's specific components
  - Setpoints tuned for the unit's meter, pump, and process
  - AlarmConfig appropriate for the unit's instrumentation

This is the bridge between the intake/profile system and the
running PLC controller. A unit profile goes in; a ready-to-run
configuration comes out.
"""

from plc.config.io_map import IOMap, IOPoint, SignalType
from plc.config.setpoints import Setpoints
from plc.config.alarms import AlarmConfig, AlarmDefinition, AlarmPriority, AlarmAction
from plc.fleet.unit_profile import UnitProfile
from plc.fleet.components import (
    KNOWN_METERS, KNOWN_PUMPS, KNOWN_DIVERT_VALVES,
    KNOWN_BSW_PROBES, KNOWN_SAMPLERS, KNOWN_PROVERS,
    MeterType,
)


class ConfigGenerator:
    """
    Generates IOMap, Setpoints, and AlarmConfig from a UnitProfile.

    The generator uses the component library to determine what
    I/O points are needed and what default parameters are
    appropriate for each specific component combination.
    """

    def __init__(self, profile: UnitProfile):
        self.profile = profile
        self.comp = profile.components

    def generate_all(self) -> tuple:
        """
        Generate all configuration objects.
        Returns (IOMap, Setpoints, AlarmConfig).
        """
        io_map = self.generate_io_map()
        setpoints = self.generate_setpoints()
        alarm_config = self.generate_alarms()
        return io_map, setpoints, alarm_config

    # ── I/O Map Generation ───────────────────────────────────

    def generate_io_map(self) -> IOMap:
        """Generate a complete IOMap for the unit."""
        io_map = IOMap(
            digital_inputs={},
            digital_outputs={},
            analog_inputs={},
            pulse_inputs={},
            analog_outputs={},
        )

        di_addr = 0
        do_addr = 0
        ai_addr = 0
        pi_addr = 0
        ao_addr = 0

        # ── Inlet Section ────────────────────────────────────
        io_map.digital_inputs["DI_INLET_VLV_OPEN"] = IOPoint(
            tag="DI_INLET_VLV_OPEN",
            signal_type=SignalType.DIGITAL_IN,
            address=di_addr, description="Inlet ball valve - open limit switch",
            modbus_register=di_addr,
        )
        di_addr += 1

        io_map.digital_inputs["DI_INLET_VLV_CLOSED"] = IOPoint(
            tag="DI_INLET_VLV_CLOSED",
            signal_type=SignalType.DIGITAL_IN,
            address=di_addr, description="Inlet ball valve - closed limit switch",
            modbus_register=di_addr,
        )
        di_addr += 1

        # ── Strainer ─────────────────────────────────────────
        if self.comp.has_strainer:
            io_map.digital_inputs["DI_STRAINER_HI_DP"] = IOPoint(
                tag="DI_STRAINER_HI_DP",
                signal_type=SignalType.DIGITAL_IN,
                address=di_addr,
                description=f"Strainer high DP switch ({self.comp.strainer_mesh} mesh)",
                modbus_register=di_addr,
            )
            di_addr += 1

        # ── Pump ─────────────────────────────────────────────
        pump = KNOWN_PUMPS.get(self.comp.pump_key)
        io_map.digital_inputs["DI_PUMP_RUNNING"] = IOPoint(
            tag="DI_PUMP_RUNNING",
            signal_type=SignalType.DIGITAL_IN,
            address=di_addr,
            description="Transfer pump motor running feedback",
            modbus_register=di_addr,
        )
        di_addr += 1

        io_map.digital_inputs["DI_PUMP_OVERLOAD"] = IOPoint(
            tag="DI_PUMP_OVERLOAD",
            signal_type=SignalType.DIGITAL_IN,
            address=di_addr,
            description="Transfer pump motor overload relay trip",
            modbus_register=di_addr,
        )
        di_addr += 1

        io_map.digital_outputs["DO_PUMP_START"] = IOPoint(
            tag="DO_PUMP_START",
            signal_type=SignalType.DIGITAL_OUT,
            address=do_addr,
            description="Transfer pump motor contactor coil",
            modbus_register=100 + do_addr,
        )
        do_addr += 1

        # ── Divert Valve ─────────────────────────────────────
        io_map.digital_inputs["DI_DIVERT_SALES"] = IOPoint(
            tag="DI_DIVERT_SALES",
            signal_type=SignalType.DIGITAL_IN,
            address=di_addr,
            description="Divert valve at SALES position",
            modbus_register=di_addr,
        )
        di_addr += 1

        io_map.digital_inputs["DI_DIVERT_DIVERT"] = IOPoint(
            tag="DI_DIVERT_DIVERT",
            signal_type=SignalType.DIGITAL_IN,
            address=di_addr,
            description="Divert valve at DIVERT position",
            modbus_register=di_addr,
        )
        di_addr += 1

        io_map.digital_outputs["DO_DIVERT_CMD"] = IOPoint(
            tag="DO_DIVERT_CMD",
            signal_type=SignalType.DIGITAL_OUT,
            address=do_addr,
            description="Divert valve command (0=SALES, 1=DIVERT)",
            modbus_register=100 + do_addr,
        )
        do_addr += 1

        # ── Sampler ──────────────────────────────────────────
        sampler = KNOWN_SAMPLERS.get(self.comp.sampler_key)
        io_map.digital_inputs["DI_SAMPLE_POT_HI"] = IOPoint(
            tag="DI_SAMPLE_POT_HI",
            signal_type=SignalType.DIGITAL_IN,
            address=di_addr,
            description="Sample receiver pot high level",
            modbus_register=di_addr,
        )
        di_addr += 1

        io_map.digital_inputs["DI_SAMPLE_POT_LO"] = IOPoint(
            tag="DI_SAMPLE_POT_LO",
            signal_type=SignalType.DIGITAL_IN,
            address=di_addr,
            description="Sample receiver pot low level",
            modbus_register=di_addr,
        )
        di_addr += 1

        io_map.digital_outputs["DO_SAMPLE_SOL"] = IOPoint(
            tag="DO_SAMPLE_SOL",
            signal_type=SignalType.DIGITAL_OUT,
            address=do_addr,
            description="Sample solenoid valve",
            modbus_register=100 + do_addr,
        )
        do_addr += 1

        if sampler and sampler.has_mixing_pump:
            io_map.digital_outputs["DO_SAMPLE_MIX_PUMP"] = IOPoint(
                tag="DO_SAMPLE_MIX_PUMP",
                signal_type=SignalType.DIGITAL_OUT,
                address=do_addr,
                description="Sample pot mixing pump",
                modbus_register=100 + do_addr,
            )
            do_addr += 1

        # ── Prover ───────────────────────────────────────────
        prover = KNOWN_PROVERS.get(self.comp.prover_key)
        if prover and prover.io_signature.digital_inputs:
            io_map.digital_inputs["DI_PROVER_VLV_OPEN"] = IOPoint(
                tag="DI_PROVER_VLV_OPEN",
                signal_type=SignalType.DIGITAL_IN,
                address=di_addr,
                description="Prover DBB valve - open",
                modbus_register=di_addr,
            )
            di_addr += 1

            io_map.digital_outputs["DO_PROVER_VLV_CMD"] = IOPoint(
                tag="DO_PROVER_VLV_CMD",
                signal_type=SignalType.DIGITAL_OUT,
                address=do_addr,
                description="Prover DBB valve open command",
                modbus_register=100 + do_addr,
            )
            do_addr += 1

        # ── Air Eliminator ───────────────────────────────────
        if self.comp.has_air_eliminator:
            io_map.digital_inputs["DI_AIR_ELIM_FLOAT"] = IOPoint(
                tag="DI_AIR_ELIM_FLOAT",
                signal_type=SignalType.DIGITAL_IN,
                address=di_addr,
                description="Air eliminator float switch (gas detected)",
                modbus_register=di_addr,
            )
            di_addr += 1

        # ── Outlet ───────────────────────────────────────────
        io_map.digital_inputs["DI_OUTLET_VLV_OPEN"] = IOPoint(
            tag="DI_OUTLET_VLV_OPEN",
            signal_type=SignalType.DIGITAL_IN,
            address=di_addr,
            description="Outlet ball valve - open limit switch",
            modbus_register=di_addr,
        )
        di_addr += 1

        # ── E-Stop ───────────────────────────────────────────
        io_map.digital_inputs["DI_ESTOP"] = IOPoint(
            tag="DI_ESTOP",
            signal_type=SignalType.DIGITAL_IN,
            address=di_addr,
            description="Emergency stop pushbutton (NC contact)",
            modbus_register=di_addr,
        )
        di_addr += 1

        # ── Annunciation ─────────────────────────────────────
        io_map.digital_outputs["DO_ALARM_BEACON"] = IOPoint(
            tag="DO_ALARM_BEACON",
            signal_type=SignalType.DIGITAL_OUT,
            address=do_addr,
            description="Alarm beacon (visual)",
            modbus_register=100 + do_addr,
        )
        do_addr += 1

        io_map.digital_outputs["DO_ALARM_HORN"] = IOPoint(
            tag="DO_ALARM_HORN",
            signal_type=SignalType.DIGITAL_OUT,
            address=do_addr,
            description="Alarm horn (audible)",
            modbus_register=100 + do_addr,
        )
        do_addr += 1

        io_map.digital_outputs["DO_STATUS_GREEN"] = IOPoint(
            tag="DO_STATUS_GREEN",
            signal_type=SignalType.DIGITAL_OUT,
            address=do_addr,
            description="Running status light (green)",
            modbus_register=100 + do_addr,
        )
        do_addr += 1

        # ── Analog Inputs ────────────────────────────────────
        # Pressure transmitters
        io_map.analog_inputs["AI_INLET_PRESS"] = IOPoint(
            tag="AI_INLET_PRESS",
            signal_type=SignalType.ANALOG_IN,
            address=ai_addr,
            description="Inlet pressure transmitter",
            unit="PSI", eng_min=0.0, eng_max=300.0,
            modbus_register=200 + ai_addr,
        )
        ai_addr += 1

        if self.comp.num_pressure_transmitters >= 2:
            io_map.analog_inputs["AI_LOOP_HI_PRESS"] = IOPoint(
                tag="AI_LOOP_HI_PRESS",
                signal_type=SignalType.ANALOG_IN,
                address=ai_addr,
                description="Loop high-point pressure",
                unit="PSI", eng_min=0.0, eng_max=300.0,
                modbus_register=200 + ai_addr,
            )
            ai_addr += 1

        # Strainer DP transmitter (if present)
        if self.comp.has_strainer:
            io_map.analog_inputs["AI_STRAINER_DP"] = IOPoint(
                tag="AI_STRAINER_DP",
                signal_type=SignalType.ANALOG_IN,
                address=ai_addr,
                description="Strainer differential pressure",
                unit="PSI", eng_min=0.0, eng_max=50.0,
                modbus_register=200 + ai_addr,
            )
            ai_addr += 1

        # BS&W probe
        bsw_probe = KNOWN_BSW_PROBES.get(self.comp.bsw_probe_key)
        bsw_range = bsw_probe.range_pct if bsw_probe else 5.0
        io_map.analog_inputs["AI_BSW_PROBE"] = IOPoint(
            tag="AI_BSW_PROBE",
            signal_type=SignalType.ANALOG_IN,
            address=ai_addr,
            description="BS&W probe",
            unit="%", eng_min=0.0, eng_max=bsw_range,
            modbus_register=200 + ai_addr,
        )
        ai_addr += 1

        # Meter temperature
        meter = KNOWN_METERS.get(self.comp.meter_key)
        if meter and meter.has_temperature_probe:
            io_map.analog_inputs["AI_METER_TEMP"] = IOPoint(
                tag="AI_METER_TEMP",
                signal_type=SignalType.ANALOG_IN,
                address=ai_addr,
                description="Meter TA probe temperature",
                unit="°F", eng_min=-20.0, eng_max=200.0,
                modbus_register=200 + ai_addr,
            )
            ai_addr += 1

        # Test thermowell
        if self.comp.has_test_thermowell:
            io_map.analog_inputs["AI_TEST_THERMO"] = IOPoint(
                tag="AI_TEST_THERMO",
                signal_type=SignalType.ANALOG_IN,
                address=ai_addr,
                description="Test thermowell downstream of meter",
                unit="°F", eng_min=-20.0, eng_max=200.0,
                modbus_register=200 + ai_addr,
            )
            ai_addr += 1

        # Outlet pressure
        if self.comp.num_pressure_transmitters >= 3:
            io_map.analog_inputs["AI_OUTLET_PRESS"] = IOPoint(
                tag="AI_OUTLET_PRESS",
                signal_type=SignalType.ANALOG_IN,
                address=ai_addr,
                description="Outlet pressure transmitter",
                unit="PSI", eng_min=0.0, eng_max=300.0,
                modbus_register=200 + ai_addr,
            )
            ai_addr += 1

        # ── Pulse Inputs ─────────────────────────────────────
        if meter and meter.has_pulse_output:
            io_map.pulse_inputs["PI_METER_PULSE"] = IOPoint(
                tag="PI_METER_PULSE",
                signal_type=SignalType.PULSE_IN,
                address=pi_addr,
                description=f"{meter.display_name} pulse output",
                unit="pulses",
                modbus_register=300 + pi_addr,
            )
            pi_addr += 1

        # ── Analog Outputs ───────────────────────────────────
        if self.comp.num_backpressure_valves >= 1:
            io_map.analog_outputs["AO_BP_SALES_SP"] = IOPoint(
                tag="AO_BP_SALES_SP",
                signal_type=SignalType.ANALOG_OUT,
                address=ao_addr,
                description="Backpressure valve setpoint - sales",
                unit="PSI", eng_min=0.0, eng_max=150.0,
                modbus_register=400 + ao_addr,
            )
            ao_addr += 1

        if self.comp.num_backpressure_valves >= 2:
            io_map.analog_outputs["AO_BP_DIVERT_SP"] = IOPoint(
                tag="AO_BP_DIVERT_SP",
                signal_type=SignalType.ANALOG_OUT,
                address=ao_addr,
                description="Backpressure valve setpoint - divert",
                unit="PSI", eng_min=0.0, eng_max=150.0,
                modbus_register=400 + ao_addr,
            )
            ao_addr += 1

        return io_map

    # ── Setpoints Generation ─────────────────────────────────

    def generate_setpoints(self) -> Setpoints:
        """Generate setpoints tuned for the unit's components."""
        sp = Setpoints()

        # Meter-specific setpoints
        meter = KNOWN_METERS.get(self.comp.meter_key)
        if meter:
            sp.meter_k_factor = meter.k_factor_default
            sp.meter_min_flow_bph = meter.min_flow_bph
            sp.meter_max_flow_bph = meter.max_flow_bph

        # Divert valve travel time
        divert = KNOWN_DIVERT_VALVES.get(self.comp.divert_valve_key)
        if divert:
            sp.divert_travel_timeout_sec = divert.travel_time_sec + 5.0

        # Sampler pot size
        sampler = KNOWN_SAMPLERS.get(self.comp.sampler_key)
        if sampler:
            sp.sample_pot_full_gal = sampler.pot_size_gal

        # BS&W probe range
        bsw_probe = KNOWN_BSW_PROBES.get(self.comp.bsw_probe_key)
        if bsw_probe and bsw_probe.range_pct > 5.0:
            sp.bsw_divert_pct = 1.0
            sp.bsw_alarm_pct = 0.5

        # Apply user overrides
        for key, value in self.profile.setpoint_overrides.items():
            sp.update(key, value)

        return sp

    # ── Alarm Configuration ──────────────────────────────────

    def generate_alarms(self) -> AlarmConfig:
        """Generate alarm configuration for the unit."""
        # Start with the standard alarm set
        config = AlarmConfig()

        # Adjust alarms based on installed components
        if not self.comp.has_strainer:
            config.definitions.pop("ALM_STRAINER_DP_HI", None)

        if not self.comp.has_air_eliminator:
            config.definitions.pop("ALM_GAS_DETECTED", None)

        prover = KNOWN_PROVERS.get(self.comp.prover_key)
        if not prover or not prover.io_signature.digital_inputs:
            config.definitions.pop("ALM_PROVE_REPEAT_FAIL", None)
            config.definitions.pop("ALM_PROVE_MF_RANGE", None)

        return config

    # ── Summary ──────────────────────────────────────────────

    def summary(self) -> dict:
        """Return a summary of what will be generated."""
        io_map = self.generate_io_map()
        return {
            "unit_id": self.profile.unit_id,
            "digital_inputs": len(io_map.digital_inputs),
            "digital_outputs": len(io_map.digital_outputs),
            "analog_inputs": len(io_map.analog_inputs),
            "pulse_inputs": len(io_map.pulse_inputs),
            "analog_outputs": len(io_map.analog_outputs),
            "total_io_points": len(io_map.get_all_points()),
            "meter": self.comp.meter_key,
            "pump": self.comp.pump_key,
            "divert": self.comp.divert_valve_key,
            "bsw_probe": self.comp.bsw_probe_key,
            "sampler": self.comp.sampler_key,
            "prover": self.comp.prover_key,
        }
