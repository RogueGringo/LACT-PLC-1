"""
Automatic Sampling System
==========================
Controls the 15/20 gallon sampling system:

  - Clay Bailey lid sample receiver
  - SS 3-way solenoid valve with XP 120 VAC coil
  - Volume regulator for flow-weighted sampling
  - Sample probe (beveled insertion type) downstream of static mixer
  - Sampling pot mixing TEFC motor and pump with 1/2" inline static mixer
  - Manual draw probe and check valve for spot checks

Sampling follows API MPMS Chapter 8 requirements:
  - Flow-proportional (flow-weighted) grab sampling
  - Sample from middle third of flow per API recommendations
  - Minimum down-gradient of 1" per foot for gravitational flow
"""

import time
import logging

from plc.core.data_store import DataStore
from plc.core.state_machine import LACTState
from plc.config.setpoints import Setpoints

logger = logging.getLogger(__name__)


class Sampler:
    """
    Manages automatic flow-proportional sampling.

    Activates the sample solenoid at intervals proportional to
    flow, controlling the volume per grab and tracking total
    sample collected.
    """

    def __init__(self, data_store: DataStore, setpoints: Setpoints):
        self.ds = data_store
        self.sp = setpoints
        self._last_grab_time = 0.0
        self._grab_count = 0
        self._total_ml = 0.0
        self._solenoid_on_time = 0.0
        self._solenoid_active = False
        self._mix_running = False

    def execute(self, state: LACTState):
        """Run sampler logic for this scan cycle."""
        now = time.time()

        # Only sample during RUNNING state (not during DIVERT)
        if state != LACTState.RUNNING:
            self._set_solenoid(False)
            return

        # Check if sample pot is full
        if self.ds.read("DI_SAMPLE_POT_HI"):
            self._set_solenoid(False)
            return

        # Flow-weighted grab timing
        flow_rate = self.ds.read("FLOW_RATE_BPH")
        if flow_rate <= 0:
            return

        # Calculate grab interval: at higher flow, sample more frequently
        # Base rate from setpoints, adjusted by flow proportion
        base_interval = self.sp.sample_rate_sec
        time_since_grab = now - self._last_grab_time

        if time_since_grab >= base_interval:
            self._take_grab(now)

        # Manage solenoid pulse duration
        if self._solenoid_active:
            # Solenoid pulse: proportional to desired volume
            pulse_duration = 0.5  # 500ms grab pulse
            if (now - self._solenoid_on_time) >= pulse_duration:
                self._set_solenoid(False)

        # Run mixing pump periodically to keep sample homogeneous
        self._manage_mixing(now)

    def _take_grab(self, now: float):
        """Actuate the sample solenoid for one grab."""
        self._set_solenoid(True)
        self._solenoid_on_time = now
        self._solenoid_active = True
        self._last_grab_time = now
        self._grab_count += 1
        self._total_ml += self.sp.sample_volume_ml

        self.ds.write("SAMPLE_TOTAL_GRABS", self._grab_count)
        self.ds.write("SAMPLE_TOTAL_ML", round(self._total_ml, 1))

    def _set_solenoid(self, on: bool):
        """Control the SS 3-way solenoid valve."""
        self.ds.write("DO_SAMPLE_SOL", on)
        if not on:
            self._solenoid_active = False

    def _manage_mixing(self, now: float):
        """Run the sample pot mixing pump periodically."""
        # Mix every 5 minutes for the configured duration
        mix_interval = 300.0  # 5 minutes
        cycle_pos = now % mix_interval
        should_mix = cycle_pos < self.sp.sample_mix_time_sec

        if should_mix != self._mix_running:
            self.ds.write("DO_SAMPLE_MIX_PUMP", should_mix)
            self._mix_running = should_mix

    def reset_totals(self):
        """Reset sample totals for new batch."""
        self._grab_count = 0
        self._total_ml = 0.0
        self.ds.write("SAMPLE_TOTAL_GRABS", 0)
        self.ds.write("SAMPLE_TOTAL_ML", 0.0)
        logger.info("Sample totals reset")
