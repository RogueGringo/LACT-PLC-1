"""
Topological Flow Graph
========================
Models the LACT unit process flow as a directed graph.
Each node represents a piece of equipment, each edge
represents a flow path between equipment.

This enables:
  - Automated flow path validation
  - Simulation of fluid routing (sales vs divert)
  - Visualization of the process
  - Topological comparison between different units
  - Detection of flow-path anomalies

Based on the Reverse Engineering Topological Abstraction
methodology: extract the system's connectivity structure,
then reason about it independently of implementation.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class NodeType(Enum):
    """Types of equipment nodes in the flow graph."""
    INLET_VALVE = "inlet_valve"
    STRAINER = "strainer"
    PUMP = "pump"
    BSW_PROBE = "bsw_probe"
    AIR_ELIMINATOR = "air_eliminator"
    STATIC_MIXER = "static_mixer"
    SAMPLER = "sampler"
    DIVERT_VALVE = "divert_valve"
    METER = "meter"
    TEST_THERMOWELL = "test_thermowell"
    PROVER_TEE = "prover_tee"
    BACKPRESSURE_VALVE = "backpressure_valve"
    CHECK_VALVE = "check_valve"
    OUTLET_VALVE = "outlet_valve"
    TANK_RETURN = "tank_return"      # Divert line destination
    PIPELINE = "pipeline"             # Sales line destination
    JUNCTION = "junction"             # Flow path junction


class FlowPath(Enum):
    """Named flow paths through the unit."""
    MAIN = "main"            # Inlet → divert valve
    SALES = "sales"          # Divert valve → meter → outlet
    DIVERT = "divert"        # Divert valve → tank return
    PROVER = "prover"        # Off meter → prover → return


@dataclass
class FlowNode:
    """A single equipment node in the flow graph."""
    node_id: str
    node_type: NodeType
    label: str
    io_tags: list = field(default_factory=list)  # Associated I/O tags
    position: tuple = (0.0, 0.0)  # x, y for visualization
    properties: dict = field(default_factory=dict)


@dataclass
class FlowEdge:
    """A directed edge representing flow between nodes."""
    source: str         # node_id of upstream equipment
    target: str         # node_id of downstream equipment
    path: FlowPath      # Which flow path this edge belongs to
    pipe_size_in: float = 3.0
    label: str = ""


class FlowGraph:
    """
    Directed graph representation of a LACT unit's process flow.

    Nodes = equipment, Edges = flow paths.
    Supports flow path tracing, validation, and comparison.
    """

    def __init__(self, unit_id: str = ""):
        self.unit_id = unit_id
        self.nodes: dict = {}   # node_id → FlowNode
        self.edges: list = []   # FlowEdge list
        self._adjacency: dict = {}  # node_id → [FlowEdge]

    def add_node(self, node: FlowNode):
        """Add a node to the graph."""
        self.nodes[node.node_id] = node
        if node.node_id not in self._adjacency:
            self._adjacency[node.node_id] = []

    def add_edge(self, edge: FlowEdge):
        """Add a directed edge to the graph."""
        self.edges.append(edge)
        self._adjacency.setdefault(edge.source, []).append(edge)

    def get_downstream(self, node_id: str) -> list:
        """Get all nodes directly downstream of the given node."""
        edges = self._adjacency.get(node_id, [])
        return [self.nodes[e.target] for e in edges if e.target in self.nodes]

    def get_upstream(self, node_id: str) -> list:
        """Get all nodes directly upstream of the given node."""
        upstream = []
        for edge in self.edges:
            if edge.target == node_id and edge.source in self.nodes:
                upstream.append(self.nodes[edge.source])
        return upstream

    def trace_path(self, start: str, end: str) -> list:
        """
        Trace the flow path from start to end node.
        Returns list of node_ids in order, or empty list if
        no path exists.
        """
        visited = set()
        path = []

        def dfs(current):
            if current == end:
                path.append(current)
                return True
            if current in visited:
                return False
            visited.add(current)
            path.append(current)
            for edge in self._adjacency.get(current, []):
                if dfs(edge.target):
                    return True
            path.pop()
            return False

        dfs(start)
        return path

    def get_flow_path_nodes(self, flow_path: FlowPath) -> list:
        """Get all nodes on a specific flow path."""
        node_ids = set()
        for edge in self.edges:
            if edge.path == flow_path:
                node_ids.add(edge.source)
                node_ids.add(edge.target)
        # Return in topological order
        return [self.nodes[nid] for nid in self._topo_sort() if nid in node_ids]

    def validate(self) -> list:
        """
        Validate the flow graph structure.
        Returns list of issues found.
        """
        issues = []

        # Check for required node types
        node_types = {n.node_type for n in self.nodes.values()}
        required = {
            NodeType.INLET_VALVE,
            NodeType.PUMP,
            NodeType.DIVERT_VALVE,
            NodeType.METER,
        }
        missing = required - node_types
        if missing:
            issues.append(f"Missing required nodes: {[m.value for m in missing]}")

        # Check connectivity
        inlet_nodes = [n for n in self.nodes.values() if n.node_type == NodeType.INLET_VALVE]
        meter_nodes = [n for n in self.nodes.values() if n.node_type == NodeType.METER]
        if inlet_nodes and meter_nodes:
            path = self.trace_path(inlet_nodes[0].node_id, meter_nodes[0].node_id)
            if not path:
                issues.append("No flow path from inlet to meter")

        # Check for isolated nodes
        connected = set()
        for edge in self.edges:
            connected.add(edge.source)
            connected.add(edge.target)
        isolated = set(self.nodes.keys()) - connected
        if isolated:
            issues.append(f"Isolated nodes: {list(isolated)}")

        # Check that divert valve has both sales and divert paths
        divert_nodes = [n for n in self.nodes.values() if n.node_type == NodeType.DIVERT_VALVE]
        for dv in divert_nodes:
            downstream = self._adjacency.get(dv.node_id, [])
            paths = {e.path for e in downstream}
            if FlowPath.SALES not in paths:
                issues.append(f"Divert valve {dv.node_id} missing SALES path")
            if FlowPath.DIVERT not in paths:
                issues.append(f"Divert valve {dv.node_id} missing DIVERT path")

        return issues

    def _topo_sort(self) -> list:
        """Topological sort of nodes (Kahn's algorithm)."""
        in_degree = {nid: 0 for nid in self.nodes}
        for edge in self.edges:
            if edge.target in in_degree:
                in_degree[edge.target] += 1

        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node)
            for edge in self._adjacency.get(node, []):
                if edge.target in in_degree:
                    in_degree[edge.target] -= 1
                    if in_degree[edge.target] == 0:
                        queue.append(edge.target)

        return result

    def to_ascii(self) -> str:
        """
        Generate an ASCII representation of the flow graph.
        Shows the main flow path with branches for sales/divert.
        """
        sorted_nodes = self._topo_sort()
        if not sorted_nodes:
            return "(empty graph)"

        lines = []
        lines.append(f"Flow Graph: {self.unit_id}")
        lines.append("=" * 50)

        # Group by flow path
        main_path = self.get_flow_path_nodes(FlowPath.MAIN)
        sales_path = self.get_flow_path_nodes(FlowPath.SALES)
        divert_path = self.get_flow_path_nodes(FlowPath.DIVERT)

        for node in main_path:
            lines.append(f"  │")
            io_str = f" [{', '.join(node.io_tags)}]" if node.io_tags else ""
            lines.append(f"  ├─ {node.label}{io_str}")

        if sales_path or divert_path:
            lines.append(f"  │")
            lines.append(f"  ├── SALES ──────────┐  DIVERT ─────────┐")

            max_len = max(len(sales_path), len(divert_path))
            for i in range(max_len):
                sales_node = sales_path[i] if i < len(sales_path) else None
                divert_node = divert_path[i] if i < len(divert_path) else None

                s_text = f"{sales_node.label}" if sales_node else ""
                d_text = f"{divert_node.label}" if divert_node else ""
                lines.append(f"  │  {s_text:<20s}│  {d_text}")

        return "\n".join(lines)

    def compare(self, other: "FlowGraph") -> dict:
        """
        Compare this flow graph with another.
        Returns dict describing structural differences.
        """
        self_types = sorted(n.node_type.value for n in self.nodes.values())
        other_types = sorted(n.node_type.value for n in other.nodes.values())

        self_set = set(self_types)
        other_set = set(other_types)

        return {
            "nodes_only_in_self": list(self_set - other_set),
            "nodes_only_in_other": list(other_set - self_set),
            "nodes_in_both": list(self_set & other_set),
            "self_node_count": len(self.nodes),
            "other_node_count": len(other.nodes),
            "self_edge_count": len(self.edges),
            "other_edge_count": len(other.edges),
            "topologically_equivalent": self_types == other_types,
        }


