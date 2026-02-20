"""
Tests for the Meter Proving module.
"""

import time
import pytest

from plc.modules.proving import ProvingManager, ProvingState
from plc.core.data_store import DataStore
from plc.config.setpoints import Setpoints


class TestProvingManager:
    """Test meter proving workflow and calculations."""

    @pytest.fixture
    def proving(self, data_store, setpoints):
        setpoints.prove_num_runs = 3
        setpoints.prove_repeatability_pct = 0.05
        return ProvingManager(data_store, setpoints)

    def test_initial_state(self, proving):
        assert proving.state == ProvingState.IDLE

    def test_start_proving(self, proving):
        proving.start_proving()
        assert proving.state == ProvingState.SETUP
        assert len(proving.runs) == 0

    def test_setup_waits_for_valve(self, proving, data_store):
        proving.start_proving()
        proving.execute()
        assert data_store.read("DO_PROVER_VLV_CMD") is True
        assert proving.state == ProvingState.SETUP

    def test_setup_transitions_on_valve_open(self, proving, data_store):
        proving.start_proving()
        data_store.write("DI_PROVER_VLV_OPEN", True)
        proving.execute()
        assert proving.state == ProvingState.RUNNING

    def test_setup_timeout(self, proving, data_store):
        proving.start_proving()
        proving._state_entry_time = time.time() - 31.0
        proving.execute()
        assert proving.state == ProvingState.FAILED

    def test_status_report(self, proving):
        status = proving.get_status()
        assert status["state"] == "IDLE"
        assert status["runs_completed"] == 0

    def test_complete_transitions_close_valve(self, proving, data_store):
        proving.state = ProvingState.COMPLETE
        proving.execute()
        assert data_store.read("DO_PROVER_VLV_CMD") is False

    def test_failed_transitions_close_valve(self, proving, data_store):
        proving.state = ProvingState.FAILED
        proving.execute()
        assert data_store.read("DO_PROVER_VLV_CMD") is False
