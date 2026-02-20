"""
LACT Unit TUI Dashboard
=========================
Terminal-based graphical dashboard using curses for real-time
process monitoring. Displays:

  - Live process values (flow, BS&W, temp, pressure)
  - State machine status
  - Active alarms
  - Equipment status
  - Batch information

Refreshes at 1 Hz for responsive operator experience.
"""

import curses
import time
import logging
from typing import Optional

from plc.core.controller import PLCController
from plc.config.alarms import AlarmPriority

logger = logging.getLogger(__name__)


def run_tui(controller: PLCController):
    """Launch the curses-based TUI dashboard."""
    try:
        curses.wrapper(_tui_main, controller)
    except KeyboardInterrupt:
        pass


def _tui_main(stdscr, controller: PLCController):
    """Main TUI loop inside curses wrapper."""
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(1000)  # 1 second refresh

    # Color pairs
    if curses.has_colors():
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_GREEN, -1)   # Normal/running
        curses.init_pair(2, curses.COLOR_YELLOW, -1)   # Warning
        curses.init_pair(3, curses.COLOR_RED, -1)      # Alarm/error
        curses.init_pair(4, curses.COLOR_CYAN, -1)     # Info
        curses.init_pair(5, curses.COLOR_WHITE, -1)    # Header

    GREEN = curses.color_pair(1) if curses.has_colors() else curses.A_NORMAL
    YELLOW = curses.color_pair(2) if curses.has_colors() else curses.A_NORMAL
    RED = curses.color_pair(3) if curses.has_colors() else curses.A_NORMAL
    CYAN = curses.color_pair(4) if curses.has_colors() else curses.A_NORMAL
    HEADER = curses.color_pair(5) | curses.A_BOLD if curses.has_colors() else curses.A_BOLD

    while True:
        key = stdscr.getch()
        if key == ord('q') or key == ord('Q'):
            break
        elif key == ord('s') or key == ord('S'):
            controller.cmd_start()
        elif key == ord('x') or key == ord('X'):
            controller.cmd_stop()
        elif key == ord('e') or key == ord('E'):
            controller.cmd_estop()
        elif key == ord('r') or key == ord('R'):
            controller.cmd_estop_reset()
        elif key == ord('a') or key == ord('A'):
            controller.cmd_ack_alarms()
        elif key == ord('h') or key == ord('H'):
            controller.cmd_silence_horn()
        elif key == ord('p') or key == ord('P'):
            controller.cmd_prove()

        stdscr.clear()
        height, width = stdscr.getmaxyx()
        status = controller.get_status()
        ds = controller.ds

        # ── Header ─────────────────────────────────────────
        row = 0
        title = "SCS Technologies 3\" LACT Unit — Live Dashboard"
        stdscr.addstr(row, 0, "═" * min(width - 1, 60), HEADER)
        row += 1
        stdscr.addstr(row, 0, title[:width-1], HEADER)
        row += 1
        stdscr.addstr(row, 0, "═" * min(width - 1, 60), HEADER)
        row += 2

        # ── State ──────────────────────────────────────────
        state = status['state']
        state_color = {
            "IDLE": CYAN,
            "STARTUP": YELLOW,
            "RUNNING": GREEN,
            "DIVERT": YELLOW,
            "PROVING": CYAN,
            "SHUTDOWN": YELLOW,
            "E_STOP": RED,
        }.get(state, CYAN)

        stdscr.addstr(row, 0, "STATE: ", HEADER)
        stdscr.addstr(row, 7, f" {state} ", state_color | curses.A_BOLD)

        scan_info = f"  Scan: {status['scan_count']}  ({status['scan_time_ms']} ms)"
        if len(scan_info) + 20 < width:
            stdscr.addstr(row, 25, scan_info[:width-26], CYAN)
        row += 2

        # ── Process Values ─────────────────────────────────
        if row < height - 2:
            stdscr.addstr(row, 0, "── Process Values ──", HEADER)
            row += 1

        def add_value(r, label, value, unit="", threshold_hi=None, threshold_lo=None):
            if r >= height - 1:
                return r
            color = GREEN
            if threshold_hi and value > threshold_hi:
                color = RED
            elif threshold_lo and value < threshold_lo:
                color = YELLOW
            text = f"  {label:<20s} {value:>10.2f} {unit}"
            stdscr.addstr(r, 0, text[:width-1], color)
            return r + 1

        row = add_value(row, "Flow Rate:", status['flow_rate_bph'], "BPH")
        row = add_value(row, "Gross Total:", status['flow_total_bbl'], "BBL")
        row = add_value(row, "BS&W:", status['bsw_pct'], "%",
                       threshold_hi=controller.sp.bsw_alarm_pct)
        row = add_value(row, "Temperature:", status['meter_temp_f'], "°F",
                       threshold_hi=controller.sp.temp_hi_alarm_f,
                       threshold_lo=controller.sp.temp_lo_alarm_f)
        row = add_value(row, "Inlet Pressure:", status['inlet_press_psi'], "PSI")
        row = add_value(row, "Outlet Pressure:", status['outlet_press_psi'], "PSI")
        row = add_value(row, "Meter Factor:", status['meter_factor'], "")
        row += 1

        # ── Batch Info ─────────────────────────────────────
        if row < height - 5:
            stdscr.addstr(row, 0, "── Batch ──", HEADER)
            row += 1
            row = add_value(row, "Gross BBL:", status['batch_gross_bbl'], "BBL")
            row = add_value(row, "Net BBL:", status['batch_net_bbl'], "BBL")
            elapsed = status['batch_elapsed_sec']
            hrs = int(elapsed // 3600)
            mins = int((elapsed % 3600) // 60)
            if row < height - 1:
                stdscr.addstr(row, 0, f"  {'Elapsed:':<20s} {hrs:>7d}h {mins:02d}m", CYAN)
                row += 1
            row += 1

        # ── Equipment ──────────────────────────────────────
        if row < height - 5:
            stdscr.addstr(row, 0, "── Equipment ──", HEADER)
            row += 1
            pump_text = "RUNNING" if status['pump_running'] else "STOPPED"
            pump_color = GREEN if status['pump_running'] else CYAN
            if row < height - 1:
                stdscr.addstr(row, 0, f"  {'Pump:':<20s} {pump_text:>10s}", pump_color)
                row += 1
            divert_text = "DIVERT" if status['divert_active'] else "SALES"
            divert_color = YELLOW if status['divert_active'] else GREEN
            if row < height - 1:
                stdscr.addstr(row, 0, f"  {'Divert Valve:':<20s} {divert_text:>10s}", divert_color)
                row += 1
            row += 1

        # ── Alarms ─────────────────────────────────────────
        if row < height - 3:
            alm_count = status['active_alarms']
            alm_color = RED if alm_count > 0 else GREEN
            stdscr.addstr(row, 0, f"── Alarms ({alm_count} active) ──", alm_color | curses.A_BOLD)
            row += 1

            active = controller.safety.get_active_alarms()
            for alm in sorted(active, key=lambda a: a.definition.priority, reverse=True):
                if row >= height - 2:
                    break
                d = alm.definition
                pri = AlarmPriority(d.priority).name
                ack = "✓" if alm.acknowledged else "!"
                color = RED if d.priority >= AlarmPriority.HIGH else YELLOW
                text = f"  {ack} [{pri:>8s}] {d.tag}: {d.description}"
                stdscr.addstr(row, 0, text[:width-1], color)
                row += 1

        # ── Key Bindings ───────────────────────────────────
        if height > 3:
            keys = "S=Start X=Stop E=EStop R=Reset A=Ack H=Silence P=Prove Q=Quit"
            stdscr.addstr(height - 1, 0, keys[:width-1], HEADER)

        stdscr.refresh()


def main():
    """Entry point for standalone TUI usage."""
    from plc.drivers.simulator import HardwareSimulator
    from plc.drivers.io_handler import IOHandler

    logging.basicConfig(
        level=logging.WARNING,
        filename="lact_tui.log",
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    sim = HardwareSimulator()
    io_handler = IOHandler(backend=sim)
    controller = PLCController(io_handler=io_handler)
    controller.start(blocking=False)

    try:
        run_tui(controller)
    finally:
        controller.stop()


if __name__ == "__main__":
    main()
