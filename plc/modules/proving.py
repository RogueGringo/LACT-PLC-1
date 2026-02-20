"""
Meter Proving Manager
======================
Manages the proving process for the Smith E3-S1 PD meter.

Prover connections:
  - Franklin DuraSeal DBB Valve 3" 150# ANSI
  - Proving tees with full-port 3" 150# ANSI ball valves
  - Proving line drain valves (1/2") to sump enclosure
  - Male 3" cam lock connections with dust covers
  - Enclosed sump with lid

Proving procedure follows API MPMS Chapter 4 requirements:
  - Multiple consecutive proving runs
  - Repeatability check between runs
  - Meter factor calculation
"""

import time
import logging
from enum import Enum

from plc.core.data_store import DataStore
from plc.config.setpoints import Setpoints

logger = logging.getLogger(__name__)


class ProvingState(Enum):
    IDLE = "IDLE"
    SETUP = "SETUP"
    RUNNING = "RUNNING"
    CALCULATING = "CALCULATING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class ProvingRun:
    """Data from a single proving run."""
    def __init__(self):
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        self.meter_pulses: int = 0
        self.prover_volume_bbl: float = 0.0
        self.temperature_f: float = 60.0
        self.pressure_psi: float = 0.0
        self.meter_factor: float = 0.0


class ProvingManager:
    """
    Manages the meter proving workflow.

    Coordinates with external prover equipment via the DBB valve
    and prover connections. Calculates meter factor from proving
    runs and validates repeatability per API standards.
    """

    def __init__(self, data_store: DataStore, setpoints: Setpoints):
        self.ds = data_store
        self.sp = setpoints
        self.state = ProvingState.IDLE
        self.runs: list[ProvingRun] = []
        self.current_run: ProvingRun = None
        self._state_entry_time = 0.0
        self.result_meter_factor: float = 0.0
        self.result_repeatability: float = 0.0

    def start_proving(self):
        """Initiate a proving sequence."""
        self.state = ProvingState.SETUP
        self._state_entry_time = time.time()
        self.runs.clear()
        self.current_run = None
        logger.info("Proving sequence initiated")

    def execute(self):
        """Execute proving logic for this scan cycle."""
        handler = {
            ProvingState.IDLE: self._handle_idle,
            ProvingState.SETUP: self._handle_setup,
            ProvingState.RUNNING: self._handle_running,
            ProvingState.CALCULATING: self._handle_calculating,
            ProvingState.COMPLETE: self._handle_complete,
            ProvingState.FAILED: self._handle_failed,
        }.get(self.state)

        if handler:
            handler()

    def _handle_idle(self):
        pass

    def _handle_setup(self):
        """Open prover DBB valve and prepare for first run."""
        self.ds.write("DO_PROVER_VLV_CMD", True)

        # Wait for valve confirmation
        if self.ds.read("DI_PROVER_VLV_OPEN"):
            self._start_run()
        elif (time.time() - self._state_entry_time) > 30.0:
            logger.error("Proving aborted: prover valve timeout")
            self.state = ProvingState.FAILED
            self.ds.write("DO_PROVER_VLV_CMD", False)

    def _start_run(self):
        """Begin a single proving run."""
        self.current_run = ProvingRun()
        self.current_run.start_time = time.time()
        self.current_run.meter_pulses = self.ds.read("PI_METER_PULSE")
        self.current_run.temperature_f = self.ds.read("AI_METER_TEMP")
        self.current_run.pressure_psi = self.ds.read("AI_OUTLET_PRESS")
        self.state = ProvingState.RUNNING
        logger.info("Proving run %d started", len(self.runs) + 1)

    def _handle_running(self):
        """
        Accumulate pulses during a proving run.

        In practice, this waits for the prover displacer to
        complete its pass. For simulation, we use a time-based
        approach.
        """
        # Simulated run completion after 60 seconds
        # In production, this would be triggered by prover detector switches
        elapsed = time.time() - self.current_run.start_time
        if elapsed >= 60.0:
            self._end_run()

    def _end_run(self):
        """Complete a proving run and record results."""
        run = self.current_run
        run.end_time = time.time()
        end_pulses = self.ds.read("PI_METER_PULSE")
        run.meter_pulses = end_pulses - run.meter_pulses

        # In production, prover_volume_bbl comes from certified prover
        # For simulation, use a known reference volume
        run.prover_volume_bbl = 10.0  # Placeholder reference volume

        # Calculate meter factor for this run
        k_factor = self.sp.meter_k_factor
        if k_factor > 0 and run.meter_pulses > 0:
            indicated_volume = run.meter_pulses / k_factor
            run.meter_factor = run.prover_volume_bbl / indicated_volume
        else:
            run.meter_factor = 1.0

        self.runs.append(run)
        logger.info(
            "Proving run %d complete: MF=%.4f, pulses=%d",
            len(self.runs), run.meter_factor, run.meter_pulses,
        )

        # Check if we have enough runs
        if len(self.runs) >= self.sp.prove_num_runs:
            self.state = ProvingState.CALCULATING
        else:
            self._start_run()

    def _handle_calculating(self):
        """Validate repeatability and compute final meter factor."""
        meter_factors = [r.meter_factor for r in self.runs]

        if not meter_factors:
            self.state = ProvingState.FAILED
            return

        avg_mf = sum(meter_factors) / len(meter_factors)
        mf_range = max(meter_factors) - min(meter_factors)
        repeatability = (mf_range / avg_mf) * 100.0 if avg_mf else 0.0

        self.result_meter_factor = round(avg_mf, 4)
        self.result_repeatability = round(repeatability, 4)

        logger.info(
            "Proving results: MF=%.4f, repeatability=%.4f%%",
            self.result_meter_factor, self.result_repeatability,
        )

        # Validate
        if repeatability > self.sp.prove_repeatability_pct:
            logger.warning("Proving FAILED: repeatability %.4f%% > %.4f%%",
                          repeatability, self.sp.prove_repeatability_pct)
            self.state = ProvingState.FAILED
            return

        if not (self.sp.prove_meter_factor_min <= avg_mf <= self.sp.prove_meter_factor_max):
            logger.warning("Proving FAILED: MF %.4f outside range [%.4f, %.4f]",
                          avg_mf, self.sp.prove_meter_factor_min,
                          self.sp.prove_meter_factor_max)
            self.state = ProvingState.FAILED
            return

        # Apply new meter factor
        self.ds.write("METER_FACTOR", self.result_meter_factor)
        self.state = ProvingState.COMPLETE
        logger.info("New meter factor applied: %.4f", self.result_meter_factor)

    def _handle_complete(self):
        """Clean up after successful proving."""
        self.ds.write("DO_PROVER_VLV_CMD", False)

    def _handle_failed(self):
        """Clean up after failed proving."""
        self.ds.write("DO_PROVER_VLV_CMD", False)

    def get_status(self) -> dict:
        """Return proving status for display."""
        return {
            "state": self.state.value,
            "runs_completed": len(self.runs),
            "runs_required": self.sp.prove_num_runs,
            "current_mf": self.result_meter_factor,
            "repeatability_pct": self.result_repeatability,
            "run_data": [
                {
                    "run": i + 1,
                    "meter_factor": r.meter_factor,
                    "pulses": r.meter_pulses,
                    "temp_f": r.temperature_f,
                }
                for i, r in enumerate(self.runs)
            ],
        }
