"""Tests for the topological flow graph system."""

import pytest
from plc.fleet.flow_graph import (
    FlowGraph, FlowNode, FlowEdge, FlowPath, NodeType,
    build_flow_graph,
)
from plc.fleet.unit_profile import UnitProfile, ComponentSelection


def _make_profile(**kwargs) -> UnitProfile:
    comp_kwargs = {
        "meter_key": "smith_e3s1_3in",
        "pump_key": "generic_centrifugal_480v",
        "divert_valve_key": "hydromatic_3in",
        "bsw_probe_key": "phase_dynamics_4528",
        "sampler_key": "clay_bailey_15gal",
        "prover_key": "none",
    }
    comp_kwargs.update(kwargs)
    return UnitProfile(
        unit_id="TEST-GRAPH",
        pipe_size=3.0,
        components=ComponentSelection(**comp_kwargs),
    )


class TestFlowGraphBasics:
    def test_empty_graph(self):
        graph = FlowGraph("empty")
        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0

    def test_add_node(self):
        graph = FlowGraph()
        node = FlowNode("n1", NodeType.PUMP, "Test Pump")
        graph.add_node(node)
        assert "n1" in graph.nodes
        assert graph.nodes["n1"].label == "Test Pump"

    def test_add_edge(self):
        graph = FlowGraph()
        graph.add_node(FlowNode("n1", NodeType.PUMP, "Pump"))
        graph.add_node(FlowNode("n2", NodeType.METER, "Meter"))
        graph.add_edge(FlowEdge("n1", "n2", FlowPath.MAIN))
        assert len(graph.edges) == 1

    def test_get_downstream(self):
        graph = FlowGraph()
        graph.add_node(FlowNode("n1", NodeType.PUMP, "Pump"))
        graph.add_node(FlowNode("n2", NodeType.METER, "Meter"))
        graph.add_edge(FlowEdge("n1", "n2", FlowPath.MAIN))
        downstream = graph.get_downstream("n1")
        assert len(downstream) == 1
        assert downstream[0].node_id == "n2"

    def test_get_upstream(self):
        graph = FlowGraph()
        graph.add_node(FlowNode("n1", NodeType.PUMP, "Pump"))
        graph.add_node(FlowNode("n2", NodeType.METER, "Meter"))
        graph.add_edge(FlowEdge("n1", "n2", FlowPath.MAIN))
        upstream = graph.get_upstream("n2")
        assert len(upstream) == 1
        assert upstream[0].node_id == "n1"

    def test_trace_path(self):
        graph = FlowGraph()
        graph.add_node(FlowNode("a", NodeType.INLET_VALVE, "Inlet"))
        graph.add_node(FlowNode("b", NodeType.PUMP, "Pump"))
        graph.add_node(FlowNode("c", NodeType.METER, "Meter"))
        graph.add_edge(FlowEdge("a", "b", FlowPath.MAIN))
        graph.add_edge(FlowEdge("b", "c", FlowPath.MAIN))
        path = graph.trace_path("a", "c")
        assert path == ["a", "b", "c"]

    def test_trace_no_path(self):
        graph = FlowGraph()
        graph.add_node(FlowNode("a", NodeType.INLET_VALVE, "Inlet"))
        graph.add_node(FlowNode("b", NodeType.METER, "Meter"))
        # No edge between them
        path = graph.trace_path("a", "b")
        assert path == []


