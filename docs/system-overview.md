# LACT PLC Control System — System Overview

## Unit Identification

| Field | Value |
|---|---|
| **Manufacturer** | SCS Technologies |
| **Type** | 3" LACT Unit (Lease Automatic Custody Transfer) |
| **Serial Numbers** | 6113-045 / 19713-03 |
| **Meter** | Smith E3-S1 3" Positive Displacement with right-angle drive |
| **Location** | Lenorah, Texas 79749 |
| **Piping Class** | 3" 150# ANSI flanged throughout |

## Architecture

### Control Platform

The system runs as a Python-based soft PLC on a Linux single-board computer:

- **Target Hardware**: Raspberry Pi 4/5 or industrial SBC (e.g., Revolution Pi)
- **I/O Interface**: Modbus RTU (serial) or Modbus TCP (Ethernet) expansion modules
- **Scan Rate**: 100 ms configurable
- **Programming Language**: Python 3.10+
- **No External Dependencies Required** for simulator mode

### Software Layers

```
┌────────────────────────────────────────────┐
│             Console Layer                   │
│   CLI (cmd module)  │  TUI (curses)        │
├────────────────────────────────────────────┤
│             Core PLC Engine                 │
│  Controller → Safety → StateMachine        │
│                 ↕                           │
│             DataStore (Tag DB)             │
├────────────────────────────────────────────┤
│           Process Modules                   │
│  Flow │ BS&W │ Sampler │ Divert │ Pump    │
│  Proving │ Pressure │ Temperature          │
├────────────────────────────────────────────┤
│            I/O Driver Layer                 │
│  IOHandler → Modbus RTU/TCP │ Simulator    │
├────────────────────────────────────────────┤
│           Physical I/O                      │
│  DI/DO/AI/AO Modbus Modules │ Field Wiring │
└────────────────────────────────────────────┘
```

### Scan Cycle Execution Order

Each 100 ms scan cycle follows this deterministic sequence:

1. **Read Inputs**: IOHandler reads all physical DI/AI/PI → DataStore
2. **Safety Interlocks**: SafetyManager evaluates all alarm conditions
3. **Safety Actions**: Shutdown/divert requests propagated to state machine
4. **State Machine**: LACTStateMachine executes current state handler
5. **Process Modules**: Each module reads DataStore, computes, writes results
6. **Write Outputs**: IOHandler writes DataStore DO/AO → physical I/O

## Process Flow Description

Oil enters the LACT unit and flows through these stages:

```
INLET → Strainer → Pump → BS&W Probe → Air Eliminator
  → Static Mixer → Sampler → Divert Valve
  → PD Meter → Prover Connections
  → Backpressure Valve → Check Valve → OUTLET
```

### Stage Details

1. **Inlet Isolation**: 3" ball valve with open/closed limit switches
2. **Straining**: 3" strainer with 4-mesh screen plate, DPI gauge for clogging detection
3. **Transfer Pump**: 480 VAC 3-phase TEFC motor, ANSI centrifugal pump
4. **BS&W Detection**: 3" capacitance probe with 4528-5 detector card on vertical riser
5. **Air Elimination**: Float-type air eliminator at loop high point
6. **Static Mixing**: 3" dual-element static mixer on vertical downcomer
7. **Sampling**: 15/20 gal system with Clay Bailey lid, SS 3-way solenoid (120 VAC XP), flow-weighted per API MPMS Ch. 8
8. **Flow Diversion**: 3" electric hydromatic divert valve (fail-to-divert)
9. **Metering**: Smith E3-S1 PD meter, right-angle drive, VR counter head, TA probe
10. **Proving**: Franklin DuraSeal DBB valve, proving tees, 3" cam lock connections
11. **Backpressure**: Two 3" backpressure valves (sales and divert lines)
12. **Check Valves**: Two 3" swing check valves (sales and divert lines)
13. **Outlet Isolation**: 3" ball valve

## State Machine

```
IDLE ──► STARTUP ──► RUNNING ──► SHUTDOWN ──► IDLE
              │           │
              │           ├──► DIVERT ──► RUNNING
              │           │
              │           └──► PROVING ──► RUNNING
              │
              └──► IDLE (on failure)

Any State ──► E_STOP (emergency)
E_STOP   ──► IDLE   (after reset)
```

| State | Description |
|---|---|
| IDLE | All outputs off, waiting for operator START command |
| STARTUP | Sequential valve alignment, pump start, BS&W stabilization |
| RUNNING | Normal custody transfer with active sampling |
| DIVERT | Flow diverted due to high BS&W or other condition |
| PROVING | Meter proving in progress, sampling paused |
| SHUTDOWN | Orderly stop: divert → stop sampler → stop pump |
| E_STOP | Immediate halt, all outputs safe, beacon/horn active |

## Running the System

```bash
# Simulator mode with CLI console (default)
python main.py

# Simulator mode with TUI dashboard
python main.py --tui

# Headless mode (no console)
python main.py --headless

# Real Modbus TCP hardware
python main.py --modbus-tcp 192.168.1.100:502

# Real Modbus RTU hardware
python main.py --modbus-rtu /dev/ttyUSB0

# Run tests
python -m pytest tests/ -v
```
