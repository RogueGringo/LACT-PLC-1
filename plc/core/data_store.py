"""
Runtime Data Store (Tag Database)
=================================
Central repository for all live process values. Every module
reads/writes through this store, ensuring a single source of
truth per scan cycle.
"""

import time
import threading
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class TagValue:
    """A single tagged process value with metadata."""
    value: Any = 0
    timestamp: float = 0.0
    quality: str = "GOOD"  # GOOD, BAD, UNCERTAIN, STALE

    def set(self, value: Any, quality: str = "GOOD"):
        self.value = value
        self.timestamp = time.time()
        self.quality = quality


class DataStore:
    """
    Thread-safe tag database for all process variables.

    Holds the current value of every I/O point, computed variable,
    setpoint, and alarm state. All modules interact via this store
    rather than directly reading I/O, enforcing a clean scan-cycle
    discipline:

        1. IOHandler reads physical I/O → writes to DataStore
        2. Modules read DataStore → compute → write results to DataStore
        3. IOHandler reads DataStore outputs → writes to physical I/O
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._tags: dict[str, TagValue] = {}
        self._init_tags()

    def _init_tags(self):
        """Pre-register all known tags with default values."""

        # ── Digital Inputs ───────────────────────────────────
        di_tags = [
            "DI_INLET_VLV_OPEN", "DI_INLET_VLV_CLOSED",
            "DI_STRAINER_HI_DP",
            "DI_PUMP_RUNNING", "DI_PUMP_OVERLOAD",
            "DI_DIVERT_SALES", "DI_DIVERT_DIVERT",
            "DI_SAMPLE_POT_HI", "DI_SAMPLE_POT_LO",
            "DI_PROVER_VLV_OPEN",
            "DI_AIR_ELIM_FLOAT",
            "DI_OUTLET_VLV_OPEN",
            "DI_ESTOP",
        ]
        for tag in di_tags:
            self._tags[tag] = TagValue(value=False)

        # ── Digital Outputs ──────────────────────────────────
        do_tags = [
            "DO_PUMP_START", "DO_DIVERT_CMD",
            "DO_SAMPLE_SOL", "DO_SAMPLE_MIX_PUMP",
            "DO_PROVER_VLV_CMD",
            "DO_ALARM_BEACON", "DO_ALARM_HORN",
            "DO_STATUS_GREEN",
        ]
        for tag in do_tags:
            self._tags[tag] = TagValue(value=False)

        # ── Analog Inputs (engineering units) ────────────────
        ai_tags = {
            "AI_INLET_PRESS": 0.0,
            "AI_LOOP_HI_PRESS": 0.0,
            "AI_STRAINER_DP": 0.0,
            "AI_BSW_PROBE": 0.0,
            "AI_METER_TEMP": 60.0,
            "AI_TEST_THERMO": 60.0,
            "AI_OUTLET_PRESS": 0.0,
        }
        for tag, default in ai_tags.items():
            self._tags[tag] = TagValue(value=default)

        # ── Pulse Inputs ─────────────────────────────────────
        self._tags["PI_METER_PULSE"] = TagValue(value=0)

        # ── Analog Outputs ───────────────────────────────────
        self._tags["AO_BP_SALES_SP"] = TagValue(value=50.0)
        self._tags["AO_BP_DIVERT_SP"] = TagValue(value=50.0)

        # ── Computed / Derived Values ────────────────────────
        computed_tags = {
            "FLOW_RATE_BPH": 0.0,          # Current flow rate (barrels/hour)
            "FLOW_TOTAL_BBL": 0.0,          # Gross total (barrels)
            "FLOW_NET_BBL": 0.0,            # Net total (temperature-corrected)
            "BSW_PCT": 0.0,                 # Current BS&W percentage
            "TEMP_CORRECTED_F": 60.0,       # Temperature for API correction
            "METER_FACTOR": 1.0000,         # Current meter factor
            "CTL_FACTOR": 1.0000,           # Correction for Temperature of Liquid
            "NET_VOLUME_BBL": 0.0,          # Net standard volume
            "SAMPLE_TOTAL_GRABS": 0,        # Number of sample grabs this batch
            "SAMPLE_TOTAL_ML": 0.0,         # Total sample volume (mL)
            "BATCH_START_TIME": 0.0,        # Batch start timestamp
            "BATCH_ELAPSED_SEC": 0.0,       # Batch elapsed time
            "BATCH_GROSS_BBL": 0.0,         # Batch gross volume
            "BATCH_NET_BBL": 0.0,           # Batch net volume
        }
        for tag, default in computed_tags.items():
            self._tags[tag] = TagValue(value=default)

        # ── State ────────────────────────────────────────────
        self._tags["LACT_STATE"] = TagValue(value="IDLE")
        self._tags["PREV_STATE"] = TagValue(value="IDLE")
        self._tags["DIVERT_REASON"] = TagValue(value="")

        # ── Alarm summary ────────────────────────────────────
        self._tags["ALARM_ACTIVE_COUNT"] = TagValue(value=0)
        self._tags["ALARM_UNACK_COUNT"] = TagValue(value=0)
        self._tags["HIGHEST_ALARM_PRI"] = TagValue(value=0)

    def read(self, tag: str) -> Any:
        """Read the current value of a tag."""
        with self._lock:
            tv = self._tags.get(tag)
            if tv is None:
                return None
            return tv.value

    def read_with_quality(self, tag: str) -> Optional[TagValue]:
        """Read value with quality and timestamp."""
        with self._lock:
            return self._tags.get(tag)

    def write(self, tag: str, value: Any, quality: str = "GOOD"):
        """Write a value to a tag."""
        with self._lock:
            if tag not in self._tags:
                self._tags[tag] = TagValue()
            self._tags[tag].set(value, quality)

    def read_multiple(self, tags: list) -> dict:
        """Read multiple tags atomically."""
        with self._lock:
            return {
                tag: self._tags[tag].value
                for tag in tags
                if tag in self._tags
            }

    def write_multiple(self, values: dict, quality: str = "GOOD"):
        """Write multiple tags atomically."""
        with self._lock:
            for tag, value in values.items():
                if tag not in self._tags:
                    self._tags[tag] = TagValue()
                self._tags[tag].set(value, quality)

    def get_all_tags(self) -> dict:
        """Return a snapshot of all tag values."""
        with self._lock:
            return {
                tag: {"value": tv.value, "quality": tv.quality, "ts": tv.timestamp}
                for tag, tv in self._tags.items()
            }

    def tag_exists(self, tag: str) -> bool:
        with self._lock:
            return tag in self._tags
