"""Unit tests for individual agents."""

import pytest

from narrative_audit.agents import (
    ClaimSplitterAgent,
    EvidenceAgent,
    LabelAgent,
    MissingContextAgent,
)
from narrative_audit.state import AuditState, Checkability, Claim, Label


def _state(text: str) -> AuditState:
    return AuditState(text=text)


def test_claim_splitter_breaks_sentences():
    state = _state("我工作了六年。上周五我被开除了。")
    ClaimSplitterAgent().run(state)
    assert len(state.claims) >= 2


def test_label_agent_applies_llm_labels(fake_llm):
    state = _state("placeholder")
    state.claims = [
        Claim(id="c1", text="这是赤裸裸的压榨"),
        Claim(id="c2", text="对方追了我们二十分钟"),
    ]
    LabelAgent(fake_llm).run(state)
    assert state.claims[0].checkability == Checkability.NONE
    assert Label.FACT in state.claims[1].labels
    assert state.claims[1].is_checkable


def test_label_agent_raises_without_llm():
    state = _state("placeholder")
    state.claims = [Claim(id="c1", text="这是赤裸裸的压榨")]
    with pytest.raises(RuntimeError, match="requires an LLM"):
        LabelAgent().run(state)


def test_missing_context_suggests_questions():
    state = _state("placeholder")
    state.claims = [Claim(id="c1", text="上周五部门经理把我开除了", labels=[Label.FACT])]
    state.claims[0].checkability = Checkability.HIGH
    MissingContextAgent().run(state)
    claim = state.claims[0]
    assert claim.missing_context
    assert claim.suggested_questions


def test_evidence_agent_skips_subjective_claims():
    state = _state("placeholder")
    state.claims = [
        Claim(
            id="c1",
            text="这是赤裸裸的压榨",
            labels=[Label.EMOTIONAL],
            checkability=Checkability.NONE,
        ),
    ]
    # search_fn returns a hit for everything; agent should not call it for this claim.
    called = {"n": 0}

    def fake_search(_query: str):
        called["n"] += 1
        return [{"snippet": "x", "source": "s", "url": ""}]

    EvidenceAgent(search_fn=fake_search).run(state)
    assert called["n"] == 0
    assert state.claims[0].evidence == []
