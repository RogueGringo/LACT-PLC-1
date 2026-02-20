"""
I/O Handler — Abstraction Layer
=================================
Translates between the DataStore tags and the physical I/O
driver (Modbus or simulator). Handles:

  - Reading all physical inputs into DataStore
  - Scaling analog signals (4-20mA → engineering units)
  - Writing DataStore outputs to physical I/O
  - Scaling analog outputs (engineering units → 4-20mA)

This layer allows the control logic to be completely
independent of the physical I/O mechanism.
"""

import logging
from typing import Protocol

from plc.core.data_store import DataStore
from plc.config.io_map import IOMap, IOPoint, SignalType

logger = logging.getLogger(__name__)


class IOBackend(Protocol):
    """Protocol for I/O backend implementations."""

    def read_digital(self, address: int) -> bool: ...
    def write_digital(self, address: int, value: bool) -> None: ...
    def read_analog(self, address: int) -> int: ...
    def write_analog(self, address: int, value: int) -> None: ...
    def read_pulse_count(self, address: int) -> int: ...


class IOHandler:
    """
    Bridges the DataStore to physical I/O via a pluggable backend.

    On each scan cycle:
      read_inputs():  backend → scale → DataStore
      write_outputs(): DataStore → scale → backend
    """

    def __init__(self, backend: IOBackend):
        self.backend = backend

    def read_inputs(self, ds: DataStore, io_map: IOMap):
        """Read all physical inputs into the DataStore."""
        # Digital inputs
        for tag, point in io_map.digital_inputs.items():
            try:
                raw = self.backend.read_digital(point.address)
                ds.write(tag, bool(raw))
            except Exception:
                ds.write(tag, False, quality="BAD")
                logger.warning("DI read failed: %s", tag)

        # Analog inputs
        for tag, point in io_map.analog_inputs.items():
            try:
                raw = self.backend.read_analog(point.address)
                eng = self._scale_input(raw, point)
                ds.write(tag, round(eng, 3))
            except Exception:
                ds.write(tag, 0.0, quality="BAD")
                logger.warning("AI read failed: %s", tag)

        # Pulse inputs
        for tag, point in io_map.pulse_inputs.items():
            try:
                count = self.backend.read_pulse_count(point.address)
                ds.write(tag, count)
            except Exception:
                ds.write(tag, 0, quality="BAD")
                logger.warning("PI read failed: %s", tag)

    def write_outputs(self, ds: DataStore, io_map: IOMap):
        """Write DataStore outputs to physical I/O."""
        # Digital outputs
        for tag, point in io_map.digital_outputs.items():
            try:
                value = bool(ds.read(tag))
                self.backend.write_digital(point.address, value)
            except Exception:
                logger.warning("DO write failed: %s", tag)

        # Analog outputs
        for tag, point in io_map.analog_outputs.items():
            try:
                eng_value = float(ds.read(tag) or 0)
                raw = self._scale_output(eng_value, point)
                self.backend.write_analog(point.address, raw)
            except Exception:
                logger.warning("AO write failed: %s", tag)

    @staticmethod
    def _scale_input(raw: int, point: IOPoint) -> float:
        """Scale raw ADC value to engineering units."""
        raw_range = point.raw_max - point.raw_min
        eng_range = point.eng_max - point.eng_min
        if raw_range == 0:
            return point.eng_min
        proportion = (raw - point.raw_min) / raw_range
        return point.eng_min + (proportion * eng_range)

    @staticmethod
    def _scale_output(eng_value: float, point: IOPoint) -> int:
        """Scale engineering units to raw DAC value."""
        eng_range = point.eng_max - point.eng_min
        raw_range = point.raw_max - point.raw_min
        if eng_range == 0:
            return int(point.raw_min)
        proportion = (eng_value - point.eng_min) / eng_range
        proportion = max(0.0, min(1.0, proportion))
        return int(point.raw_min + (proportion * raw_range))
