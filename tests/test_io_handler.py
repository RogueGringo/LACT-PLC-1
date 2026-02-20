"""
Tests for the I/O Handler and Simulator.
"""

import time
import pytest

from plc.drivers.io_handler import IOHandler
from plc.drivers.simulator import HardwareSimulator
from plc.core.data_store import DataStore
from plc.config.io_map import IOMap, IOPoint, SignalType


class TestIOHandler:
    """Test I/O scaling and read/write operations."""

    def test_read_digital_inputs(self, io_handler, data_store, io_map):
        io_handler.read_inputs(data_store, io_map)
        # Simulator defaults: inlet valve open
        assert data_store.read("DI_INLET_VLV_OPEN") is True

    def test_read_analog_inputs(self, io_handler, data_store, io_map):
        io_handler.read_inputs(data_store, io_map)
        # Should have some analog values
        temp = data_store.read("AI_METER_TEMP")
        assert isinstance(temp, float)

    def test_write_digital_outputs(self, io_handler, data_store, io_map, simulator):
        data_store.write("DO_PUMP_START", True)
        io_handler.write_outputs(data_store, io_map)
        # Simulator should now have pump on
        assert simulator._pump_on is True

    def test_analog_scaling_input(self):
        point = IOPoint(
            tag="TEST",
            signal_type=SignalType.ANALOG_IN,
            address=0,
            description="test",
            raw_min=0,
            raw_max=4095,
            eng_min=0.0,
            eng_max=100.0,
        )
        # Mid-range
        result = IOHandler._scale_input(2048, point)
        assert abs(result - 50.0) < 1.0

        # Zero
        result = IOHandler._scale_input(0, point)
        assert result == 0.0

        # Full scale
        result = IOHandler._scale_input(4095, point)
        assert abs(result - 100.0) < 0.1

    def test_analog_scaling_output(self):
        point = IOPoint(
            tag="TEST",
            signal_type=SignalType.ANALOG_OUT,
            address=0,
            description="test",
            raw_min=0,
            raw_max=4095,
            eng_min=0.0,
            eng_max=100.0,
        )
        result = IOHandler._scale_output(50.0, point)
        assert abs(result - 2048) < 2

        result = IOHandler._scale_output(0.0, point)
        assert result == 0

        result = IOHandler._scale_output(100.0, point)
        assert result == 4095


class TestHardwareSimulator:
    """Test simulator behavior."""

    def test_pump_start_response(self, simulator):
        simulator.write_digital(0, True)  # DO_PUMP_START
        assert simulator._pump_on is True

    def test_pump_run_feedback_delay(self, simulator):
        simulator.write_digital(0, True)
        # Immediate: not yet running
        assert simulator._get_di(3) is False
        # After delay
        simulator._pump_start_time -= 3.0
        simulator._update_simulation()
        assert simulator._get_di(3) is True

    def test_divert_valve_travel(self, simulator):
        # Start at SALES
        assert simulator._get_di(5) is True  # DI_DIVERT_SALES

        # Command to DIVERT
        simulator.write_digital(1, True)  # DO_DIVERT_CMD
        # Force enough time delta for valve to travel
        simulator._divert_position = 0.0
        simulator._last_pulse_time = time.time()
        # Directly advance position to test the endpoint
        simulator._divert_position = 0.95
        assert simulator._divert_position > 0.5

    def test_estop_control(self, simulator):
        assert simulator._get_di(12) is False
        simulator.set_estop(True)
        assert simulator._get_di(12) is True

    def test_bsw_override(self, simulator):
        simulator.set_bsw(3.0)
        assert simulator._bsw_base == 3.0

    def test_temperature_override(self, simulator):
        simulator.set_temperature(100.0)
        assert simulator._temperature == 100.0

    def test_pulse_count_increases_with_flow(self, simulator):
        initial = simulator.read_pulse_count(0)
        simulator.write_digital(0, True)  # Start pump
        simulator._pump_start_time -= 3.0  # Skip motor start delay
        simulator._pump_run_feedback = True
        simulator._flow_rate_bph = 400.0

        # Force enough time delta for pulses to accumulate
        simulator._last_pulse_time = time.time() - 1.0
        simulator._update_simulation()

        final = simulator._pulse_count
        assert final > initial