class TestFlowGraphValidation:
    def test_validate_complete_graph(self):
        profile = _make_profile()
        graph = build_flow_graph(profile)
        issues = graph.validate()
        assert len(issues) == 0, f"Unexpected issues: {issues}"

    def test_validate_missing_required_node(self):
        graph = FlowGraph()
        graph.add_node(FlowNode("n1", NodeType.INLET_VALVE, "Inlet"))
        # Missing pump, divert, meter
        issues = graph.validate()
        assert len(issues) > 0
        assert any("Missing required" in i for i in issues)

    def test_validate_isolated_node(self):
        graph = FlowGraph()
        graph.add_node(FlowNode("n1", NodeType.INLET_VALVE, "Inlet"))
        graph.add_node(FlowNode("n2", NodeType.PUMP, "Pump"))
        graph.add_node(FlowNode("n3", NodeType.DIVERT_VALVE, "Divert"))
        graph.add_node(FlowNode("n4", NodeType.METER, "Meter"))
        graph.add_edge(FlowEdge("n1", "n2", FlowPath.MAIN))
        # n3 and n4 are isolated
        issues = graph.validate()
        assert any("Isolated" in i for i in issues)


class TestBuildFlowGraph:
    def test_builds_from_profile(self):
        profile = _make_profile()
        graph = build_flow_graph(profile)
        assert len(graph.nodes) > 10
        assert len(graph.edges) > 10

    def test_has_inlet_and_outlet(self):
        profile = _make_profile()
        graph = build_flow_graph(profile)
        types = {n.node_type for n in graph.nodes.values()}
        assert NodeType.INLET_VALVE in types
        assert NodeType.OUTLET_VALVE in types

    def test_has_sales_and_divert_paths(self):
        profile = _make_profile()
        graph = build_flow_graph(profile)
        edge_paths = {e.path for e in graph.edges}
        assert FlowPath.MAIN in edge_paths
        assert FlowPath.SALES in edge_paths
        assert FlowPath.DIVERT in edge_paths

    def test_inlet_to_meter_path_exists(self):
        profile = _make_profile()
        graph = build_flow_graph(profile)
        inlet = [n for n in graph.nodes.values() if n.node_type == NodeType.INLET_VALVE][0]
        meter = [n for n in graph.nodes.values() if n.node_type == NodeType.METER][0]
        path = graph.trace_path(inlet.node_id, meter.node_id)
        assert len(path) > 2

    def test_without_strainer(self):
        profile = _make_profile(has_strainer=False)
        graph = build_flow_graph(profile)
        types = {n.node_type for n in graph.nodes.values()}
        assert NodeType.STRAINER not in types

    def test_without_air_eliminator(self):
        profile = _make_profile(has_air_eliminator=False)
        graph = build_flow_graph(profile)
        types = {n.node_type for n in graph.nodes.values()}
        assert NodeType.AIR_ELIMINATOR not in types

    def test_with_prover(self):
        profile = _make_profile(prover_key="portable_pipe")
        graph = build_flow_graph(profile)
        types = {n.node_type for n in graph.nodes.values()}
        assert NodeType.PROVER_TEE in types

    def test_io_tags_on_nodes(self):
        profile = _make_profile()
        graph = build_flow_graph(profile)
        pump_nodes = [n for n in graph.nodes.values() if n.node_type == NodeType.PUMP]
        assert len(pump_nodes) == 1
        assert "DO_PUMP_START" in pump_nodes[0].io_tags

    def test_ascii_representation(self):
        profile = _make_profile()
        graph = build_flow_graph(profile)
        ascii_art = graph.to_ascii()
        assert "Flow Graph" in ascii_art
        assert len(ascii_art) > 50


class TestFlowGraphComparison:
    def test_compare_identical_units(self):
        profile_a = _make_profile()
        profile_b = _make_profile()
        graph_a = build_flow_graph(profile_a)
        graph_b = build_flow_graph(profile_b)
        diff = graph_a.compare(graph_b)
        assert diff["topologically_equivalent"] is True
        assert diff["self_node_count"] == diff["other_node_count"]

    def test_compare_different_units(self):
        profile_a = _make_profile()
        profile_b = _make_profile(has_strainer=False, has_air_eliminator=False)
        graph_a = build_flow_graph(profile_a)
        graph_b = build_flow_graph(profile_b)
        diff = graph_a.compare(graph_b)
        assert diff["topologically_equivalent"] is False
        assert diff["self_node_count"] > diff["other_node_count"]
