"""Tests for the DOT / Mermaid graph exports."""

from narrative_audit.agents import GapDetectorAgent, GraphBuilderAgent, OntologyReasonerAgent
from narrative_audit.graph import Gap, GapImportance, GraphEdge, GraphNode, NarrativeGraph
from narrative_audit.state import AuditState
from narrative_audit.viz import to_dot, to_mermaid

_TEXT = "我在公司工作了六年。上周五我被开除了。"


def _audited_state(fake_llm) -> AuditState:
    state = AuditState(text=_TEXT)
    GraphBuilderAgent(fake_llm).run(state)
    OntologyReasonerAgent(fake_llm).run(state)
    GapDetectorAgent().run(state)
    return state


# ── DOT ──────────────────────────────────────────────────────────────────────


def test_dot_renders_stated_and_inferred(fake_llm):
    state = _audited_state(fake_llm)
    dot = to_dot(state.graph, gaps=state.gaps)

    assert dot.startswith("digraph narrative {") and dot.endswith("}")
    assert "被开除" in dot
    assert "[dismissal]" in dot  # typed event shows its ontology type
    assert "style=dashed" in dot  # inferred prior_employment node
    assert "style=dotted" in dot  # gap ghost nodes
    assert '"gap:' in dot
    assert "color=red" in dot  # required gap (reason)
    # Role edges are displayed without the internal prefix.
    assert 'label="employer"' in dot
    assert 'label="role:employer"' not in dot


def test_dot_escapes_quotes():
    graph = NarrativeGraph()
    graph.add_node(GraphNode(id="e1", label='他说"没有补偿"', node_type="event"))
    dot = to_dot(graph)
    assert '\\"没有补偿\\"' in dot


# ── Mermaid ──────────────────────────────────────────────────────────────────


def test_mermaid_renders_stated_and_inferred(fake_llm):
    state = _audited_state(fake_llm)
    mmd = to_mermaid(state.graph, gaps=state.gaps)

    assert mmd.startswith("flowchart LR")
    assert "被开除" in mmd
    assert "class " in mmd and "inferred" in mmd
    assert "gapRequired" in mmd and "缺失:" in mmd
    assert "classDef inferred" in mmd
    # Every graph id is remapped to a mermaid-safe token; raw ids with `::`
    # (created for role fillers) must not leak into the output.
    assert "::" not in mmd


def test_mermaid_ignores_dangling_edges_and_gaps():
    graph = NarrativeGraph()
    graph.add_node(GraphNode(id="e1", label="事件", node_type="event"))
    graph.add_edge(GraphEdge(source="e1", target="missing", relation="before"))
    gap = Gap(event_id="missing", event_label="", role="r", importance=GapImportance.REQUIRED)

    mmd = to_mermaid(graph, gaps=[gap])
    assert "missing" not in mmd
    assert "-->" not in mmd  # the dangling edge was skipped


def test_exports_are_importable_from_package():
    from narrative_audit import to_dot as td
    from narrative_audit import to_mermaid as tm

    assert callable(td) and callable(tm)
