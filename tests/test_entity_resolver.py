"""Tests for entity resolution: NarrativeGraph.merge_nodes + EntityResolverAgent."""

from narrative_audit.agents import EntityResolverAgent
from narrative_audit.graph import GraphEdge, GraphNode, NarrativeGraph
from narrative_audit.state import AuditState


def _graph_with_duplicates() -> NarrativeGraph:
    g = NarrativeGraph()
    g.add_node(GraphNode(id="ev1", label="被开除", node_type="event"))
    g.add_node(GraphNode(id="p1", label="部门经理", node_type="entity"))
    g.add_node(GraphNode(id="p2", label="经理", node_type="entity"))
    g.add_node(GraphNode(id="me", label="我", node_type="entity"))
    g.add_edge(GraphEdge(source="p2", target="ev1", relation="participates_in"))
    g.add_edge(GraphEdge(source="me", target="ev1", relation="participates_in"))
    return g


# ── merge_nodes ──────────────────────────────────────────────────────────────


def test_merge_nodes_rewires_edges_and_records_alias():
    g = _graph_with_duplicates()
    assert g.merge_nodes("p1", "p2")

    assert g.get_node("p2") is None
    kept = g.get_node("p1")
    assert kept.aliases == ["经理"]
    # The participates_in edge now hangs off the kept node.
    assert any(e.source == "p1" and e.target == "ev1" for e in g.edges)
    assert all("p2" not in (e.source, e.target) for e in g.edges)


def test_merge_nodes_drops_self_loops_and_duplicate_edges():
    g = NarrativeGraph()
    g.add_node(GraphNode(id="a", label="A", node_type="entity"))
    g.add_node(GraphNode(id="b", label="B", node_type="entity"))
    g.add_node(GraphNode(id="ev", label="事件", node_type="event"))
    g.add_edge(GraphEdge(source="a", target="b", relation="knows"))  # becomes self-loop
    g.add_edge(GraphEdge(source="a", target="ev", relation="participates_in"))
    g.add_edge(GraphEdge(source="b", target="ev", relation="participates_in"))  # duplicate

    assert g.merge_nodes("a", "b")
    assert len(g.edges) == 1
    assert g.edges[0].source == "a" and g.edges[0].target == "ev"


def test_merge_nodes_rejects_missing_or_same_ids():
    g = _graph_with_duplicates()
    assert not g.merge_nodes("p1", "p1")
    assert not g.merge_nodes("p1", "nope")
    assert not g.merge_nodes("nope", "p1")


def test_merge_nodes_rewrites_timeline():
    g = NarrativeGraph()
    g.add_node(GraphNode(id="e1", label="事件A", node_type="event"))
    g.add_node(GraphNode(id="e2", label="事件A重复", node_type="event"))
    g.timeline.append({"event_id": "e2", "time": "UNKNOWN", "order": "0", "text": "事件A"})

    assert g.merge_nodes("e1", "e2")
    assert g.timeline[0]["event_id"] == "e1"


# ── EntityResolverAgent, LLM path ────────────────────────────────────────────


def test_resolver_merges_coreferent_entities(fake_llm):
    state = AuditState(text="部门经理叫我去办公室，经理说我被开除了。")
    state.graph = _graph_with_duplicates()

    EntityResolverAgent(fake_llm).run(state)

    assert state.graph.get_node("p2") is None
    kept = state.graph.get_node("p1")
    assert kept.label == "部门经理"
    assert "经理" in kept.aliases
    # 我 does not co-refer with anything and must survive.
    assert state.graph.get_node("me") is not None
    merges = state.metadata["entity_merges"]
    assert merges[0]["kept"] == "p1" and merges[0]["dropped"] == "p2"
    assert merges[0]["confidence"] >= 0.6


def test_resolver_ignores_low_confidence_proposals():
    class _TimidLLM:
        available = True
        model = "fake"

        def complete_json(self, _system, _user):
            return {
                "merges": [
                    {"keep_id": "p1", "drop_ids": ["me"], "canonical_label": "", "confidence": 0.3}
                ]
            }

    state = AuditState(text="...")
    state.graph = _graph_with_duplicates()
    EntityResolverAgent(_TimidLLM()).run(state)
    assert state.graph.get_node("me") is not None
    assert "entity_merges" not in state.metadata


def test_resolver_never_merges_events():
    class _OverreachingLLM:
        available = True
        model = "fake"

        def complete_json(self, _system, _user):
            return {
                "merges": [
                    {"keep_id": "p1", "drop_ids": ["ev1"], "canonical_label": "", "confidence": 0.9}
                ]
            }

    state = AuditState(text="...")
    state.graph = _graph_with_duplicates()
    EntityResolverAgent(_OverreachingLLM()).run(state)
    assert state.graph.get_node("ev1") is not None


# ── Offline fallback ─────────────────────────────────────────────────────────


def test_offline_fallback_merges_only_exact_labels():
    state = AuditState(text="...")
    g = state.graph
    g.add_node(GraphNode(id="a1", label="部门经理", node_type="entity"))
    g.add_node(GraphNode(id="a2", label="部门经理", node_type="entity"))
    g.add_node(GraphNode(id="b", label="经理", node_type="entity"))

    result = EntityResolverAgent().run(state)

    assert g.get_node("a2") is None, "exact duplicate label must merge"
    assert g.get_node("b") is not None, "near-duplicate must NOT merge offline"
    assert "exact-label" in result.log[-1].message


def test_resolver_noop_with_fewer_than_two_entities(fake_llm):
    state = AuditState(text="...")
    state.graph.add_node(GraphNode(id="ev1", label="事件", node_type="event"))
    EntityResolverAgent(fake_llm).run(state)
    assert "nothing to resolve" in state.log[-1].message
