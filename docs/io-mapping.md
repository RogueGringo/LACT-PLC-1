# I/O Point Mapping

Complete I/O mapping for the SCS Technologies 3" LACT unit.
All signals interface via Modbus RTU/TCP expansion modules.

## Digital Inputs (13 points)

| Tag | Addr | Description | Signal |
|---|---|---|---|
| DI_INLET_VLV_OPEN | 0 | Inlet 3" ball valve open limit switch | 24VDC NC |
| DI_INLET_VLV_CLOSED | 1 | Inlet 3" ball valve closed limit switch | 24VDC NC |
| DI_STRAINER_HI_DP | 2 | Strainer high diff. pressure switch (4-mesh) | 24VDC NO |
| DI_PUMP_RUNNING | 3 | Transfer pump motor running (aux contact) | 24VDC NO |
| DI_PUMP_OVERLOAD | 4 | Transfer pump overload relay trip | 24VDC NC |
| DI_DIVERT_SALES | 5 | Divert valve at SALES position | 24VDC NO |
| DI_DIVERT_DIVERT | 6 | Divert valve at DIVERT position | 24VDC NO |
| DI_SAMPLE_POT_HI | 7 | Sample pot high level (15/20 gal) | 24VDC NO |
| DI_SAMPLE_POT_LO | 8 | Sample pot low level | 24VDC NC |
| DI_PROVER_VLV_OPEN | 9 | Franklin DuraSeal DBB prover valve open | 24VDC NO |
| DI_AIR_ELIM_FLOAT | 10 | Air eliminator float switch (gas present) | 24VDC NO |
| DI_OUTLET_VLV_OPEN | 11 | Outlet 3" ball valve open limit switch | 24VDC NC |
| DI_ESTOP | 12 | Emergency stop pushbutton | 24VDC NC |

## Digital Outputs (8 points)

| Tag | Addr | Description | Load |
|---|---|---|---|
| DO_PUMP_START | 0 | Transfer pump contactor coil | 480V starter |
| DO_DIVERT_CMD | 1 | Divert valve command (0=SALES, 1=DIVERT) | 120VAC coil |
| DO_SAMPLE_SOL | 2 | Sample 3-way solenoid valve | 120VAC XP coil |
| DO_SAMPLE_MIX_PUMP | 3 | Sample pot mixing pump | 120VAC motor |
| DO_PROVER_VLV_CMD | 4 | Prover DBB valve open command | 120VAC coil |
| DO_ALARM_BEACON | 5 | Visual alarm beacon | 24VDC |
| DO_ALARM_HORN | 6 | Audible alarm horn | 24VDC |
| DO_STATUS_GREEN | 7 | Running status light (green) | 24VDC |

## Analog Inputs (7 points, 4-20mA, 12-bit)

| Tag | Addr | Description | Range | Unit |
|---|---|---|---|---|
| AI_INLET_PRESS | 0 | Inlet pressure transmitter | 0-300 | PSI |
| AI_LOOP_HI_PRESS | 1 | Loop high-point pressure | 0-300 | PSI |
| AI_STRAINER_DP | 2 | Strainer differential pressure | 0-50 | PSI |
| AI_BSW_PROBE | 3 | BS&W capacitance probe (4528-5) | 0-5 | % |
| AI_METER_TEMP | 4 | TA probe in Smith E3-S1 meter | -20 to 200 | °F |
| AI_TEST_THERMO | 5 | Test thermowell downstream of meter | -20 to 200 | °F |
| AI_OUTLET_PRESS | 6 | Outlet pressure transmitter | 0-300 | PSI |

## Pulse Inputs (1 point)

| Tag | Addr | Description | Signal |
|---|---|---|---|
| PI_METER_PULSE | 0 | Smith E3-S1 meter pulse output | 24VDC pulse |

K-factor (pulses per barrel) is calibrated during proving and stored
as the `meter_k_factor` setpoint.

## Analog Outputs (2 points, 4-20mA)

| Tag | Addr | Description | Range | Unit |
|---|---|---|---|---|
| AO_BP_SALES_SP | 0 | Backpressure valve setpoint - sales | 0-150 | PSI |
| AO_BP_DIVERT_SP | 1 | Backpressure valve setpoint - divert | 0-150 | PSI |

## Modbus Register Map

| Register Range | Type | Description |
|---|---|---|
| 0-12 | Discrete Inputs | Digital inputs |
| 100-107 | Coils | Digital outputs |
| 200-206 | Input Registers | Analog inputs (raw 0-4095) |
| 300 | Input Register | Pulse counter |
| 400-401 | Holding Registers | Analog outputs (raw 0-4095) |

## Wiring Notes

- All 4-20mA signals require 250Ω sense resistors if using voltage-input ADC modules
- The BS&W probe (4528-5 detector card) outputs 4-20mA proportional to 0-5% BS&W
- The E-Stop uses NC (Normally Closed) wiring: wire break = E-Stop active
- The pump overload uses NC contacts: relay trip = contact opens = overload detected
- The sample solenoid requires XP (explosion-proof) rated 120VAC supply
- The transfer pump requires 480VAC 3-phase motor starter with overload relay
