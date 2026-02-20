"""
Shared test fixtures for the LACT PLC test suite.
"""

import pytest

from plc.config.io_map import IOMap
from plc.config.setpoints import Setpoints
from plc.config.alarms import AlarmConfig
from plc.core.data_store import DataStore
from plc.core.state_machine import LACTStateMachine
from plc.core.safety import SafetyManager
from plc.core.controller import PLCController
from plc.drivers.simulator import HardwareSimulator
from plc.drivers.io_handler import IOHandler


@pytest.fixture
def data_store():
    return DataStore()


@pytest.fixture
def setpoints():
    return Setpoints()


@pytest.fixture
def alarm_config():
    return AlarmConfig()


@pytest.fixture
def io_map():
    return IOMap()


@pytest.fixture
def simulator():
    return HardwareSimulator()


@pytest.fixture
def io_handler(simulator):
    return IOHandler(backend=simulator)


@pytest.fixture
def state_machine(data_store, setpoints):
    return LACTStateMachine(data_store, setpoints)


@pytest.fixture
def safety_manager(data_store, setpoints, alarm_config):
    return SafetyManager(data_store, setpoints, alarm_config)


@pytest.fixture
def controller(io_handler):
    """Full controller with simulator backend (not started)."""
    return PLCController(io_handler=io_handler)
