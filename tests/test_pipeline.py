"""End-to-end pipeline tests, using a fake LLM (no network)."""

import pytest

from narrative_audit import NarrativeAuditPipeline
from narrative_audit.state import EvidenceStance


def _pipeline(fake_llm, search_fn=None):
    return NarrativeAuditPipeline(llm=fake_llm, search_fn=search_fn)


def test_pipeline_runs_and_produces_report(fake_llm):
    state = _pipeline(fake_llm).run("上周五部门经理突然把我开除了。连补偿都没有。")
    assert state.claims, "should extract at least one claim"
    assert state.report_markdown.startswith("# 表述审阅报告")
    assert 0.0 <= state.overall_confidence <= 1.0
    assert state.metadata["pipeline"] == [
        "claim_splitter",
        "label",
        "missing_context",
        "graph_builder",
        "entity_resolver",
        "ontology_reasoner",
        "conflict_detector",
        "gap_detector",
        "evidence",
        "report",
    ]


def test_log_records_every_agent(fake_llm):
    state = _pipeline(fake_llm).run("公司上周四发生了大规模数据泄漏。")
    agents_logged = {step.agent for step in state.log}
    assert agents_logged == {
        "claim_splitter",
        "label",
        "missing_context",
        "graph_builder",
        "entity_resolver",
        "ontology_reasoner",
        "conflict_detector",
        "gap_detector",
        "evidence",
        "report",
    }


def test_empty_input_is_safe(fake_llm):
    state = _pipeline(fake_llm).run("")
    assert state.claims == []
    assert state.overall_confidence == 0.0


def test_label_agent_requires_llm():
    # No LLM available -> the Label stage must raise rather than guess.
    pipeline = NarrativeAuditPipeline(llm=_NoLLM())
    with pytest.raises(RuntimeError, match="requires an LLM"):
        pipeline.run("公司上周四发生了大规模数据泄漏。")


def test_evidence_attached_with_mock_search(fake_llm):
    from narrative_audit.search import make_mock_search

    state = _pipeline(fake_llm, search_fn=make_mock_search()).run(
        "公司上周四发生了大规模数据泄漏。"
    )
    checkable = [c for c in state.claims if c.is_checkable]
    assert checkable
    assert any(c.evidence for c in checkable), "mock search should attach evidence"
    assert any(c.evidence_status == EvidenceStance.SUPPORT for c in checkable)


def test_no_search_backend_means_not_enough_info(fake_llm):
    state = _pipeline(fake_llm).run("公司上周四发生了大规模数据泄漏。")
    for claim in state.claims:
        assert claim.evidence == []
        assert claim.evidence_status == EvidenceStance.NOT_ENOUGH


class _NoLLM:
    available = False
    model = "none"

    def complete_json(self, *_args, **_kwargs):
        return None
