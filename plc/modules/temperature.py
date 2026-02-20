"""
Temperature Monitoring & API Correction
========================================
Processes temperature readings from:

  - TA probe mounted in the Smith E3-S1 meter
  - Test thermowell assembly downstream of meter (per API specs)

Computes the Correction for Temperature of Liquid (CTL) factor
per API MPMS Chapter 11.1 for converting observed volume to
standard volume at 60°F.
"""

import math
import logging

from plc.core.data_store import DataStore
from plc.config.setpoints import Setpoints

logger = logging.getLogger(__name__)

# API Table 6A coefficients for crude oil (simplified)
# Full implementation would use complete API 11.1 tables
_API_ALPHA_60 = 341.0957  # Thermal expansion coefficient
_API_K0 = 341.0957
_API_K1 = 0.0
_API_K2 = 0.0


class TemperatureMonitor:
    """
    Processes temperature readings and computes CTL factor.

    The CTL (Correction for Temperature of Liquid) converts
    measured volume at observed temperature to standard volume
    at the API base temperature of 60°F.
    """

    def __init__(self, data_store: DataStore, setpoints: Setpoints):
        self.ds = data_store
        self.sp = setpoints

    def execute(self):
        """Process temperature readings for this scan cycle."""
        meter_temp = self.ds.read("AI_METER_TEMP")
        test_temp = self.ds.read("AI_TEST_THERMO")

        # Use meter (TA probe) temperature as primary
        process_temp = meter_temp

        # Compute CTL factor
        ctl = self._compute_ctl(process_temp)
        self.ds.write("CTL_FACTOR", round(ctl, 6))
        self.ds.write("TEMP_CORRECTED_F", round(process_temp, 1))

    def _compute_ctl(self, observed_temp_f: float) -> float:
        """
        Compute CTL per API MPMS Chapter 11.1 (simplified).

        For crude oil, the CTL corrects volume from observed
        temperature to the base temperature of 60°F.

        CTL = exp[-alpha_60 * dT * (1 + 0.8 * alpha_60 * dT)]

        where:
          alpha_60 = thermal expansion coefficient at 60°F
          dT = observed_temp - 60°F

        A full production implementation should use the complete
        API 11.1 table lookup with density-dependent coefficients.
        """
        base_temp = self.sp.temp_base_deg_f  # 60.0°F
        dt = observed_temp_f - base_temp

        if abs(dt) < 0.01:
            return 1.0

        # Simplified API 11.1 for light-medium crude
        # alpha_60 typically 0.00045 to 0.00065 per °F for crude
        alpha_60 = 0.00046  # Approximate for ~35 API gravity crude

        ctl = math.exp(-alpha_60 * dt * (1.0 + 0.8 * alpha_60 * dt))
        return max(0.9, min(1.1, ctl))  # Sanity bounds
