"""
Graph visualization exports (图谱可视化).

Renders a `NarrativeGraph` as Graphviz DOT or Mermaid so the audit result can
be *seen*: solid nodes are what the text stated, dashed nodes are what
ontology reasoning inferred, and ghost nodes are the gaps — required or
expected roles the ontology says should exist but the narrative never fills.

    dot = to_dot(state.graph, gaps=state.gaps)        # render with graphviz
    mmd = to_mermaid(state.graph, gaps=state.gaps)    # paste into mermaid.live

Both exporters are pure functions of the graph; nothing here touches an LLM.
"""

from __future__ import annotations

from collections.abc import Iterable

from .graph import (
    ROLE_RELATION_PREFIX,
    Gap,
    GapImportance,
    GraphEdge,
    GraphNode,
    NarrativeGraph,
    NodeStatus,
)

_GAP_NODE_PREFIX = "gap"


def _display_relation(relation: str) -> str:
    """Role edges read better without the internal `role:` prefix."""
    if relation.startswith(ROLE_RELATION_PREFIX):
        return relation[len(ROLE_RELATION_PREFIX) :]
    return relation


def _gap_label(gap: Gap) -> str:
    name = gap.role_zh or gap.role
    return f"缺失: {name}"


# ── Graphviz DOT ─────────────────────────────────────────────────────────────

_DOT_SHAPES = {"event": "box", "entity": "ellipse", "time": "note"}


def _dot_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _dot_node(node: GraphNode) -> str:
    shape = _DOT_SHAPES.get(node.node_type, "ellipse")
    label = node.label
    if node.event_type:
        label = f"{label}\\n[{node.event_type}]"
    attrs = [f'label="{_dot_escape(label)}"', f"shape={shape}"]
    if node.status == NodeStatus.INFERRED:
        attrs.append('style=dashed color=gray40 fontcolor=gray30 tooltip="inferred"')
    return f'  "{_dot_escape(node.id)}" [{" ".join(attrs)}];'


def _dot_edge(edge: GraphEdge) -> str:
    attrs = [f'label="{_dot_escape(_display_relation(edge.relation))}"']
    if edge.status == NodeStatus.INFERRED:
        attrs.append("style=dashed color=gray40 fontcolor=gray30")
    return f'  "{_dot_escape(edge.source)}" -> "{_dot_escape(edge.target)}" [{" ".join(attrs)}];'


def to_dot(graph: NarrativeGraph, gaps: Iterable[Gap] = ()) -> str:
    """Render the graph as Graphviz DOT (stated=solid, inferred=dashed, gaps=ghost)."""
    lines = [
        "digraph narrative {",
        "  rankdir=LR;",
        '  node [fontname="Helvetica"];',
        '  edge [fontname="Helvetica" fontsize=10];',
    ]
    lines.extend(_dot_node(n) for n in graph.nodes)
    lines.extend(_dot_edge(e) for e in graph.edges)
    for gap in gaps:
        gap_id = f"{_GAP_NODE_PREFIX}:{gap.event_id}:{gap.role}"
        color = "red" if gap.importance == GapImportance.REQUIRED else "orange"
        lines.append(
            f'  "{_dot_escape(gap_id)}" [label="{_dot_escape(_gap_label(gap))}" '
            f"shape=ellipse style=dotted color={color} fontcolor={color} "
            f'tooltip="{_dot_escape(gap.suggested_question)}"];'
        )
        lines.append(
            f'  "{_dot_escape(gap.event_id)}" -> "{_dot_escape(gap_id)}" '
            f'[label="{_dot_escape(gap.role)}" style=dotted color={color} fontcolor={color}];'
        )
    lines.append("}")
    return "\n".join(lines)


# ── Mermaid ──────────────────────────────────────────────────────────────────


def _mermaid_escape(text: str) -> str:
    return text.replace('"', "#quot;")


def _mermaid_shape(node_type: str, label: str) -> str:
    escaped = _mermaid_escape(label)
    if node_type == "event":
        return f'["{escaped}"]'
    if node_type == "time":
        return f'[/"{escaped}"/]'
    return f'(["{escaped}"])'


def to_mermaid(graph: NarrativeGraph, gaps: Iterable[Gap] = ()) -> str:
    """Render the graph as a Mermaid flowchart (paste into mermaid.live or docs)."""
    # Mermaid ids must be simple tokens; graph ids may contain `::` etc.
    ids = {node.id: f"n{i}" for i, node in enumerate(graph.nodes)}

    lines = ["flowchart LR"]
    for node in graph.nodes:
        label = node.label
        if node.event_type:
            label = f"{label}<br/>[{node.event_type}]"
        lines.append(f"  {ids[node.id]}{_mermaid_shape(node.node_type, label)}")
        if node.status == NodeStatus.INFERRED:
            lines.append(f"  class {ids[node.id]} inferred")

    for edge in graph.edges:
        source, target = ids.get(edge.source), ids.get(edge.target)
        if source is None or target is None:
            continue
        arrow = "-.->" if edge.status == NodeStatus.INFERRED else "-->"
        lines.append(
            f'  {source} {arrow}|"{_mermaid_escape(_display_relation(edge.relation))}"| {target}'
        )

    for i, gap in enumerate(gaps):
        event_id = ids.get(gap.event_id)
        if event_id is None:
            continue
        gap_id = f"g{i}"
        cls = "gapRequired" if gap.importance == GapImportance.REQUIRED else "gapExpected"
        lines.append(f'  {gap_id}(["{_mermaid_escape(_gap_label(gap))}"])')
        lines.append(f"  class {gap_id} {cls}")
        lines.append(f'  {event_id} -.->|"{_mermaid_escape(gap.role)}"| {gap_id}')

    lines.extend(
        [
            "  classDef inferred stroke-dasharray:5 5,stroke:#888,color:#555",
            "  classDef gapRequired stroke-dasharray:2 4,stroke:#d33,color:#d33",
            "  classDef gapExpected stroke-dasharray:2 4,stroke:#e80,color:#e80",
        ]
    )
    return "\n".join(lines)
