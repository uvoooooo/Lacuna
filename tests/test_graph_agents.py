"""Unit tests for the graph track: build -> ontology reasoning -> conflicts -> gaps."""

from narrative_audit.agents import (
    ConflictDetectorAgent,
    GapDetectorAgent,
    GraphBuilderAgent,
    OntologyReasonerAgent,
)
from narrative_audit.graph import (
    ConflictKind,
    GapImportance,
    GraphEdge,
    GraphNode,
    NodeStatus,
)
from narrative_audit.state import AuditState

_TEXT = "我在公司工作了六年。上周五我被开除了。"


def _state(text: str = _TEXT) -> AuditState:
    return AuditState(text=text)


# ── GraphBuilder ─────────────────────────────────────────────────────────────


def test_graph_builder_with_llm(fake_llm):
    state = _state()
    GraphBuilderAgent(fake_llm).run(state)
    events = state.graph.events()
    assert len(events) == 2
    assert all(n.status == NodeStatus.STATED for n in state.graph.nodes)
    assert any(e.relation == "before" for e in state.graph.edges)


def test_graph_builder_offline_fallback():
    state = _state()
    GraphBuilderAgent().run(state)
    assert not state.graph.is_empty
    assert state.graph.events()


# ── OntologyReasoner ─────────────────────────────────────────────────────────


def test_ontology_reasoner_types_events_and_infers_nodes(fake_llm):
    state = _state()
    GraphBuilderAgent(fake_llm).run(state)
    OntologyReasonerAgent(fake_llm).run(state)

    dismissal_events = [n for n in state.graph.events() if n.event_type == "dismissal"]
    assert dismissal_events, "被开除 event should be typed as dismissal"

    inferred = [n for n in state.graph.nodes if n.status == NodeStatus.INFERRED]
    assert inferred, "prior_employment should be added as an inferred node"

    event = dismissal_events[0]
    assert {"employer", "prior_employment"} <= state.graph.filled_roles(event.id)


def test_ontology_reasoner_offline_keyword_typing():
    state = _state()
    GraphBuilderAgent().run(state)
    OntologyReasonerAgent().run(state)
    typed = [n for n in state.graph.events() if n.event_type]
    assert typed, "keyword fallback should type the 开除 event"
    # Offline fallback never invents content.
    assert all(n.status == NodeStatus.STATED for n in state.graph.nodes)


# ── ConflictDetector ─────────────────────────────────────────────────────────


def test_conflict_detector_finds_before_cycle():
    state = _state()
    state.graph.add_node(GraphNode(id="e1", label="先到公司", node_type="event"))
    state.graph.add_node(GraphNode(id="e2", label="后被开除", node_type="event"))
    state.graph.add_edge(GraphEdge(source="e1", target="e2", relation="before"))
    state.graph.add_edge(GraphEdge(source="e2", target="e1", relation="before"))

    ConflictDetectorAgent().run(state)
    kinds = {c.kind for c in state.conflicts}
    assert ConflictKind.TIMELINE in kinds


def test_conflict_detector_finds_conflicting_time_anchors():
    state = _state()
    state.graph.add_node(GraphNode(id="e1", label="被开除", node_type="event"))
    state.graph.add_node(GraphNode(id="t1", label="周五", node_type="time"))
    state.graph.add_node(GraphNode(id="t2", label="周一", node_type="time"))
    state.graph.add_edge(GraphEdge(source="e1", target="t1", relation="occurs_at"))
    state.graph.add_edge(GraphEdge(source="e1", target="t2", relation="occurs_at"))

    ConflictDetectorAgent().run(state)
    kinds = {c.kind for c in state.conflicts}
    assert ConflictKind.ATTRIBUTE in kinds


def _time_anchored_state(t1: str, t2: str) -> AuditState:
    state = _state()
    state.graph.add_node(GraphNode(id="e1", label="被开除", node_type="event"))
    state.graph.add_node(GraphNode(id="t1", label=t1, node_type="time"))
    state.graph.add_node(GraphNode(id="t2", label=t2, node_type="time"))
    state.graph.add_edge(GraphEdge(source="e1", target="t1", relation="occurs_at"))
    state.graph.add_edge(GraphEdge(source="e1", target="t2", relation="occurs_at"))
    return state


def test_conflict_verification_suppresses_same_time_anchors(fake_llm):
    state = _time_anchored_state("周五", "上周五")
    ConflictDetectorAgent(fake_llm).run(state)

    kinds = {c.kind for c in state.conflicts}
    assert ConflictKind.ATTRIBUTE not in kinds, "周五 and 上周五 denote the same day"
    suppressed = state.metadata["conflicts_suppressed"]
    assert suppressed[0]["times"] == ["上周五", "周五"]