# ── Graph Builder ─────────────────────────────────────────────

def build_flow_graph(profile) -> FlowGraph:
    """
    Build a FlowGraph from a UnitProfile.
    Auto-generates the standard LACT topology based on
    the unit's installed components.
    """
    from plc.fleet.components import (
        KNOWN_METERS, KNOWN_SAMPLERS, KNOWN_PROVERS,
    )

    graph = FlowGraph(unit_id=profile.unit_id)
    comp = profile.components
    pipe = profile.pipe_size

    # Node counter for unique IDs
    y_pos = 0.0
    step = 1.0

    def add(node_type, label, io_tags=None):
        nonlocal y_pos
        nid = f"{node_type.value}_{len(graph.nodes)}"
        node = FlowNode(
            node_id=nid,
            node_type=node_type,
            label=label,
            io_tags=io_tags or [],
            position=(0.0, y_pos),
        )
        graph.add_node(node)
        y_pos += step
        return nid

    # ── Build main flow path ─────────────────────────────────

    inlet_id = add(NodeType.INLET_VALVE, f"{pipe}\" Inlet Ball Valve",
                    ["DI_INLET_VLV_OPEN", "DI_INLET_VLV_CLOSED"])

    prev_id = inlet_id

    if comp.has_strainer:
        strainer_id = add(NodeType.STRAINER,
                          f"Strainer ({comp.strainer_mesh} mesh)",
                          ["DI_STRAINER_HI_DP", "AI_STRAINER_DP"])
        graph.add_edge(FlowEdge(prev_id, strainer_id, FlowPath.MAIN, pipe))
        prev_id = strainer_id

    pump_id = add(NodeType.PUMP, "Transfer Pump",
                  ["DO_PUMP_START", "DI_PUMP_RUNNING", "DI_PUMP_OVERLOAD"])
    graph.add_edge(FlowEdge(prev_id, pump_id, FlowPath.MAIN, pipe))
    prev_id = pump_id

    bsw_id = add(NodeType.BSW_PROBE, "BS&W Probe",
                  ["AI_BSW_PROBE"])
    graph.add_edge(FlowEdge(prev_id, bsw_id, FlowPath.MAIN, pipe))
    prev_id = bsw_id

    if comp.has_air_eliminator:
        air_id = add(NodeType.AIR_ELIMINATOR, "Air Eliminator",
                      ["DI_AIR_ELIM_FLOAT", "AI_LOOP_HI_PRESS"])
        graph.add_edge(FlowEdge(prev_id, air_id, FlowPath.MAIN, pipe))
        prev_id = air_id

    if comp.has_static_mixer:
        mixer_id = add(NodeType.STATIC_MIXER, "Static Mixer")
        graph.add_edge(FlowEdge(prev_id, mixer_id, FlowPath.MAIN, pipe))
        prev_id = mixer_id

    sampler = KNOWN_SAMPLERS.get(comp.sampler_key)
    if sampler:
        tags = ["DO_SAMPLE_SOL", "DI_SAMPLE_POT_HI", "DI_SAMPLE_POT_LO"]
        if sampler.has_mixing_pump:
            tags.append("DO_SAMPLE_MIX_PUMP")
        sampler_id = add(NodeType.SAMPLER, f"Sampler ({sampler.model})", tags)
        graph.add_edge(FlowEdge(prev_id, sampler_id, FlowPath.MAIN, pipe))
        prev_id = sampler_id

    # ── Divert valve (splits into sales and divert paths) ────
    divert_id = add(NodeType.DIVERT_VALVE, "Divert Valve",
                    ["DO_DIVERT_CMD", "DI_DIVERT_SALES", "DI_DIVERT_DIVERT"])
    graph.add_edge(FlowEdge(prev_id, divert_id, FlowPath.MAIN, pipe))

    # ── Sales path ───────────────────────────────────────────
    meter = KNOWN_METERS.get(comp.meter_key)
    meter_label = meter.display_name if meter else "PD Meter"
    meter_id = add(NodeType.METER, meter_label,
                   ["PI_METER_PULSE", "AI_METER_TEMP"])
    graph.add_edge(FlowEdge(divert_id, meter_id, FlowPath.SALES, pipe))

    sales_prev = meter_id

    if comp.has_test_thermowell:
        thermo_id = add(NodeType.TEST_THERMOWELL, "Test Thermowell",
                        ["AI_TEST_THERMO"])
        graph.add_edge(FlowEdge(sales_prev, thermo_id, FlowPath.SALES, pipe))
        sales_prev = thermo_id

    prover = KNOWN_PROVERS.get(comp.prover_key)
    if prover and prover.io_signature.digital_inputs:
        prover_id = add(NodeType.PROVER_TEE, f"Prover ({prover.model})",
                        ["DO_PROVER_VLV_CMD", "DI_PROVER_VLV_OPEN"])
        graph.add_edge(FlowEdge(sales_prev, prover_id, FlowPath.SALES, pipe))
        sales_prev = prover_id

    if comp.num_backpressure_valves >= 1:
        bp_sales_id = add(NodeType.BACKPRESSURE_VALVE, "BP Valve (Sales)",
                          ["AO_BP_SALES_SP"])
        graph.add_edge(FlowEdge(sales_prev, bp_sales_id, FlowPath.SALES, pipe))
        sales_prev = bp_sales_id

    check_sales_id = add(NodeType.CHECK_VALVE, "Check Valve (Sales)")
    graph.add_edge(FlowEdge(sales_prev, check_sales_id, FlowPath.SALES, pipe))

    outlet_id = add(NodeType.OUTLET_VALVE, f"{pipe}\" Outlet Ball Valve",
                    ["DI_OUTLET_VLV_OPEN"])
    graph.add_edge(FlowEdge(check_sales_id, outlet_id, FlowPath.SALES, pipe))

    pipeline_id = add(NodeType.PIPELINE, "Sales Pipeline")
    graph.add_edge(FlowEdge(outlet_id, pipeline_id, FlowPath.SALES, pipe))

    # ── Divert path ──────────────────────────────────────────
    if comp.num_backpressure_valves >= 2:
        bp_divert_id = add(NodeType.BACKPRESSURE_VALVE, "BP Valve (Divert)",
                           ["AO_BP_DIVERT_SP"])
        graph.add_edge(FlowEdge(divert_id, bp_divert_id, FlowPath.DIVERT, pipe))
        divert_prev = bp_divert_id
    else:
        divert_prev = divert_id

    check_divert_id = add(NodeType.CHECK_VALVE, "Check Valve (Divert)")
    graph.add_edge(FlowEdge(divert_prev, check_divert_id, FlowPath.DIVERT, pipe))

    tank_id = add(NodeType.TANK_RETURN, "Tank Return (Divert)")
    graph.add_edge(FlowEdge(check_divert_id, tank_id, FlowPath.DIVERT, pipe))

    return graph
