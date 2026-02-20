"""Tests for the LACT component library."""

import pytest
from plc.fleet.components import (
    KNOWN_METERS, KNOWN_PUMPS, KNOWN_DIVERT_VALVES,
    KNOWN_BSW_PROBES, KNOWN_SAMPLERS, KNOWN_PROVERS,
    MeterSpec, PumpSpec, MeterType, PumpType,
    search_components,
)


class TestComponentLibrary:
    def test_known_meters_populated(self):
        assert len(KNOWN_METERS) >= 4
        assert "smith_e3s1_3in" in KNOWN_METERS

    def test_smith_e3s1_3in_specs(self):
        meter = KNOWN_METERS["smith_e3s1_3in"]
        assert meter.manufacturer == "Smith"
        assert meter.model == "E3-S1"
        assert meter.meter_type == MeterType.PD
        assert meter.size_inches == 3.0
        assert meter.k_factor_default == 100.0
        assert meter.min_flow_bph == 30.0
        assert meter.max_flow_bph == 750.0

    def test_meter_display_name(self):
        meter = KNOWN_METERS["smith_e3s1_3in"]
        assert "Smith" in meter.display_name
        assert "E3-S1" in meter.display_name
        assert '3.0"' in meter.display_name

    def test_known_pumps_populated(self):
        assert len(KNOWN_PUMPS) >= 2
        assert "generic_centrifugal_480v" in KNOWN_PUMPS

    def test_known_divert_valves_populated(self):
        assert len(KNOWN_DIVERT_VALVES) >= 2
        assert "hydromatic_3in" in KNOWN_DIVERT_VALVES

    def test_known_bsw_probes_populated(self):
        assert len(KNOWN_BSW_PROBES) >= 1
        assert "phase_dynamics_4528" in KNOWN_BSW_PROBES

    def test_known_samplers_populated(self):
        assert len(KNOWN_SAMPLERS) >= 2
        assert "clay_bailey_15gal" in KNOWN_SAMPLERS

    def test_known_provers_includes_none(self):
        assert "none" in KNOWN_PROVERS
        none_prover = KNOWN_PROVERS["none"]
        assert not none_prover.io_signature.digital_inputs

    def test_search_by_manufacturer(self):
        results = search_components("Smith")
        assert "meters" in results
        assert len(results["meters"]) >= 2

    def test_search_by_model(self):
        results = search_components("4528")
        assert "bsw_probes" in results
        assert "phase_dynamics_4528" in results["bsw_probes"]

    def test_search_case_insensitive(self):
        results = search_components("smith")
        assert "meters" in results

    def test_search_no_results(self):
        results = search_components("nonexistent_component_xyz")
        assert len(results) == 0

    def test_io_signature_on_meter(self):
        meter = KNOWN_METERS["smith_e3s1_3in"]
        assert "AI_METER_TEMP" in meter.io_signature.analog_inputs
        assert "PI_METER_PULSE" in meter.io_signature.pulse_inputs

    def test_io_signature_on_pump(self):
        pump = KNOWN_PUMPS["generic_centrifugal_480v"]
        assert "DI_PUMP_RUNNING" in pump.io_signature.digital_inputs
        assert "DO_PUMP_START" in pump.io_signature.digital_outputs
