"""
Process Setpoints for SCS Technologies 3" LACT Unit
=====================================================
All tunable process parameters. These can be adjusted via the
CLI/GUI console at runtime and are persisted to disk.

References:
  - API MPMS Chapter 6 (Metering Assemblies)
  - API MPMS Chapter 8 (Sampling)
  - API MPMS Chapter 4 (Proving)
  - API MPMS Chapter 12 (Calculation of Petroleum Quantities)
"""

from dataclasses import dataclass, field
import json
from pathlib import Path


@dataclass
class Setpoints:
    """Tunable process setpoints for the LACT unit."""

    # ── BS&W (Basic Sediment & Water) ────────────────────────
    # Capacitance probe with 4528-5 detector card
    bsw_divert_pct: float = 1.0         # BS&W % to trigger divert
    bsw_alarm_pct: float = 0.5          # BS&W % to trigger high alarm
    bsw_sample_delay_sec: float = 5.0   # Delay after startup before BS&W valid
    bsw_divert_delay_sec: float = 3.0   # Debounce time before divert activates

    # ── Flow Measurement ─────────────────────────────────────
    # Smith E3-S1 PD meter with right-angle drive
    meter_k_factor: float = 100.0       # Pulses per barrel (calibration)
    meter_min_flow_bph: float = 30.0    # Minimum flow rate (barrels/hour)
    meter_max_flow_bph: float = 750.0   # Maximum flow rate (barrels/hour)
    meter_no_flow_timeout_sec: float = 60.0  # No-flow alarm timeout

    # ── Temperature Compensation ─────────────────────────────
    # TA probe in meter + test thermowell downstream
    temp_base_deg_f: float = 60.0       # Base temperature (API standard)
    temp_lo_alarm_f: float = 20.0       # Low temperature alarm
    temp_hi_alarm_f: float = 150.0      # High temperature alarm
    temp_max_delta_f: float = 2.0       # Max allowable delta between TA and test

    # ── Pressure ─────────────────────────────────────────────
    inlet_press_lo_psi: float = 5.0     # Inlet low pressure alarm (loss of feed)
    inlet_press_hi_psi: float = 250.0   # Inlet high pressure alarm
    loop_press_hi_psi: float = 250.0    # Loop high-point pressure alarm
    outlet_press_lo_psi: float = 5.0    # Outlet low pressure alarm
    backpressure_sales_psi: float = 50.0   # Sales line backpressure setpoint
    backpressure_divert_psi: float = 50.0  # Divert line backpressure setpoint
    strainer_dp_hi_psi: float = 15.0    # Strainer diff. pressure alarm (plugged)

    # ── Pump Control ─────────────────────────────────────────
    # TEFC motor + ANSI pump, 480 VAC, 3-phase
    pump_start_delay_sec: float = 5.0   # Delay after valve alignment before start
    pump_stop_delay_sec: float = 3.0    # Delay after stop command
    pump_restart_lockout_sec: float = 30.0  # Lockout after trip before restart
    pump_max_starts_per_hour: int = 6   # Motor protection limit

    # ── Sampling System ──────────────────────────────────────
    # 15/20 gal system, Clay Bailey lid, SS 3-way solenoid (120VAC)
    sample_rate_sec: float = 15.0       # Seconds between sample grabs
    sample_volume_ml: float = 5.0       # Volume per grab (API flow-weighted)
    sample_mix_time_sec: float = 30.0   # Mixing pump run time before draw
    sample_pot_full_gal: float = 15.0   # Sample pot capacity for full alarm

    # ── Proving ──────────────────────────────────────────────
    # Franklin DuraSeal DBB valve, proving tees, cam lock connections
    prove_num_runs: int = 5             # Consecutive proving runs required
    prove_repeatability_pct: float = 0.05  # Max deviation between runs (%)
    prove_meter_factor_min: float = 0.9800  # Minimum acceptable meter factor
    prove_meter_factor_max: float = 1.0200  # Maximum acceptable meter factor

    # ── Divert Valve ─────────────────────────────────────────
    # 3" electric hydromatic divert valve
    divert_travel_timeout_sec: float = 15.0  # Max time for valve to travel
    divert_confirm_delay_sec: float = 2.0    # Position confirm debounce

    # ── Safety / General ─────────────────────────────────────
    scan_rate_ms: int = 100             # PLC scan cycle time (milliseconds)
    alarm_horn_silence_sec: float = 300.0  # Auto-silence horn after (seconds)
    watchdog_timeout_sec: float = 5.0   # Watchdog timer for controller health

    # ── Persistence ──────────────────────────────────────────
    _config_path: str = field(
        default="config/setpoints.json", repr=False
    )

    def save(self, path: str = None):
        """Persist current setpoints to JSON."""
        filepath = Path(path or self._config_path)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        data = {
            k: v for k, v in self.__dict__.items()
            if not k.startswith("_")
        }
        filepath.write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls, path: str = None) -> "Setpoints":
        """Load setpoints from JSON, falling back to defaults."""
        filepath = Path(path or "config/setpoints.json")
        sp = cls()
        if filepath.exists():
            data = json.loads(filepath.read_text())
            for key, value in data.items():
                if hasattr(sp, key):
                    setattr(sp, key, type(getattr(sp, key))(value))
        return sp

    def update(self, key: str, value) -> bool:
        """Update a single setpoint, returning True on success."""
        if not hasattr(self, key) or key.startswith("_"):
            return False
        expected_type = type(getattr(self, key))
        try:
            setattr(self, key, expected_type(value))
            return True
        except (ValueError, TypeError):
            return False

    def as_dict(self) -> dict:
        """Return all setpoints as a flat dictionary."""
        return {
            k: v for k, v in self.__dict__.items()
            if not k.startswith("_")
        }