def test_conflict_verification_keeps_genuine_mismatch(fake_llm):
    state = _time_anchored_state("周五", "周一")
    ConflictDetectorAgent(fake_llm).run(state)
    kinds = {c.kind for c in state.conflicts}
    assert ConflictKind.ATTRIBUTE in kinds
    assert "conflicts_suppressed" not in state.metadata


def test_conflict_verification_unavailable_keeps_candidates():
    class _BrokenLLM:
        available = True
        model = "fake"

        def complete_json(self, _system, _user):
            return None

    state = _time_anchored_state("周五", "上周五")
    ConflictDetectorAgent(_BrokenLLM()).run(state)
    kinds = {c.kind for c in state.conflicts}
    assert ConflictKind.ATTRIBUTE in kinds, "malformed verification must not suppress"


def test_conflict_detector_clean_graph_has_no_conflicts(fake_llm):
    state = _state()
    GraphBuilderAgent(fake_llm).run(state)
    ConflictDetectorAgent(fake_llm).run(state)
    assert state.conflicts == []


# ── GapDetector ──────────────────────────────────────────────────────────────


def test_gap_detector_flags_missing_required_roles(fake_llm):
    state = _state()
    GraphBuilderAgent(fake_llm).run(state)
    OntologyReasonerAgent(fake_llm).run(state)
    GapDetectorAgent().run(state)

    # employer and prior_employment are filled by the reasoner; reason is not.
    required = [g for g in state.gaps if g.importance == GapImportance.REQUIRED]
    assert any(g.role == "reason" for g in required)
    assert all(g.role != "employer" for g in required)
    assert all(g.suggested_question for g in state.gaps)


def test_gap_detector_needs_typed_events():
    state = _state("今天天气不错。")
    GraphBuilderAgent().run(state)
    GapDetectorAgent().run(state)
    assert state.gaps == []


def test_gap_detector_suppresses_gaps_addressed_in_text(fake_llm):
    text = "我在公司工作了六年。上周五我被开除了，理由是绩效不达标，补偿也已经谈妥。"
    state = _state(text)
    GraphBuilderAgent(fake_llm).run(state)
    OntologyReasonerAgent(fake_llm).run(state)
    GapDetectorAgent(fake_llm).run(state)

    roles = {g.role for g in state.gaps}
    assert "reason" not in roles, "开除理由 is stated in the text, must not be reported"
    assert "compensation" not in roles, "补偿 is stated in the text, must not be reported"
    assert "prior_warning" in roles, "genuinely absent roles must survive verification"

    suppressed = state.metadata["gaps_suppressed"]
    assert {s["role"] for s in suppressed} == {"reason", "compensation"}
    for s in suppressed:
        assert s["quote"] and s["quote"] in text
    assert "suppressed 2" in state.log[-1].message


def test_gap_verification_rejects_hallucinated_quotes():
    class _LyingLLM:
        available = True
        model = "fake"

        def complete_json(self, _system, _user):
            return {"items": [{"index": 0, "addressed": True, "quote": "原文中不存在的句子"}]}

    state = _state()
    state.graph.add_node(
        GraphNode(id="e1", label="被开除", node_type="event", event_type="dismissal")
    )
    GapDetectorAgent(_LyingLLM()).run(state)

    # The quote does not appear in the text, so nothing may be suppressed.
    assert any(g.role == "employer" for g in state.gaps)
    assert "gaps_suppressed" not in state.metadata


def test_gap_verification_unavailable_keeps_all_candidates():
    class _BrokenLLM:
        available = True
        model = "fake"

        def complete_json(self, _system, _user):
            return None

    state = _state()
    state.graph.add_node(
        GraphNode(id="e1", label="被开除", node_type="event", event_type="dismissal")
    )
    GapDetectorAgent(_BrokenLLM()).run(state)
    assert len(state.gaps) == 7, "all dismissal roles unfilled, all must be reported"


# ── End to end report ────────────────────────────────────────────────────────


def test_report_includes_graph_findings(fake_llm):
    from narrative_audit import NarrativeAuditPipeline

    state = NarrativeAuditPipeline(llm=fake_llm).run(_TEXT)
    assert "要素空缺" in state.report_markdown
    assert "本体推理出的隐含节点" in state.report_markdown
    payload = state.to_dict()
    assert payload["graph"]["nodes"]
    assert isinstance(payload["gaps"], list) and payload["gaps"]
