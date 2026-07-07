"""Tests for the shareable HTML audit card."""

from narrative_audit import NarrativeAuditPipeline
from narrative_audit.card import to_share_card
from narrative_audit.state import AuditState

_TEXT = "我在公司勤勤恳恳工作了六年。上周五我被开除了。这是赤裸裸的压榨！"


def _audited(fake_llm) -> AuditState:
    return NarrativeAuditPipeline(llm=fake_llm).run(_TEXT)


def test_card_is_standalone_html(fake_llm):
    card = to_share_card(_audited(fake_llm))
    assert card.startswith("<!DOCTYPE html>")
    assert "<style>" in card
    assert "http" not in card.split("</style>")[1], "no external assets after the CSS block"


def test_card_shows_gaps_as_centerpiece(fake_llm):
    state = _audited(fake_llm)
    card = to_share_card(state)
    assert f"{len(state.gaps)}</span> 件事" in card
    for gap in state.gaps:
        assert gap.suggested_question in card
    # Required gaps carry the red badge, expected ones the outline badge.
    assert 'class="badge required"' in card


def test_card_highlights_subjective_claims(fake_llm):
    card = to_share_card(_audited(fake_llm))
    assert "hl-subjective" in card
    assert "压榨" in card


def test_card_escapes_html_in_input(fake_llm):
    state = NarrativeAuditPipeline(llm=fake_llm).run("<script>alert(1)</script>我被开除了。")
    card = to_share_card(state)
    assert "<script>alert" not in card
    assert "&lt;script&gt;" in card


def test_card_without_gaps_renders_fallback():
    state = AuditState(text="今天天气不错。")
    card = to_share_card(state)
    assert "关键要素基本齐全" in card
    assert "件事" not in card
