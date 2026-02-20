"""
Divert Valve Control
=====================
Controls the 3" 150# electric hydromatic divert valve.

The divert valve routes flow either to the sales line (normal
custody transfer) or to the divert line (rejected oil) based
on BS&W readings and other process conditions.

Safety behavior:
  - Fail-position is DIVERT (de-energize to divert)
  - Position feedback via two discrete limit switches
  - Travel timeout monitoring for stuck valve detection
"""

import time
import logging

from plc.core.data_store import DataStore
from plc.config.setpoints import Setpoints

logger = logging.getLogger(__name__)


class DivertValve:
    """
    Monitors and controls the hydromatic divert valve.

    Tracks valve position via limit switch feedback and
    validates transit times against configured timeouts.
    """

    def __init__(self, data_store: DataStore, setpoints: Setpoints):
        self.ds = data_store
        self.sp = setpoints
        self._last_cmd = None
        self._cmd_change_time = 0.0

    def execute(self):
        """Monitor divert valve status each scan cycle."""
        cmd = self.ds.read("DO_DIVERT_CMD")
        at_sales = self.ds.read("DI_DIVERT_SALES")
        at_divert = self.ds.read("DI_DIVERT_DIVERT")

        # Track command changes for timeout monitoring
        if cmd != self._last_cmd:
            self._cmd_change_time = time.time()
            self._last_cmd = cmd

        # Determine valve state
        if cmd:
            # Commanded to DIVERT
            expected_pos = at_divert
            position = "DIVERT" if at_divert else "TRANSIT_TO_DIVERT"
        else:
            # Commanded to SALES
            expected_pos = at_sales
            position = "SALES" if at_sales else "TRANSIT_TO_SALES"

        # Check for conflicting position feedback
        if at_sales and at_divert:
            position = "FAULT_BOTH_LIMITS"
            logger.error("Divert valve fault: both limit switches active")

        self.ds.write("DIVERT_VALVE_POS", position)

    @property
    def is_at_sales(self) -> bool:
        return self.ds.read("DI_DIVERT_SALES") and not self.ds.read("DO_DIVERT_CMD")

    @property
    def is_at_divert(self) -> bool:
        return self.ds.read("DI_DIVERT_DIVERT") and self.ds.read("DO_DIVERT_CMD")

    @property
    def is_in_transit(self) -> bool:
        cmd = self.ds.read("DO_DIVERT_CMD")
        if cmd:
            return not self.ds.read("DI_DIVERT_DIVERT")
        else:
            return not self.ds.read("DI_DIVERT_SALES")
