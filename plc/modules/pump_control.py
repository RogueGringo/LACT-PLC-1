"""
Transfer Pump Control
======================
Controls the TEFC motor and ANSI centrifugal pump.

Specifications:
  - 480 VAC, 3-phase
  - Motor starter with overload relay
  - Run feedback via auxiliary contact
  - Motor protection: max starts per hour, restart lockout

The pump is the main mover for the LACT unit, pulling oil
through the strainer and pushing it through the BS&W probe,
static mixer, sampler, meter, and out to sales/divert.
"""

import time
import logging
from collections import deque

from plc.core.data_store import DataStore
from plc.config.setpoints import Setpoints

logger = logging.getLogger(__name__)


class PumpControl:
    """
    Manages transfer pump motor start/stop and protection.

    Tracks motor starts for thermal protection and enforces
    restart lockout timing after trips.
    """

    def __init__(self, data_store: DataStore, setpoints: Setpoints):
        self.ds = data_store
        self.sp = setpoints
        self._start_times: deque = deque(maxlen=20)
        self._last_trip_time = 0.0
        self._locked_out = False

    def execute(self):
        """Monitor pump status each scan cycle."""
        pump_cmd = self.ds.read("DO_PUMP_START")
        pump_run = self.ds.read("DI_PUMP_RUNNING")
        pump_overload = self.ds.read("DI_PUMP_OVERLOAD")

        # Track overload trips
        if pump_overload and pump_cmd:
            self._last_trip_time = time.time()
            self._locked_out = True
            self.ds.write("DO_PUMP_START", False)
            logger.warning("Pump tripped on overload")

        # Enforce restart lockout
        if self._locked_out:
            elapsed = time.time() - self._last_trip_time
            if elapsed < self.sp.pump_restart_lockout_sec:
                self.ds.write("DO_PUMP_START", False)
                return
            else:
                self._locked_out = False
                logger.info("Pump restart lockout expired")

        # Track starts per hour
        if pump_cmd and not pump_run:
            # Pump being commanded but not yet running = start attempt
            pass

    def record_start(self):
        """Record a pump start event for thermal tracking."""
        now = time.time()
        self._start_times.append(now)

        # Count starts in the last hour
        one_hour_ago = now - 3600
        recent_starts = sum(1 for t in self._start_times if t > one_hour_ago)

        if recent_starts >= self.sp.pump_max_starts_per_hour:
            self._locked_out = True
            logger.warning(
                "Pump max starts exceeded: %d in last hour", recent_starts
            )
            return False
        return True

    @property
    def is_running(self) -> bool:
        return bool(self.ds.read("DI_PUMP_RUNNING"))

    @property
    def is_locked_out(self) -> bool:
        return self._locked_out

    @property
    def starts_this_hour(self) -> int:
        now = time.time()
        one_hour_ago = now - 3600
        return sum(1 for t in self._start_times if t > one_hour_ago)
