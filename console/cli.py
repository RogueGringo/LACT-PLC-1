"""
LACT Unit CLI Console
======================
Command-line interface for operator interaction with the PLC.
Supports:

  - Process commands (start, stop, e-stop, prove)
  - Setpoint viewing and modification
  - Alarm management (view, acknowledge, silence)
  - Status display (process values, I/O state)
  - Batch management
  - Configuration persistence

Usage:
  python -m console.cli              # Interactive mode
  python -m console.cli status       # One-shot status
  python -m console.cli set KEY VAL  # Update setpoint
"""

import cmd
import sys
import json
import time
import logging
from typing import Optional

from plc.core.controller import PLCController
from plc.config.alarms import AlarmPriority

logger = logging.getLogger(__name__)


class LACTConsole(cmd.Cmd):
    """Interactive CLI for the LACT PLC control system."""

    intro = (
        "\n"
        "╔══════════════════════════════════════════════════════╗\n"
        "║  SCS Technologies 3\" LACT Unit — Control Console    ║\n"
        "║  Smith E3-S1 PD Meter | Lenorah, TX                 ║\n"
        "║  Type 'help' for commands, 'quit' to exit           ║\n"
        "╚══════════════════════════════════════════════════════╝\n"
    )
    prompt = "LACT> "

    def __init__(self, controller: PLCController):
        super().__init__()
        self.ctrl = controller

    # ── Process Commands ─────────────────────────────────────

    def do_start(self, arg):
        """Start the LACT unit: start"""
        print(self.ctrl.cmd_start())

    def do_stop(self, arg):
        """Normal shutdown: stop"""
        print(self.ctrl.cmd_stop())

    def do_estop(self, arg):
        """Emergency stop: estop"""
        print(self.ctrl.cmd_estop())

    def do_reset(self, arg):
        """Reset E-Stop: reset"""
        print(self.ctrl.cmd_estop_reset())

    def do_prove(self, arg):
        """Initiate meter proving: prove"""
        print(self.ctrl.cmd_prove())

    # ── Status Commands ──────────────────────────────────────

    def do_status(self, arg):
        """Show process status: status"""
        s = self.ctrl.get_status()
        print("\n── LACT Unit Status ──────────────────────────────")
        print(f"  State:          {s['state']}")
        print(f"  Scan Count:     {s['scan_count']}")
        print(f"  Scan Time:      {s['scan_time_ms']} ms (max: {s['max_scan_time_ms']} ms)")
        print()
        print("── Process Values ───────────────────────────────")
        print(f"  Flow Rate:      {s['flow_rate_bph']:.1f} BPH")
        print(f"  Gross Total:    {s['flow_total_bbl']:.2f} BBL")
        print(f"  BS&W:           {s['bsw_pct']:.3f} %")
        print(f"  Temperature:    {s['meter_temp_f']:.1f} °F")
        print(f"  Inlet Press:    {s['inlet_press_psi']:.1f} PSI")
        print(f"  Outlet Press:   {s['outlet_press_psi']:.1f} PSI")
        print(f"  Meter Factor:   {s['meter_factor']:.4f}")
        print()
        print("── Batch ────────────────────────────────────────")
        print(f"  Gross BBL:      {s['batch_gross_bbl']:.2f}")
        print(f"  Net BBL:        {s['batch_net_bbl']:.2f}")
        elapsed = s['batch_elapsed_sec']
        hrs = int(elapsed // 3600)
        mins = int((elapsed % 3600) // 60)
        print(f"  Elapsed:        {hrs}h {mins}m")
        print()
        print("── Equipment ────────────────────────────────────")
        print(f"  Pump:           {'RUNNING' if s['pump_running'] else 'STOPPED'}")
        print(f"  Divert Valve:   {'DIVERT' if s['divert_active'] else 'SALES'}")
        print(f"  Active Alarms:  {s['active_alarms']}")
        print(f"  Unack Alarms:   {s['unack_alarms']}")
        print()

    def do_io(self, arg):
        """Show all I/O tag values: io [filter]"""
        tags = self.ctrl.ds.get_all_tags()
        filter_str = arg.strip().upper() if arg else ""

        print("\n── I/O Tag Values ───────────────────────────────")
        for tag in sorted(tags.keys()):
            if filter_str and filter_str not in tag:
                continue
            info = tags[tag]
            val = info["value"]
            q = info["quality"]
            q_flag = "" if q == "GOOD" else f" [{q}]"
            if isinstance(val, bool):
                display = "ON" if val else "OFF"
            elif isinstance(val, float):
                display = f"{val:.3f}"
            else:
                display = str(val)
            print(f"  {tag:<30s} {display:>12s}{q_flag}")
        print()

    def do_flow(self, arg):
        """Show flow measurement details: flow"""
        ds = self.ctrl.ds
        print("\n── Flow Measurement (Smith E3-S1) ────────────────")
        print(f"  Flow Rate:     {ds.read('FLOW_RATE_BPH'):.1f} BPH")
        print(f"  Gross Total:   {ds.read('FLOW_TOTAL_BBL'):.4f} BBL")
        print(f"  Net Total:     {ds.read('FLOW_NET_BBL'):.4f} BBL")
        print(f"  Meter Factor:  {ds.read('METER_FACTOR'):.4f}")
        print(f"  CTL Factor:    {ds.read('CTL_FACTOR'):.6f}")
        print(f"  Pulse Count:   {ds.read('PI_METER_PULSE')}")
        print(f"  K-Factor:      {self.ctrl.sp.meter_k_factor} pulses/BBL")
        print()

    def do_proving(self, arg):
        """Show proving status: proving"""
        status = self.ctrl.proving.get_status()
        print("\n── Meter Proving Status ──────────────────────────")
        print(f"  State:          {status['state']}")
        print(f"  Runs:           {status['runs_completed']} / {status['runs_required']}")
        print(f"  Meter Factor:   {status['current_mf']:.4f}")
        print(f"  Repeatability:  {status['repeatability_pct']:.4f} %")
        if status['run_data']:
            print("\n  Run Details:")
            for rd in status['run_data']:
                print(f"    Run {rd['run']}: MF={rd['meter_factor']:.4f}  "
                      f"Pulses={rd['pulses']}  Temp={rd['temp_f']:.1f}°F")
        print()

    # ── Alarm Commands ───────────────────────────────────────

    def do_alarms(self, arg):
        """Show active alarms: alarms"""
        active = self.ctrl.safety.get_active_alarms()
        if not active:
            print("\n  No active alarms.\n")
            return
        print("\n── Active Alarms ────────────────────────────────")
        for a in sorted(active, key=lambda x: x.definition.priority, reverse=True):
            d = a.definition
            ack = "ACK" if a.acknowledged else "UNACK"
            pri = AlarmPriority(d.priority).name
            ts = time.strftime("%H:%M:%S", time.localtime(a.timestamp))
            print(f"  [{pri:8s}] {d.tag:<28s} {d.description}")
            print(f"             {ack} | Value: {a.value:.2f} | Time: {ts}")
        print()

    def do_ack(self, arg):
        """Acknowledge alarm(s): ack [tag|all]"""
        if arg.strip().lower() == "all" or not arg.strip():
            print(self.ctrl.cmd_ack_alarms())
        else:
            tag = arg.strip().upper()
            if self.ctrl.safety.acknowledge_alarm(tag):
                print(f"Alarm {tag} acknowledged")
            else:
                print(f"Alarm {tag} not found or not active")

    def do_silence(self, arg):
        """Silence alarm horn: silence"""
        print(self.ctrl.cmd_silence_horn())

    # ── Setpoint Commands ────────────────────────────────────

    def do_setpoints(self, arg):
        """Show all setpoints: setpoints [filter]"""
        sp_dict = self.ctrl.sp.as_dict()
        filter_str = arg.strip().lower() if arg else ""

        print("\n── Process Setpoints ────────────────────────────")
        for key in sorted(sp_dict.keys()):
            if filter_str and filter_str not in key.lower():
                continue
            val = sp_dict[key]
            print(f"  {key:<35s} = {val}")
        print()

    def do_set(self, arg):
        """Update a setpoint: set <key> <value>"""
        parts = arg.strip().split(None, 1)
        if len(parts) != 2:
            print("Usage: set <key> <value>")
            return

        key, value_str = parts
        # Try numeric conversion
        try:
            if "." in value_str:
                value = float(value_str)
            else:
                value = int(value_str)
        except ValueError:
            value = value_str

        result = self.ctrl.cmd_update_setpoint(key, value)
        print(result)

    def do_save(self, arg):
        """Save setpoints to disk: save [path]"""
        path = arg.strip() or None
        print(self.ctrl.cmd_save_setpoints(path))

    def do_load(self, arg):
        """Load setpoints from disk: load [path]"""
        from plc.config.setpoints import Setpoints
        path = arg.strip() or None
        self.ctrl.sp = Setpoints.load(path)
        print("Setpoints loaded")

    # ── Batch Commands ───────────────────────────────────────

    def do_batch_reset(self, arg):
        """Reset batch totals: batch_reset"""
        self.ctrl.flow.reset_totals()
        self.ctrl.sampler.reset_totals()
        self.ctrl.ds.write("BATCH_START_TIME", time.time())
        print("Batch totals reset")

    # ── Simulator Commands (dev mode) ────────────────────────

    def do_sim_bsw(self, arg):
        """[Sim] Set BS&W percentage: sim_bsw <pct>"""
        if not hasattr(self.ctrl.io.backend, 'set_bsw'):
            print("Not in simulation mode")
            return
        try:
            pct = float(arg)
            self.ctrl.io.backend.set_bsw(pct)
            print(f"Simulator BS&W set to {pct}%")
        except ValueError:
            print("Usage: sim_bsw <percentage>")

    def do_sim_temp(self, arg):
        """[Sim] Set temperature: sim_temp <°F>"""
        if not hasattr(self.ctrl.io.backend, 'set_temperature'):
            print("Not in simulation mode")
            return
        try:
            temp = float(arg)
            self.ctrl.io.backend.set_temperature(temp)
            print(f"Simulator temperature set to {temp}°F")
        except ValueError:
            print("Usage: sim_temp <degrees_F>")

    def do_sim_overload(self, arg):
        """[Sim] Trigger pump overload: sim_overload"""
        if not hasattr(self.ctrl.io.backend, 'trigger_pump_overload'):
            print("Not in simulation mode")
            return
        self.ctrl.io.backend.trigger_pump_overload()
        print("Pump overload triggered")

    def do_sim_estop(self, arg):
        """[Sim] Toggle E-Stop: sim_estop [on|off]"""
        if not hasattr(self.ctrl.io.backend, 'set_estop'):
            print("Not in simulation mode")
            return
        val = arg.strip().lower()
        if val == "on":
            self.ctrl.io.backend.set_estop(True)
            print("E-Stop activated")
        elif val == "off":
            self.ctrl.io.backend.set_estop(False)
            print("E-Stop released")
        else:
            print("Usage: sim_estop [on|off]")

    # ── Utility ──────────────────────────────────────────────

    def do_quit(self, arg):
        """Exit the console: quit"""
        print("Shutting down...")
        return True

    def do_exit(self, arg):
        """Exit the console: exit"""
        return self.do_quit(arg)

    do_EOF = do_quit

    def emptyline(self):
        pass

    def default(self, line):
        print(f"Unknown command: {line}. Type 'help' for available commands.")


def run_cli(controller: PLCController):
    """Launch the interactive CLI console."""
    console = LACTConsole(controller)
    try:
        console.cmdloop()
    except KeyboardInterrupt:
        print("\nInterrupted.")


def main():
    """Entry point for standalone CLI usage."""
    from plc.drivers.simulator import HardwareSimulator
    from plc.drivers.io_handler import IOHandler

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Create controller with simulator backend
    sim = HardwareSimulator()
    io_handler = IOHandler(backend=sim)
    controller = PLCController(io_handler=io_handler)

    # Start PLC in background thread
    controller.start(blocking=False)

    # Run interactive console
    try:
        run_cli(controller)
    finally:
        controller.stop()


if __name__ == "__main__":
    main()
