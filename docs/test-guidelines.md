# Test Guidelines & Commissioning Checklist

## Test Framework

Tests use `pytest` and require no hardware. The `HardwareSimulator`
backend provides realistic process behavior for all test scenarios.

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage report
python -m pytest tests/ --cov=plc --cov-report=term-missing

# Run specific test module
python -m pytest tests/test_safety.py -v

# Run specific test
python -m pytest tests/test_state_machine.py::TestLACTStateMachine::test_estop_from_any_state -v
```

## Test Categories

### Unit Tests (105 tests total)

| Module | File | Tests | Coverage |
|---|---|---|---|
| DataStore | test_data_store.py | 10 | Tag CRUD, quality, threading |
| State Machine | test_state_machine.py | 12 | All state transitions, E-Stop |
| Safety Manager | test_safety.py | 17 | All alarm conditions, annunciators |
| Flow Measurement | test_flow_measurement.py | 7 | Pulse processing, CTL, meter factor |
| BS&W Monitor | test_bsw_monitor.py | 6 | Signal processing, divert logic |
| Sampler | test_sampler.py | 7 | Grab timing, pot full, flow-weighted |
| Pump Control | test_pump_control.py | 7 | Overload, lockout, max starts |
| Proving | test_proving.py | 8 | Proving workflow, valve control |
| I/O Handler | test_io_handler.py | 5 | Scaling, read/write operations |
| Simulator | test_io_handler.py | 6 | Pump, valve, pulse simulation |
| Controller | test_controller.py | 13 | Integration, commands, scan loop |

### What Each Test Validates

**Safety-Critical Tests:**
- E-Stop activates from any operational state
- E-Stop forces all outputs to safe state
- Pump overload trips immediately stop pump
- BS&W above divert setpoint triggers divert
- BS&W probe failure (out-of-range signal) triggers divert
- Inlet pressure loss shuts down pump
- Divert valve travel timeout triggers shutdown alarm
- All critical alarms correctly request shutdown or divert

**Process Logic Tests:**
- Meter pulse accumulation correctly computes volume
- Meter factor is applied to gross volume
- CTL correction reduces net volume when temperature > 60°F
- BS&W rolling average filters noise
- Sample grabs only occur during RUNNING state (not DIVERT)
- Sample pot full stops sampling
- Flow-weighted sampling proportional to flow rate
- Proving sequence validates repeatability

**State Machine Tests:**
- All legal transitions are permitted
- Illegal transitions are rejected (e.g., IDLE → RUNNING)
- Startup sequence aborts if valves not aligned
- Shutdown sequence is orderly (divert → stop sampler → stop pump)
- Divert state clears when BS&W drops below setpoint

## Commissioning Checklist

### Phase 1: Pre-Power Checks

- [ ] Verify all field wiring per I/O mapping document
- [ ] Confirm 24VDC supply to I/O modules
- [ ] Confirm 480VAC 3-phase supply to pump motor starter
- [ ] Confirm 120VAC supply for solenoid valves
- [ ] Verify E-Stop wiring (NC contacts, wire break = active)
- [ ] Verify pump overload relay NC contacts
- [ ] Inspect all pressure transmitter installations
- [ ] Verify BS&W probe mounting (vertical riser, after pump)
- [ ] Verify TA probe installation in meter
- [ ] Verify test thermowell downstream of meter per API specs
- [ ] Inspect sample probe insertion depth (middle third of flow)
- [ ] Verify sample line gradient (min 1" per foot downslope)

### Phase 2: I/O Verification

For each I/O point, verify correct reading in the CLI:

```bash
python main.py
LACT> io DI    # Check all digital inputs
LACT> io AI    # Check all analog inputs
```

- [ ] DI_INLET_VLV_OPEN: Manually open/close inlet valve, verify state
- [ ] DI_OUTLET_VLV_OPEN: Same for outlet valve
- [ ] DI_PUMP_RUNNING: Jog pump, verify feedback
- [ ] DI_PUMP_OVERLOAD: Trip overload, verify detection
- [ ] DI_DIVERT_SALES / DI_DIVERT_DIVERT: Manually cycle valve
- [ ] DI_STRAINER_HI_DP: Verify switch operation
- [ ] DI_SAMPLE_POT_HI / LO: Fill/drain sample pot
- [ ] DI_AIR_ELIM_FLOAT: Verify float switch
- [ ] DI_ESTOP: Press/release E-Stop button
- [ ] AI_INLET_PRESS: Apply known pressure, verify reading
- [ ] AI_BSW_PROBE: Verify with known BS&W standard
- [ ] AI_METER_TEMP: Verify against test thermometer
- [ ] AI_TEST_THERMO: Verify matches TA probe within tolerance
- [ ] PI_METER_PULSE: Manually turn meter, count pulses
- [ ] DO_PUMP_START: Command on, verify contactor pulls in
- [ ] DO_DIVERT_CMD: Command divert, verify valve travels
- [ ] DO_SAMPLE_SOL: Command on, verify solenoid energizes
- [ ] DO_ALARM_BEACON: Command on, verify beacon
- [ ] DO_ALARM_HORN: Command on, verify horn

### Phase 3: Functional Testing

- [ ] **Startup Sequence**: Issue `start`, verify valve alignment → pump start → BS&W check → transition to RUNNING
- [ ] **Normal Operation**: Verify flow rate, temperature, pressure readings are reasonable
- [ ] **BS&W Divert**: Use `sim_bsw 1.5` to trigger divert, verify valve moves to DIVERT, verify return when BS&W drops
- [ ] **Sampling**: Verify sample solenoid cycles during RUNNING, stops during DIVERT
- [ ] **Normal Shutdown**: Issue `stop`, verify orderly sequence
- [ ] **E-Stop**: Press E-Stop, verify immediate halt, all outputs off, alarm active
- [ ] **E-Stop Recovery**: Release E-Stop, verify return to IDLE
- [ ] **Pump Overload**: Trigger overload, verify pump stops, lockout period enforced
- [ ] **Pressure Alarms**: Simulate low/high pressure, verify alarm activates and correct response
- [ ] **Temperature Alarms**: Verify high/low temperature alarms
- [ ] **Strainer DP Alarm**: Verify alarm on high differential pressure

### Phase 4: Meter Proving

- [ ] Connect certified pipe prover to prover connections
- [ ] Open proving tee ball valves
- [ ] Issue `prove` command
- [ ] Verify prover DBB valve opens
- [ ] Complete required proving runs (default 5)
- [ ] Verify repeatability < 0.05%
- [ ] Verify meter factor within range (0.9800 - 1.0200)
- [ ] Record new meter factor
- [ ] Close prover connections, replace dust covers

### Phase 5: API Compliance Verification

- [ ] Sample probe draws from middle third of flow (API MPMS Ch. 8)
- [ ] Sample frequency is flow-proportional
- [ ] Temperature correction uses API MPMS Ch. 11.1 (CTL at 60°F base)
- [ ] Test thermowell within API-specified distance downstream of meter
- [ ] Proving repeatability meets API MPMS Ch. 4 requirements
- [ ] BS&W divert setpoint appropriate for crude grade (typically 1.0%)

## Adding New Tests

When modifying the control logic, add corresponding tests:

```python
# tests/test_new_feature.py
import pytest
from plc.core.data_store import DataStore
from plc.config.setpoints import Setpoints

class TestNewFeature:
    @pytest.fixture
    def setup(self, data_store, setpoints):
        # Use shared fixtures from conftest.py
        return MyModule(data_store, setpoints)

    def test_expected_behavior(self, setup, data_store):
        data_store.write("SOME_INPUT", some_value)
        setup.execute()
        assert data_store.read("EXPECTED_OUTPUT") == expected
```

All fixtures (data_store, setpoints, controller, simulator, etc.) are
defined in `tests/conftest.py` and available to all test files.
