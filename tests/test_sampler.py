"""
Tests for the Automatic Sampling module.
"""

import time
import pytest

from plc.modules.sampler import Sampler
from plc.core.data_store import DataStore
from plc.core.state_machine import LACTState
from plc.config.setpoints import Setpoints


class TestSampler:
    """Test automatic flow-proportional sampling logic."""

    @pytest.fixture
    def sampler(self, data_store, setpoints):
        setpoints.sample_rate_sec = 0.0  # Immediate grab for testing
        return Sampler(data_store, setpoints)

    def test_no_sampling_when_not_running(self, sampler, data_store):
        data_store.write("FLOW_RATE_BPH", 400.0)
        sampler.execute(LACTState.IDLE)
        assert data_store.read("DO_SAMPLE_SOL") is False

    def test_no_sampling_during_divert(self, sampler, data_store):
        data_store.write("FLOW_RATE_BPH", 400.0)
        sampler.execute(LACTState.DIVERT)
        assert data_store.read("DO_SAMPLE_SOL") is False

    def test_sample_grab_when_running(self, sampler, data_store):
        data_store.write("FLOW_RATE_BPH", 400.0)
        sampler.execute(LACTState.RUNNING)
        assert data_store.read("SAMPLE_TOTAL_GRABS") == 1

    def test_sample_pot_full_stops_sampling(self, sampler, data_store):
        data_store.write("FLOW_RATE_BPH", 400.0)
        data_store.write("DI_SAMPLE_POT_HI", True)
        sampler.execute(LACTState.RUNNING)
        assert data_store.read("DO_SAMPLE_SOL") is False

    def test_no_sampling_without_flow(self, sampler, data_store):
        data_store.write("FLOW_RATE_BPH", 0.0)
        sampler.execute(LACTState.RUNNING)
        assert data_store.read("SAMPLE_TOTAL_GRABS") == 0

    def test_sample_total_ml_accumulates(self, sampler, data_store, setpoints):
        setpoints.sample_volume_ml = 5.0
        data_store.write("FLOW_RATE_BPH", 400.0)

        sampler.execute(LACTState.RUNNING)
        assert data_store.read("SAMPLE_TOTAL_ML") == 5.0

    def test_reset_totals(self, sampler, data_store):
        data_store.write("FLOW_RATE_BPH", 400.0)
        sampler.execute(LACTState.RUNNING)
        assert data_store.read("SAMPLE_TOTAL_GRABS") > 0

        sampler.reset_totals()
        assert data_store.read("SAMPLE_TOTAL_GRABS") == 0
        assert data_store.read("SAMPLE_TOTAL_ML") == 0.0
