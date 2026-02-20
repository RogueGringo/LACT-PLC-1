"""
BS&W (Basic Sediment & Water) Monitor
=======================================
Processes the 3" 150# capacitance probe with 4528-5 detector
card, mounted after the transfer pump on the vertical riser.

The probe measures water content in the oil stream. When BS&W
exceeds the divert setpoint, flow is diverted away from the
sales line to protect custody transfer accuracy.
"""

import time
import logging

from plc.core.data_store import DataStore
from plc.config.setpoints import Setpoints

logger = logging.getLogger(__name__)


class BSWMonitor:
    """
    Processes BS&W capacitance probe readings.

    Applies signal conditioning (averaging, validation) and
    determines if the BS&W level requires diverting.
    """

    def __init__(self, data_store: DataStore, setpoints: Setpoints):
        self.ds = data_store
        self.sp = setpoints
        self._readings: list[float] = []
        self._max_history = 10  # Rolling average window
        self._divert_timer_start: float = 0.0
        self._divert_pending = False

    def execute(self):
        """Process BS&W probe reading for this scan cycle."""
        raw_bsw = self.ds.read("AI_BSW_PROBE")

        # Validate signal range (0-5% for this probe)
        if raw_bsw < -0.1 or raw_bsw > 5.5:
            self.ds.write("AI_BSW_PROBE", raw_bsw, quality="BAD")
            self.ds.write("BSW_PCT", raw_bsw)
            return

        # Rolling average for noise rejection
        self._readings.append(raw_bsw)
        if len(self._readings) > self._max_history:
            self._readings.pop(0)

        avg_bsw = sum(self._readings) / len(self._readings)
        self.ds.write("BSW_PCT", round(avg_bsw, 3))

        # Divert logic with debounce timer
        if avg_bsw >= self.sp.bsw_divert_pct:
            if not self._divert_pending:
                self._divert_pending = True
                self._divert_timer_start = time.time()
            elif (time.time() - self._divert_timer_start) >= self.sp.bsw_divert_delay_sec:
                self.ds.write("DIVERT_REASON", f"BS&W {avg_bsw:.2f}%")
        else:
            self._divert_pending = False

    def reset(self):
        """Clear the rolling average history."""
        self._readings.clear()
        self._divert_pending = False
