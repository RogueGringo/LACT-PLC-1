"""
Pressure Monitoring Module
===========================
Monitors all pressure points across the LACT unit:

  - Inlet pressure (after inlet ball valve)
  - Loop high-point pressure (at air eliminator)
  - Strainer differential pressure (4-mesh screen)
  - Outlet pressure (downstream of meter)

Drives the backpressure valve setpoints for the sales
and divert lines (two 3" 150# backpressure valves).
"""

import logging

from plc.core.data_store import DataStore
from plc.config.setpoints import Setpoints

logger = logging.getLogger(__name__)


class PressureMonitor:
    """
    Reads and processes all pressure transmitters.

    Updates analog output setpoints for the backpressure
    valves based on configured targets.
    """

    def __init__(self, data_store: DataStore, setpoints: Setpoints):
        self.ds = data_store
        self.sp = setpoints

    def execute(self):
        """Process pressure readings for this scan cycle."""
        # Write backpressure valve setpoints
        self.ds.write("AO_BP_SALES_SP", self.sp.backpressure_sales_psi)
        self.ds.write("AO_BP_DIVERT_SP", self.sp.backpressure_divert_psi)

    @property
    def inlet_pressure(self) -> float:
        return self.ds.read("AI_INLET_PRESS")

    @property
    def loop_pressure(self) -> float:
        return self.ds.read("AI_LOOP_HI_PRESS")

    @property
    def strainer_dp(self) -> float:
        return self.ds.read("AI_STRAINER_DP")

    @property
    def outlet_pressure(self) -> float:
        return self.ds.read("AI_OUTLET_PRESS")
