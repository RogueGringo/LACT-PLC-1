"""
LACT Component Library
========================
Catalog of known LACT components — meters, pumps, valves,
probes, samplers, and their standard I/O signatures. This
library enables automatic configuration generation when a
unit's components are identified (via photos, nameplate data,
or manual selection).

Each component type defines:
  - Standard variants available on the market
  - Default operating parameters
  - Required I/O points (signals that must exist)
  - Optional I/O points (signals that may exist)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ── Enums ────────────────────────────────────────────────────

class MeterType(Enum):
    PD = "positive_displacement"
    TURBINE = "turbine"
    CORIOLIS = "coriolis"
    ULTRASONIC = "ultrasonic"


class PumpType(Enum):
    CENTRIFUGAL = "centrifugal"
    GEAR = "gear"
    SCREW = "screw"
    PROGRESSIVE_CAVITY = "progressive_cavity"


class ValveType(Enum):
    BALL = "ball"
    PLUG = "plug"
    BUTTERFLY = "butterfly"
    GATE = "gate"


class DivertType(Enum):
    HYDROMATIC = "hydromatic"
    PNEUMATIC = "pneumatic"
    ELECTRIC_BALL = "electric_ball"


class ProbeType(Enum):
    CAPACITANCE = "capacitance"
    MICROWAVE = "microwave"
    OPTICAL = "optical"


class SamplerType(Enum):
    SOLENOID = "solenoid"
    PISTON = "piston"
    COMPOSITE = "composite"


class ProverType(Enum):
    PIPE = "pipe"
    COMPACT = "compact"
    MASTER_METER = "master_meter"


class PowerRating(Enum):
    V24DC = "24VDC"
    V120AC = "120VAC"
    V240AC = "240VAC"
    V480AC_1PH = "480VAC_1PH"
    V480AC_3PH = "480VAC_3PH"


# ── Component Definitions ────────────────────────────────────

@dataclass(frozen=True)
class IOSignature:
    """Defines what I/O signals a component needs."""
    digital_inputs: tuple = ()   # Tag name templates
    digital_outputs: tuple = ()
    analog_inputs: tuple = ()
    analog_outputs: tuple = ()
    pulse_inputs: tuple = ()


@dataclass(frozen=True)
class MeterSpec:
    """Positive displacement or turbine flow meter."""
    manufacturer: str
    model: str
    meter_type: MeterType
    size_inches: float
    min_flow_bph: float
    max_flow_bph: float
    k_factor_default: float  # pulses per barrel
    has_temperature_probe: bool = True
    has_pulse_output: bool = True
    io_signature: IOSignature = IOSignature(
        analog_inputs=("AI_METER_TEMP",),
        pulse_inputs=("PI_METER_PULSE",),
    )

    @property
    def display_name(self) -> str:
        return f"{self.manufacturer} {self.model} ({self.size_inches}\")"


@dataclass(frozen=True)
class PumpSpec:
    """Transfer pump specification."""
    manufacturer: str
    model: str
    pump_type: PumpType
    power: PowerRating
    hp: float
    max_flow_bph: float
    max_pressure_psi: float
    io_signature: IOSignature = IOSignature(
        digital_inputs=("DI_PUMP_RUNNING", "DI_PUMP_OVERLOAD"),
        digital_outputs=("DO_PUMP_START",),
    )


@dataclass(frozen=True)
class DivertValveSpec:
    """Divert valve (sales/reject routing)."""
    manufacturer: str
    model: str
    valve_type: DivertType
    size_inches: float
    travel_time_sec: float = 10.0
    power: PowerRating = PowerRating.V120AC
    io_signature: IOSignature = IOSignature(
        digital_inputs=("DI_DIVERT_SALES", "DI_DIVERT_DIVERT"),
        digital_outputs=("DO_DIVERT_CMD",),
    )


@dataclass(frozen=True)
class BSWProbeSpec:
    """BS&W probe specification."""
    manufacturer: str
    model: str
    probe_type: ProbeType
    range_pct: float = 5.0
    output_ma: str = "4-20"
    io_signature: IOSignature = IOSignature(
        analog_inputs=("AI_BSW_PROBE",),
    )


@dataclass(frozen=True)
class SamplerSpec:
    """Sampler system specification."""
    manufacturer: str
    model: str
    sampler_type: SamplerType
    pot_size_gal: float
    power: PowerRating = PowerRating.V120AC
    has_mixing_pump: bool = True
    io_signature: IOSignature = IOSignature(
        digital_inputs=("DI_SAMPLE_POT_HI", "DI_SAMPLE_POT_LO"),
        digital_outputs=("DO_SAMPLE_SOL", "DO_SAMPLE_MIX_PUMP"),
    )


@dataclass(frozen=True)
class ProverSpec:
    """Meter prover specification."""
    manufacturer: str
    model: str
    prover_type: ProverType
    volume_bbl: float = 0.0
    io_signature: IOSignature = IOSignature(
        digital_inputs=("DI_PROVER_VLV_OPEN",),
        digital_outputs=("DO_PROVER_VLV_CMD",),
    )


@dataclass(frozen=True)
class BackpressureValveSpec:
    """Backpressure control valve."""
    manufacturer: str
    model: str
    size_inches: float
    max_pressure_psi: float = 150.0
    io_signature: IOSignature = IOSignature(
        analog_outputs=("AO_BP_SP",),
    )


@dataclass(frozen=True)
class PressureTransmitterSpec:
    """Pressure transmitter."""
    manufacturer: str
    model: str
    range_psi: float
    output_ma: str = "4-20"


@dataclass(frozen=True)
class StrainerSpec:
    """Inlet strainer."""
    manufacturer: str
    model: str
    mesh_size: int = 4
    size_inches: float = 3.0
    has_dp_switch: bool = True
    has_dp_transmitter: bool = False
    io_signature: IOSignature = IOSignature(
        digital_inputs=("DI_STRAINER_HI_DP",),
    )


# ── Known Component Database ─────────────────────────────────

KNOWN_METERS = {
    "smith_e3s1_3in": MeterSpec(
        manufacturer="Smith",
        model="E3-S1",
        meter_type=MeterType.PD,
        size_inches=3.0,
        min_flow_bph=30.0,
        max_flow_bph=750.0,
        k_factor_default=100.0,
    ),
    "smith_e3s1_4in": MeterSpec(
        manufacturer="Smith",
        model="E3-S1",
        meter_type=MeterType.PD,
        size_inches=4.0,
        min_flow_bph=50.0,
        max_flow_bph=1500.0,
        k_factor_default=50.0,
    ),
    "smith_g6_2in": MeterSpec(
        manufacturer="Smith",
        model="G6",
        meter_type=MeterType.PD,
        size_inches=2.0,
        min_flow_bph=15.0,
        max_flow_bph=400.0,
        k_factor_default=200.0,
    ),
    "totalflow_7150_3in": MeterSpec(
        manufacturer="Totalflow",
        model="7150",
        meter_type=MeterType.TURBINE,
        size_inches=3.0,
        min_flow_bph=50.0,
        max_flow_bph=1200.0,
        k_factor_default=85.0,
    ),
    "brooks_bm07_3in": MeterSpec(
        manufacturer="Brooks",
        model="BM07",
        meter_type=MeterType.PD,
        size_inches=3.0,
        min_flow_bph=25.0,
        max_flow_bph=700.0,
        k_factor_default=120.0,
    ),
}

KNOWN_PUMPS = {
    "generic_centrifugal_480v": PumpSpec(
        manufacturer="Generic",
        model="ANSI Centrifugal",
        pump_type=PumpType.CENTRIFUGAL,
        power=PowerRating.V480AC_3PH,
        hp=10.0,
        max_flow_bph=800.0,
        max_pressure_psi=150.0,
    ),
    "viking_gear_480v": PumpSpec(
        manufacturer="Viking",
        model="HL4195",
        pump_type=PumpType.GEAR,
        power=PowerRating.V480AC_3PH,
        hp=7.5,
        max_flow_bph=500.0,
        max_pressure_psi=200.0,
    ),
}

KNOWN_DIVERT_VALVES = {
    "hydromatic_3in": DivertValveSpec(
        manufacturer="Hydromatic",
        model="3\" Electric",
        valve_type=DivertType.HYDROMATIC,
        size_inches=3.0,
        travel_time_sec=10.0,
        power=PowerRating.V120AC,
    ),
    "hydromatic_4in": DivertValveSpec(
        manufacturer="Hydromatic",
        model="4\" Electric",
        valve_type=DivertType.HYDROMATIC,
        size_inches=4.0,
        travel_time_sec=12.0,
        power=PowerRating.V120AC,
    ),
    "pneumatic_3in": DivertValveSpec(
        manufacturer="Generic",
        model="3\" Pneumatic",
        valve_type=DivertType.PNEUMATIC,
        size_inches=3.0,
        travel_time_sec=5.0,
    ),
}

KNOWN_BSW_PROBES = {
    "phase_dynamics_4528": BSWProbeSpec(
        manufacturer="Phase Dynamics",
        model="4528-5",
        probe_type=ProbeType.CAPACITANCE,
        range_pct=5.0,
    ),
    "phase_dynamics_analyzer": BSWProbeSpec(
        manufacturer="Phase Dynamics",
        model="Analyzer",
        probe_type=ProbeType.MICROWAVE,
        range_pct=10.0,
    ),
}

KNOWN_SAMPLERS = {
    "clay_bailey_15gal": SamplerSpec(
        manufacturer="Clay Bailey",
        model="15/20 gal",
        sampler_type=SamplerType.SOLENOID,
        pot_size_gal=15.0,
        has_mixing_pump=True,
    ),
    "clay_bailey_5gal": SamplerSpec(
        manufacturer="Clay Bailey",
        model="5 gal",
        sampler_type=SamplerType.SOLENOID,
        pot_size_gal=5.0,
        has_mixing_pump=False,
    ),
    "welker_piston": SamplerSpec(
        manufacturer="Welker",
        model="CP-8M",
        sampler_type=SamplerType.PISTON,
        pot_size_gal=20.0,
        has_mixing_pump=True,
    ),
}

KNOWN_PROVERS = {
    "none": ProverSpec(
        manufacturer="None",
        model="No Prover",
        prover_type=ProverType.PIPE,
        volume_bbl=0.0,
        io_signature=IOSignature(),
    ),
    "portable_pipe": ProverSpec(
        manufacturer="Generic",
        model="Portable Pipe Prover",
        prover_type=ProverType.PIPE,
        volume_bbl=10.0,
    ),
    "compact_prover": ProverSpec(
        manufacturer="Smith",
        model="Compact Prover",
        prover_type=ProverType.COMPACT,
        volume_bbl=0.5,
    ),
}


def search_components(query: str) -> dict:
    """Search all component catalogs for a match."""
    query_lower = query.lower()
    results = {}
    catalogs = {
        "meters": KNOWN_METERS,
        "pumps": KNOWN_PUMPS,
        "divert_valves": KNOWN_DIVERT_VALVES,
        "bsw_probes": KNOWN_BSW_PROBES,
        "samplers": KNOWN_SAMPLERS,
        "provers": KNOWN_PROVERS,
    }
    for cat_name, catalog in catalogs.items():
        for key, spec in catalog.items():
            searchable = f"{key} {spec.manufacturer} {spec.model}".lower()
            if query_lower in searchable:
                results.setdefault(cat_name, {})[key] = spec
    return results
