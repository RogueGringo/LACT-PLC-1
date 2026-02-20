"""
Hardware Simulator
===================
Simulates the physical LACT unit for development and testing
without real hardware. Models realistic process behavior:

  - Oil flow through the metering loop
  - BS&W variations
  - Temperature and pressure dynamics
  - Pump response
  - Valve travel times
  - Meter pulse generation

Use this backend with IOHandler for offline development.
"""

import time
import math
import random
import logging

logger = logging.getLogger(__name__)


class HardwareSimulator:
    """
    Simulates the physical I/O of the SCS Technologies LACT unit.

    Maintains internal state for the simulated process and
    generates realistic I/O values based on the current state
    of the outputs (pump command, valve commands, etc.).
    """

    def __init__(self):
        # Internal process state
        self._pump_on = False
        self._pump_run_feedback = False
        self._pump_start_time = 0.0
        self._pump_overload = False

        self._divert_cmd = False
        self._divert_position = 0.0  # 0.0 = SALES, 1.0 = DIVERT
        self._divert_travel_rate = 0.1  # position units per second

        self._flow_rate_bph = 0.0
        self._pulse_count = 0
        self._last_pulse_time = time.time()

        self._bsw_base = 0.3  # Base BS&W percentage
        self._temperature = 85.0  # °F
        self._inlet_pressure = 45.0  # PSI
        self._outlet_pressure = 35.0  # PSI

        self._prover_valve_open = False
        self._sample_pot_level = 0.0  # gallons
        self._estop = False

        # Digital output mirror (written by control logic)
        self._do = [False] * 16
        # Analog output mirror
        self._ao = [0] * 8

        self._start_time = time.time()

    # ── IOBackend Protocol Implementation ────────────────────

    def read_digital(self, address: int) -> bool:
        """Read a simulated digital input."""
        self._update_simulation()
        return self._get_di(address)

    def write_digital(self, address: int, value: bool) -> None:
        """Write a digital output (drives simulation)."""
        self._do[address] = value
        self._process_output(address, value)

    def read_analog(self, address: int) -> int:
        """Read a simulated analog input (raw ADC value, 0-4095)."""
        self._update_simulation()
        return self._get_ai_raw(address)

    def write_analog(self, address: int, value: int) -> None:
        """Write an analog output."""
        self._ao[address] = value

    def read_pulse_count(self, address: int) -> int:
        """Read the accumulated pulse count from the meter."""
        self._update_simulation()
        return self._pulse_count

    # ── Simulation Controls ──────────────────────────────────

    def set_bsw(self, pct: float):
        """Override BS&W reading for testing."""
        self._bsw_base = pct

    def set_temperature(self, temp_f: float):
        """Override temperature for testing."""
        self._temperature = temp_f

    def set_inlet_pressure(self, psi: float):
        """Override inlet pressure for testing."""
        self._inlet_pressure = psi

    def trigger_pump_overload(self):
        """Simulate a pump motor overload trip."""
        self._pump_overload = True

    def clear_pump_overload(self):
        """Clear simulated overload condition."""
        self._pump_overload = False

    def set_estop(self, active: bool):
        """Set the E-stop state."""
        self._estop = active

    # ── Internal Simulation ──────────────────────────────────

    def _update_simulation(self):
        """Advance the simulation by one tick."""
        now = time.time()
        dt = min(now - self._last_pulse_time, 1.0)

        # Pump dynamics
        if self._pump_on:
            if not self._pump_run_feedback:
                # Motor starting delay (~2 seconds)
                if (now - self._pump_start_time) > 2.0:
                    self._pump_run_feedback = True

            if self._pump_run_feedback and not self._pump_overload:
                # Ramp flow rate up
                target_flow = 400.0  # BPH nominal
                self._flow_rate_bph += (target_flow - self._flow_rate_bph) * 0.05
            else:
                self._flow_rate_bph *= 0.9
        else:
            self._pump_run_feedback = False
            self._flow_rate_bph *= 0.8
            if self._flow_rate_bph < 1.0:
                self._flow_rate_bph = 0.0

        # Generate meter pulses based on flow
        if self._flow_rate_bph > 0:
            k_factor = 100.0  # pulses per barrel
            bbl_per_sec = self._flow_rate_bph / 3600.0
            pulses_per_sec = bbl_per_sec * k_factor
            new_pulses = int(pulses_per_sec * dt)
            self._pulse_count += new_pulses

        # Divert valve travel
        if self._divert_cmd:
            self._divert_position = min(1.0, self._divert_position + self._divert_travel_rate * dt * 10)
        else:
            self._divert_position = max(0.0, self._divert_position - self._divert_travel_rate * dt * 10)

        # Pressure varies with flow
        if self._flow_rate_bph > 0:
            self._inlet_pressure = 45.0 + random.gauss(0, 0.5)
            self._outlet_pressure = 35.0 + random.gauss(0, 0.3)
        else:
            self._inlet_pressure = max(0, self._inlet_pressure - 0.5)
            self._outlet_pressure = max(0, self._outlet_pressure - 0.3)

        # Temperature drift
        self._temperature += random.gauss(0, 0.02)
        self._temperature = max(40.0, min(120.0, self._temperature))

        # BS&W with random variation
        self._bsw_base += random.gauss(0, 0.001)
        self._bsw_base = max(0.0, min(5.0, self._bsw_base))

        # Sample pot level increases when solenoid is energized
        if self._do[2]:  # DO_SAMPLE_SOL
            self._sample_pot_level += 0.001 * dt

        self._last_pulse_time = now

    def _process_output(self, address: int, value: bool):
        """React to output changes."""
        if address == 0:  # DO_PUMP_START
            if value and not self._pump_on:
                self._pump_on = True
                self._pump_start_time = time.time()
            elif not value:
                self._pump_on = False
        elif address == 1:  # DO_DIVERT_CMD
            self._divert_cmd = value
        elif address == 4:  # DO_PROVER_VLV_CMD
            self._prover_valve_open = value

    def _get_di(self, address: int) -> bool:
        """Map address to simulated digital input state."""
        di_map = {
            0: True,   # DI_INLET_VLV_OPEN (always open in sim)
            1: False,  # DI_INLET_VLV_CLOSED
            2: False,  # DI_STRAINER_HI_DP
            3: self._pump_run_feedback,  # DI_PUMP_RUNNING
            4: self._pump_overload,      # DI_PUMP_OVERLOAD
            5: self._divert_position < 0.1,   # DI_DIVERT_SALES
            6: self._divert_position > 0.9,   # DI_DIVERT_DIVERT
            7: self._sample_pot_level >= 15.0,  # DI_SAMPLE_POT_HI
            8: self._sample_pot_level <= 0.5,   # DI_SAMPLE_POT_LO
            9: self._prover_valve_open,   # DI_PROVER_VLV_OPEN
            10: False,  # DI_AIR_ELIM_FLOAT
            11: True,   # DI_OUTLET_VLV_OPEN (always open in sim)
            12: self._estop,  # DI_ESTOP
        }
        return di_map.get(address, False)

    def _get_ai_raw(self, address: int) -> int:
        """Map address to simulated analog input (raw 0-4095)."""
        ai_map = {
            0: self._psi_to_raw(self._inlet_pressure, 0, 300),
            1: self._psi_to_raw(self._inlet_pressure * 0.95, 0, 300),
            2: self._psi_to_raw(random.gauss(2.0, 0.3), 0, 50),  # Strainer DP
            3: self._pct_to_raw(self._bsw_base + random.gauss(0, 0.01), 0, 5),
            4: self._temp_to_raw(self._temperature, -20, 200),
            5: self._temp_to_raw(self._temperature + random.gauss(0, 0.3), -20, 200),
            6: self._psi_to_raw(self._outlet_pressure, 0, 300),
        }
        return ai_map.get(address, 0)

    @staticmethod
    def _psi_to_raw(psi: float, eng_min: float, eng_max: float) -> int:
        """Convert PSI to raw ADC (0-4095)."""
        proportion = (psi - eng_min) / (eng_max - eng_min)
        return int(max(0, min(4095, proportion * 4095)))

    @staticmethod
    def _pct_to_raw(pct: float, eng_min: float, eng_max: float) -> int:
        """Convert percentage to raw ADC (0-4095)."""
        proportion = (pct - eng_min) / (eng_max - eng_min)
        return int(max(0, min(4095, proportion * 4095)))

    @staticmethod
    def _temp_to_raw(temp_f: float, eng_min: float, eng_max: float) -> int:
        """Convert temperature °F to raw ADC (0-4095)."""
        proportion = (temp_f - eng_min) / (eng_max - eng_min)
        return int(max(0, min(4095, proportion * 4095)))
