"""
Flow Measurement Module — Smith E3-S1 PD Meter
================================================
Processes pulse input from the Smith E3-S1 positive displacement
meter with right-angle drive. Computes:

  - Instantaneous flow rate (BPH)
  - Gross accumulated volume (BBL)
  - Net volume with temperature correction (CTL per API 11.1)

The meter has a VR Truck loading counter head for local display
and generates pulses proportional to throughput volume.
"""

import time
import logging

from plc.core.data_store import DataStore
from plc.config.setpoints import Setpoints

logger = logging.getLogger(__name__)


class FlowMeasurement:
    """
    Processes Smith E3-S1 meter pulses into engineering values.

    The meter K-factor (pulses per barrel) is calibrated during
    proving and stored in setpoints. Temperature correction is
    applied per API MPMS Chapter 11.1 (CTL tables).
    """

    def __init__(self, data_store: DataStore, setpoints: Setpoints):
        self.ds = data_store
        self.sp = setpoints
        self._last_pulse_count = 0
        self._last_pulse_time = time.time()
        self._flow_rate_bph = 0.0
        self._gross_total_bbl = 0.0

    def execute(self):
        """Run flow calculation for this scan cycle."""
        current_pulses = self.ds.read("PI_METER_PULSE")
        now = time.time()

        # Calculate delta pulses since last scan
        delta_pulses = current_pulses - self._last_pulse_count
        delta_time = now - self._last_pulse_time

        if delta_pulses < 0:
            # Counter rollover
            delta_pulses = current_pulses

        if delta_time <= 0:
            delta_time = self.sp.scan_rate_ms / 1000.0

        # Gross volume increment
        k_factor = self.sp.meter_k_factor
        if k_factor > 0:
            delta_bbl = delta_pulses / k_factor
        else:
            delta_bbl = 0.0

        # Instantaneous flow rate (barrels per hour)
        if delta_time > 0 and delta_pulses > 0:
            bbl_per_sec = delta_bbl / delta_time
            self._flow_rate_bph = bbl_per_sec * 3600.0
        elif delta_time > 2.0:
            # No pulses for 2 seconds - decay flow rate
            self._flow_rate_bph = 0.0

        # Accumulate gross total
        self._gross_total_bbl += delta_bbl

        # Apply meter factor
        meter_factor = self.ds.read("METER_FACTOR") or 1.0
        corrected_gross = self._gross_total_bbl * meter_factor

        # Temperature correction (CTL)
        ctl = self.ds.read("CTL_FACTOR") or 1.0
        net_bbl = corrected_gross * ctl

        # Write results
        self.ds.write("FLOW_RATE_BPH", round(self._flow_rate_bph, 2))
        self.ds.write("FLOW_TOTAL_BBL", round(self._gross_total_bbl, 4))
        self.ds.write("FLOW_NET_BBL", round(net_bbl, 4))
        self.ds.write("BATCH_GROSS_BBL", round(corrected_gross, 4))
        self.ds.write("BATCH_NET_BBL", round(net_bbl, 4))

        self._last_pulse_count = current_pulses
        self._last_pulse_time = now

    def reset_totals(self):
        """Reset batch totals (new batch)."""
        self._gross_total_bbl = 0.0
        self.ds.write("FLOW_TOTAL_BBL", 0.0)
        self.ds.write("FLOW_NET_BBL", 0.0)
        self.ds.write("BATCH_GROSS_BBL", 0.0)
        self.ds.write("BATCH_NET_BBL", 0.0)
        logger.info("Flow totals reset")
