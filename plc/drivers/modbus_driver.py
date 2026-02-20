"""
Modbus RTU/TCP Communication Driver
=====================================
Interfaces with physical I/O expansion modules via Modbus
protocol. Supports both RTU (serial) and TCP (Ethernet)
connections for maximum flexibility.

Compatible with common industrial I/O modules:
  - Waveshare Modbus RTU relay/IO modules
  - Click PLC I/O modules (Koyo/AutomationDirect)
  - Adam-6000 series (Advantech)
  - Any standard Modbus-compliant I/O
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from pymodbus.client import ModbusSerialClient, ModbusTcpClient
    from pymodbus.exceptions import ModbusException
    HAS_PYMODBUS = True
except ImportError:
    HAS_PYMODBUS = False
    logger.info("pymodbus not installed; Modbus driver unavailable")


class ModbusDriver:
    """
    Low-level Modbus communication driver.

    Wraps pymodbus for reading/writing coils, discrete inputs,
    holding registers, and input registers from field I/O modules.
    """

    def __init__(
        self,
        mode: str = "tcp",
        host: str = "127.0.0.1",
        port: int = 502,
        serial_port: str = "/dev/ttyUSB0",
        baudrate: int = 9600,
        timeout: float = 1.0,
    ):
        self.mode = mode
        self._client = None
        self._connected = False

        if not HAS_PYMODBUS:
            logger.warning("pymodbus not available; running without hardware I/O")
            return

        if mode == "tcp":
            self._client = ModbusTcpClient(
                host=host, port=port, timeout=timeout
            )
        elif mode == "rtu":
            self._client = ModbusSerialClient(
                port=serial_port,
                baudrate=baudrate,
                timeout=timeout,
                parity="N",
                stopbits=1,
                bytesize=8,
            )

    def connect(self) -> bool:
        """Establish Modbus connection."""
        if self._client is None:
            return False
        try:
            self._connected = self._client.connect()
            if self._connected:
                logger.info("Modbus %s connected", self.mode.upper())
            else:
                logger.error("Modbus %s connection failed", self.mode.upper())
            return self._connected
        except Exception:
            logger.exception("Modbus connect error")
            return False

    def disconnect(self):
        """Close Modbus connection."""
        if self._client:
            self._client.close()
            self._connected = False
            logger.info("Modbus disconnected")

    @property
    def is_connected(self) -> bool:
        return self._connected

    def read_coils(self, address: int, count: int = 1, unit: int = 1) -> Optional[list]:
        """Read discrete output coils."""
        if not self._connected:
            return None
        try:
            result = self._client.read_coils(address, count, slave=unit)
            if result.isError():
                logger.warning("Modbus read_coils error at %d", address)
                return None
            return result.bits[:count]
        except Exception:
            logger.exception("Modbus read_coils exception")
            return None

    def read_discrete_inputs(self, address: int, count: int = 1, unit: int = 1) -> Optional[list]:
        """Read discrete inputs."""
        if not self._connected:
            return None
        try:
            result = self._client.read_discrete_inputs(address, count, slave=unit)
            if result.isError():
                return None
            return result.bits[:count]
        except Exception:
            logger.exception("Modbus read_discrete exception")
            return None

    def read_input_registers(self, address: int, count: int = 1, unit: int = 1) -> Optional[list]:
        """Read analog input registers."""
        if not self._connected:
            return None
        try:
            result = self._client.read_input_registers(address, count, slave=unit)
            if result.isError():
                return None
            return result.registers[:count]
        except Exception:
            logger.exception("Modbus read_input_reg exception")
            return None

    def read_holding_registers(self, address: int, count: int = 1, unit: int = 1) -> Optional[list]:
        """Read holding registers."""
        if not self._connected:
            return None
        try:
            result = self._client.read_holding_registers(address, count, slave=unit)
            if result.isError():
                return None
            return result.registers[:count]
        except Exception:
            logger.exception("Modbus read_holding_reg exception")
            return None

    def write_coil(self, address: int, value: bool, unit: int = 1) -> bool:
        """Write a single coil (digital output)."""
        if not self._connected:
            return False
        try:
            result = self._client.write_coil(address, value, slave=unit)
            return not result.isError()
        except Exception:
            logger.exception("Modbus write_coil exception")
            return False

    def write_register(self, address: int, value: int, unit: int = 1) -> bool:
        """Write a single holding register (analog output)."""
        if not self._connected:
            return False
        try:
            result = self._client.write_register(address, value, slave=unit)
            return not result.isError()
        except Exception:
            logger.exception("Modbus write_register exception")
            return False
