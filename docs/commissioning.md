# Hardware Commissioning Guide

## Bill of Materials — Control System

This section lists the components needed to build the PLC control
system for the SCS Technologies 3" LACT unit. The LACT unit itself
is already equipped with all process instruments and valves.

### Controller

| Item | Qty | Description |
|---|---|---|
| Raspberry Pi 4B (4GB+) | 1 | Main PLC controller |
| Industrial DIN-rail case | 1 | For Pi mounting in enclosure |
| 32GB+ microSD card | 1 | For OS and software |
| 24VDC to 5V power supply | 1 | Pi power (DIN-rail mount) |
| UPS HAT or battery backup | 1 | Graceful shutdown on power loss |

### I/O Modules (Modbus RTU)

| Item | Qty | Description |
|---|---|---|
| 16-ch Digital Input module | 1 | 24VDC, Modbus RTU |
| 8-ch Relay Output module | 1 | 24VDC coil / dry contact, Modbus RTU |
| 8-ch Analog Input module | 1 | 4-20mA / 0-10V, 12-bit, Modbus RTU |
| 2-ch Analog Output module | 1 | 4-20mA, 12-bit, Modbus RTU |
| High-speed Pulse Counter | 1 | For meter pulse input, Modbus RTU |
| RS-485 USB adapter | 1 | For Pi to Modbus RTU bus |
| RS-485 bus termination | 2 | 120Ω resistors at bus ends |

### Enclosure & Wiring

| Item | Qty | Description |
|---|---|---|
| NEMA 4X enclosure | 1 | Weather-rated for outdoor installation |
| DIN rails | 2-3 | For module mounting |
| Terminal blocks | ~50 | For field wiring termination |
| 24VDC power supply | 1 | For I/O modules and field devices |
| Interposing relays | 3 | For 480V pump starter, 120V solenoids |
| Circuit breakers | As needed | Branch protection |
| Cable glands | As needed | Enclosure entry |

### Alternative: Modbus TCP Setup

For Ethernet-based I/O, replace the RTU modules and USB adapter with
TCP-capable equivalents (e.g., Advantech ADAM-6000 series). Update
the startup command:

```bash
python main.py --modbus-tcp 192.168.1.100:502
```

## Software Installation

### On Raspberry Pi

```bash
# Install Raspberry Pi OS Lite (64-bit)
# Connect via SSH, then:

sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git

# Clone repository
git clone <repo-url> /opt/lact-plc
cd /opt/lact-plc

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install with Modbus support
pip install -e ".[modbus]"

# Test (simulator mode)
python -m pytest tests/ -v
```

### Auto-Start on Boot

Create a systemd service:

```ini
# /etc/systemd/system/lact-plc.service
[Unit]
Description=LACT PLC Control System
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/opt/lact-plc
Environment=PATH=/opt/lact-plc/venv/bin
ExecStart=/opt/lact-plc/venv/bin/python main.py --headless --modbus-rtu /dev/ttyUSB0 --log-file /var/log/lact-plc.log
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable lact-plc
sudo systemctl start lact-plc
sudo systemctl status lact-plc
```

## Field Wiring

### Digital Input Wiring (24VDC)

```
24VDC ──────┬──── DI Module Common
            │
     ┌──────┴──────┐
     │   FIELD     │
     │   CONTACT   │
     │   (NO/NC)   │
     └──────┬──────┘
            │
            └──── DI Module Input Ch.
```

For NC contacts (E-Stop, overload): wire break = alarm active.
This is fail-safe: a broken wire triggers the alarm.

### Analog Input Wiring (4-20mA, 2-wire)

```
24VDC ──── Transmitter (+) ──── Transmitter (-) ──── AI (+)
                                                      │
                                              250Ω    │ (if voltage input)
                                                      │
                                                  AI (-) / COM
```

### Pump Motor Starter (480VAC)

The DO_PUMP_START output drives an interposing relay that
energizes the 480VAC motor starter coil:

```
DO Module (24VDC) ──► Interposing Relay Coil
                          │
Interposing Relay Contact ──► 480V Starter Coil Circuit
```

### Sample Solenoid (120VAC XP)

```
DO Module (24VDC) ──► Interposing Relay Coil
                          │
Interposing Relay Contact ──► 120VAC XP Solenoid Circuit
```

## Setpoint Configuration

After installation, configure setpoints for your specific crude oil:

```bash
python main.py
LACT> setpoints                    # View all defaults
LACT> set bsw_divert_pct 1.0      # Set BS&W divert at 1.0%
LACT> set meter_k_factor 105.2    # Set meter K-factor from proving
LACT> set backpressure_sales_psi 55  # Adjust backpressure
LACT> save                         # Persist to config/setpoints.json
```

Key setpoints to configure for your installation:

| Setpoint | Default | Description |
|---|---|---|
| bsw_divert_pct | 1.0 | BS&W % to trigger divert |
| meter_k_factor | 100.0 | Pulses per barrel (from proving) |
| backpressure_sales_psi | 50.0 | Sales line backpressure |
| backpressure_divert_psi | 50.0 | Divert line backpressure |
| sample_rate_sec | 15.0 | Seconds between sample grabs |
| pump_max_starts_per_hour | 6 | Motor protection limit |
| inlet_press_lo_psi | 5.0 | Low inlet pressure alarm |
| temp_base_deg_f | 60.0 | API base temperature |
