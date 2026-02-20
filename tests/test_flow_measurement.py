"""
Tests for the Flow Measurement module (Smith E3-S1).
"""

import time
import pytest

from plc.modules.flow_measurement import FlowMeasurement
from plc.core.data_store import DataStore
from plc.config.setpoints import Setpoints


class TestFlowMeasurement:
    """Test pulse processing and volume calculations."""

    @pytest.fixture
    def flow(self, data_store, setpoints):
        setpoints.meter_k_factor = 100.0  # 100 pulses/barrel
        return FlowMeasurement(data_store, setpoints)

    def test_initial_values(self, flow, data_store):
        flow.execute()
        assert data_store.read("FLOW_RATE_BPH") == 0.0
        assert data_store.read("FLOW_TOTAL_BBL") == 0.0

    def test_pulse_accumulation(self, flow, data_store, setpoints):
        # Simulate 100 pulses = 1 barrel
        data_store.write("PI_METER_PULSE", 100)
        data_store.write("METER_FACTOR", 1.0)
        data_store.write("CTL_FACTOR", 1.0)
        flow._last_pulse_time = time.time() - 1.0  # 1 second ago
        flow.execute()

        assert data_store.read("FLOW_TOTAL_BBL") == 1.0

    def test_flow_rate_calculation(self, flow, data_store):
        data_store.write("METER_FACTOR", 1.0)
        data_store.write("CTL_FACTOR", 1.0)

        # 100 pulses in 1 second = 1 BBL/sec = 3600 BPH
        flow._last_pulse_time = time.time() - 1.0
        data_store.write("PI_METER_PULSE", 100)
        flow.execute()

        rate = data_store.read("FLOW_RATE_BPH")
        assert rate > 0

    def test_meter_factor_applied(self, flow, data_store):
        data_store.write("METER_FACTOR", 1.05)
        data_store.write("CTL_FACTOR", 1.0)

        data_store.write("PI_METER_PULSE", 100)
        flow._last_pulse_time = time.time() - 1.0
        flow.execute()

        gross = data_store.read("BATCH_GROSS_BBL")
        assert abs(gross - 1.05) < 0.01  # 1 BBL * 1.05 MF

    def test_ctl_correction(self, flow, data_store):
        data_store.write("METER_FACTOR", 1.0)
        data_store.write("CTL_FACTOR", 0.995)

        data_store.write("PI_METER_PULSE", 100)
        flow._last_pulse_time = time.time() - 1.0
        flow.execute()

        net = data_store.read("BATCH_NET_BBL")
        assert net < 1.0  # CTL < 1 means hot oil, net < gross

    def test_reset_totals(self, flow, data_store):
        data_store.write("METER_FACTOR", 1.0)
        data_store.write("CTL_FACTOR", 1.0)
        data_store.write("PI_METER_PULSE", 200)
        flow._last_pulse_time = time.time() - 1.0
        flow.execute()
        assert data_store.read("FLOW_TOTAL_BBL") > 0

        flow.reset_totals()
        assert data_store.read("FLOW_TOTAL_BBL") == 0.0
        assert data_store.read("BATCH_GROSS_BBL") == 0.0

    def test_zero_k_factor_safety(self, flow, data_store, setpoints):
        setpoints.meter_k_factor = 0.0
        data_store.write("PI_METER_PULSE", 100)
        flow._last_pulse_time = time.time() - 1.0
        flow.execute()
        assert data_store.read("FLOW_TOTAL_BBL") == 0.0
