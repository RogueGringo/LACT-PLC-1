"""
Tests for the BS&W Monitor module.
"""

import pytest

from plc.modules.bsw_monitor import BSWMonitor
from plc.core.data_store import DataStore
from plc.config.setpoints import Setpoints


class TestBSWMonitor:
    """Test BS&W probe signal processing and divert logic."""

    @pytest.fixture
    def bsw(self, data_store, setpoints):
        return BSWMonitor(data_store, setpoints)

    def test_normal_bsw_reading(self, bsw, data_store):
        data_store.write("AI_BSW_PROBE", 0.3)
        bsw.execute()
        assert data_store.read("BSW_PCT") == pytest.approx(0.3, abs=0.01)

    def test_rolling_average(self, bsw, data_store):
        # Feed multiple readings
        for val in [0.3, 0.4, 0.5]:
            data_store.write("AI_BSW_PROBE", val)
            bsw.execute()
        expected_avg = (0.3 + 0.4 + 0.5) / 3
        assert data_store.read("BSW_PCT") == pytest.approx(expected_avg, abs=0.01)

    def test_out_of_range_signal(self, bsw, data_store):
        data_store.write("AI_BSW_PROBE", 6.0)  # Above 5.5 = bad
        bsw.execute()
        tag = data_store.read_with_quality("AI_BSW_PROBE")
        assert tag.quality == "BAD"

    def test_negative_signal(self, bsw, data_store):
        data_store.write("AI_BSW_PROBE", -0.5)  # Below -0.1 = bad
        bsw.execute()
        tag = data_store.read_with_quality("AI_BSW_PROBE")
        assert tag.quality == "BAD"

    def test_reset_clears_history(self, bsw, data_store):
        for _ in range(5):
            data_store.write("AI_BSW_PROBE", 1.0)
            bsw.execute()

        bsw.reset()
        assert len(bsw._readings) == 0

    def test_divert_reason_set_on_high_bsw(self, bsw, data_store, setpoints):
        setpoints.bsw_divert_pct = 1.0
        setpoints.bsw_divert_delay_sec = 0.0  # No delay for testing

        data_store.write("AI_BSW_PROBE", 1.5)
        bsw.execute()
        bsw.execute()  # Second call triggers after debounce

        reason = data_store.read("DIVERT_REASON")
        assert "BS&W" in reason
