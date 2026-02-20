"""
LACT PLC Control System — Entry Point
=======================================
Launch the PLC controller with optional CLI or TUI console.

Usage:
  python main.py                  # PLC + CLI console (simulator)
  python main.py --tui            # PLC + TUI dashboard (simulator)
  python main.py --headless       # PLC only, no console
  python main.py --modbus-tcp HOST:PORT   # Real Modbus TCP I/O
  python main.py --modbus-rtu /dev/ttyUSB0  # Real Modbus RTU I/O
"""

import argparse
import logging
import signal
import sys

from plc.config.io_map import IOMap
from plc.config.setpoints import Setpoints
from plc.config.alarms import AlarmConfig
from plc.core.controller import PLCController
from plc.drivers.io_handler import IOHandler
from plc.drivers.simulator import HardwareSimulator


def parse_args():
    parser = argparse.ArgumentParser(
        description="SCS Technologies 3\" LACT Unit PLC Controller"
    )
    parser.add_argument(
        "--tui", action="store_true",
        help="Launch the curses-based TUI dashboard"
    )
    parser.add_argument(
        "--headless", action="store_true",
        help="Run PLC without console (headless mode)"
    )
    parser.add_argument(
        "--modbus-tcp",
        help="Modbus TCP address (host:port)"
    )
    parser.add_argument(
        "--modbus-rtu",
        help="Modbus RTU serial port (e.g., /dev/ttyUSB0)"
    )
    parser.add_argument(
        "--setpoints",
        help="Path to setpoints JSON file"
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level"
    )
    parser.add_argument(
        "--log-file",
        help="Log to file instead of stderr"
    )
    return parser.parse_args()


def create_io_backend(args):
    """Create the appropriate I/O backend based on arguments."""
    if args.modbus_tcp:
        from plc.drivers.modbus_driver import ModbusDriver
        parts = args.modbus_tcp.split(":")
        host = parts[0]
        port = int(parts[1]) if len(parts) > 1 else 502
        driver = ModbusDriver(mode="tcp", host=host, port=port)
        if not driver.connect():
            print(f"Failed to connect to Modbus TCP at {host}:{port}")
            sys.exit(1)
        return driver

    if args.modbus_rtu:
        from plc.drivers.modbus_driver import ModbusDriver
        driver = ModbusDriver(mode="rtu", serial_port=args.modbus_rtu)
        if not driver.connect():
            print(f"Failed to connect to Modbus RTU at {args.modbus_rtu}")
            sys.exit(1)
        return driver

    # Default: hardware simulator
    return HardwareSimulator()


def main():
    args = parse_args()

    # Configure logging
    log_kwargs = {
        "level": getattr(logging, args.log_level),
        "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    }
    if args.log_file:
        log_kwargs["filename"] = args.log_file
    elif args.tui:
        log_kwargs["filename"] = "lact.log"
    logging.basicConfig(**log_kwargs)

    # Load configuration
    setpoints = Setpoints.load(args.setpoints) if args.setpoints else Setpoints()
    io_map = IOMap()
    alarm_config = AlarmConfig()

    # Create I/O backend and handler
    backend = create_io_backend(args)
    io_handler = IOHandler(backend=backend)

    # Create controller
    controller = PLCController(
        io_handler=io_handler,
        io_map=io_map,
        setpoints=setpoints,
        alarm_config=alarm_config,
    )

    # Handle SIGINT/SIGTERM gracefully
    def signal_handler(sig, frame):
        controller.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start PLC in background
    controller.start(blocking=False)

    try:
        if args.headless:
            print("LACT PLC running (headless mode). Press Ctrl+C to stop.")
            signal.pause()
        elif args.tui:
            from console.tui import run_tui
            run_tui(controller)
        else:
            from console.cli import run_cli
            run_cli(controller)
    finally:
        controller.stop()


if __name__ == "__main__":
    main()
