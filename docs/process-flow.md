# Process Flow Description

## LACT Unit Process Flow Diagram

```
                          ┌─────────────┐
                          │  INLET      │
                          │  Ball Valve  │ ← DI_INLET_VLV_OPEN
                          └──────┬──────┘
                                 │
                          ┌──────▼──────┐
    AI_STRAINER_DP ──────►│  STRAINER   │ ← DI_STRAINER_HI_DP
                          │  (4 mesh)   │
                          └──────┬──────┘
                                 │
                          ┌──────▼──────┐
    DO_PUMP_START ───────►│  TRANSFER   │ ← DI_PUMP_RUNNING
    DI_PUMP_OVERLOAD ────►│  PUMP       │    DI_PUMP_OVERLOAD
                          │  480V 3-ph  │
                          └──────┬──────┘
                                 │
                          ┌──────▼──────┐
    AI_BSW_PROBE ────────►│  BS&W PROBE │  (vertical riser)
                          │  Cap. 4528-5│
                          └──────┬──────┘
                                 │
    AI_LOOP_HI_PRESS ───►┌──────▼──────┐
    DI_AIR_ELIM_FLOAT ──►│  AIR ELIM.  │  (loop high point)
                          │  + Press.   │
                          └──────┬──────┘
                                 │ (vertical downcomer)
                          ┌──────▼──────┐
                          │STATIC MIXER │
                          │  Dual elem. │
                          └──────┬──────┘
                                 │
    DO_SAMPLE_SOL ──────►┌──────▼──────┐
    DO_SAMPLE_MIX_PUMP ─►│  SAMPLER    │ ← DI_SAMPLE_POT_HI
                          │  15/20 gal  │   DI_SAMPLE_POT_LO
                          │  Clay Bailey│
                          └──────┬──────┘
                                 │
    DO_DIVERT_CMD ──────►┌──────▼──────┐
                          │  DIVERT     │ ← DI_DIVERT_SALES
                          │  VALVE      │   DI_DIVERT_DIVERT
                          │  Hydromatic │
                          └──┬─────┬───┘
                    SALES    │     │   DIVERT
                    ┌────────▼┐   ┌▼────────┐
                    │         │   │         │
              ┌─────▼─────┐   │   │  ┌──────▼──────┐
    PI_METER ►│ PD METER  │   │   │  │ BACKPRESS.  │◄ AO_BP_DIVERT_SP
    AI_TEMP  ►│ Smith     │   │   │  │ VALVE       │
              │ E3-S1     │   │   │  └──────┬──────┘
              └─────┬─────┘   │   │         │
                    │         │   │  ┌──────▼──────┐
    AI_TEST ───────►│ Thermo  │   │  │CHECK VALVE  │
                    │  well   │   │  └──────┬──────┘
                    │         │   │         │
    DO_PROVER ────►┌▼────────┐│   │         │
                   │PROVER   ││   │    DIVERT LINE
                   │DBB Valve││   │    (to tank)
                   │Cam Lock ││   │
                   └─────────┘│   │
                    │         │   │
              ┌─────▼─────┐   │
              │BACKPRESS. │◄──┘ AO_BP_SALES_SP
              │ VALVE     │
              └─────┬─────┘
                    │
              ┌─────▼─────┐
              │CHECK VALVE │
              └─────┬─────┘
                    │
              ┌─────▼─────┐
              │  OUTLET    │ ← DI_OUTLET_VLV_OPEN
              │  Ball Valve│
              └────────────┘
                 SALES LINE
                 (to pipeline)
```

## Custody Transfer Sequence

### Normal Operation

1. Operator issues **START** command via CLI/TUI
2. System enters **STARTUP** state:
   - Verifies inlet and outlet ball valves are open
   - Commands divert valve to DIVERT position (safe start)
   - Waits for divert valve position confirmation
   - Starts transfer pump motor (480V contactor)
   - Verifies pump running feedback
   - Waits for BS&W probe stabilization
   - If BS&W < divert setpoint → switches to SALES, enters **RUNNING**
3. In **RUNNING** state:
   - Pump maintains flow through metering loop
   - BS&W continuously monitored
   - Flow-proportional sampling activated per API MPMS Ch. 8
   - Meter pulses accumulated for volume totalization
   - Temperature correction (CTL) applied per API MPMS Ch. 11.1
   - Batch totals updated each scan cycle

### BS&W Diversion

When the BS&W capacitance probe detects water content above the divert
setpoint (default 1.0%), after a configurable debounce delay:

1. ALM_BSW_DIVERT alarm activates
2. State machine transitions to **DIVERT**
3. Divert valve commands to DIVERT position
4. Sampling pauses (only clean oil is sampled)
5. Flow continues through divert line back to tank
6. When BS&W drops below setpoint, after delay:
   - Divert valve returns to SALES
   - State returns to **RUNNING**
   - Sampling resumes

### Meter Proving

When operator issues **PROVE** command:

1. State transitions to **PROVING**
2. Prover DBB valve opens
3. Multiple proving runs execute (default 5)
4. For each run: meter pulses counted against known prover volume
5. Repeatability checked between runs (default 0.05%)
6. If within tolerance: new meter factor applied
7. If fails: alarm raised, old factor retained
8. State returns to **RUNNING**

### Shutdown

When operator issues **STOP** command:

1. State transitions to **SHUTDOWN**
2. Divert valve switches to DIVERT
3. Sampler deactivates
4. Transfer pump stops
5. After pump stop confirmed → state returns to **IDLE**

### Emergency Stop

E-Stop is handled immediately from any state:

1. All outputs forced off (pump, sampler, prover valve)
2. Divert valve commanded to DIVERT (fail-safe)
3. Alarm beacon and horn activated
4. State enters **E_STOP**
5. After E-Stop button released and debounce: returns to **IDLE**
