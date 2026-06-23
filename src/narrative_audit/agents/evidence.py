"""
Agent 4 — Evidence Agent (证据检索 + 匹配).

Key rule from docs/MVP_items.md: the search agent should NOT search everything.
It only looks up claims that are externally verifiable (checkability high/medium
and not purely emotional/subjective). For each retrieved snippet it judges the
stance: support / refute / partial / irrelevant / not_enough_info.

`search_fn` is pluggable. Default is offline (returns no hits), so the pipeline
runs without network. Pass a real search callable to enable retrieval.
"""

from __future__ import annotations

from collections.abc import Callable

from ..llm import LLMClient
from ..state import AuditState, Claim, Evidence, EvidenceStance, Label
from .base import BaseAgent

# A search function takes a query string and returns a list of raw hits, each a
# dict with at least {"snippet": str, "source": str, "url": str}.
SearchFn = Callable[[str], list[dict]]

_SYSTEM = (
    "You are an evidence-matching engine. Judge how each evidence snippet "
    "relates to the claim. Respond with JSON only."
)
_USER_TMPL = (
    "Claim: {claim}\nEvidence snippets:\n{snippets}\n"
    "For each snippet, judge stance: "
    "support / refute / partial_support / irrelevant / not_enough_info, "
    "and give credibility (0-1) and freshness (0-1).\n"
    'Return strict JSON: {{"items": [{{"index": 0, "stance": "...", '
    '"credibility": 0.6, "freshness": 0.5}}]}}. No markdown.'
)


class EvidenceAgent(BaseAgent):
    name = "evidence"
    description = "只对可核查事实去搜证据并判断支持/反驳"

    def __init__(
        self,
        llm: LLMClient | None = None,
        search_fn: SearchFn | None = None,
        max_hits: int = 5,
    ) -> None:
        super().__init__(llm)
        self.search_fn = search_fn
        self.max_hits = max_hits

    def _run(self, state: AuditState) -> str:
        if not state.claims:
            return "no claims"

        searched = 0
        skipped = 0
        for claim in state.claims:
            if not self._should_search(claim):
                skipped += 1
                continue
            searched += 1
            self._gather(claim)
            self._set_evidence_status(claim)

        if self.search_fn is None:
            return f"无检索后端：{searched} 条可核查陈述待检索，{skipped} 条跳过"
        return f"检索 {searched} 条可核查陈述，跳过 {skipped} 条主观/情绪化陈述"

    @staticmethod
    def _should_search(claim: Claim) -> bool:
        if not claim.is_checkable:
            return False
        # Never hand purely emotional/opinion claims to search.
        if set(claim.labels) & {Label.EMOTIONAL, Label.OPINION} and Label.FACT not in claim.labels:
            return False
        return True

    def _gather(self, claim: Claim) -> None:
        if self.search_fn is None:
            return
        try:
            hits = self.search_fn(claim.text) or []
        except Exception:
            hits = []
        hits = hits[: self.max_hits]
        if not hits:
            return

        stances = self._match_stances(claim, hits)
        for idx, hit in enumerate(hits):
            stance, cred, fresh = stances.get(idx, (EvidenceStance.NOT_ENOUGH, 0.5, 0.5))
            claim.evidence.append(
                Evidence(
                    snippet=str(hit.get("snippet", "")).strip(),
                    source=str(hit.get("source", "unknown")),
                    url=str(hit.get("url", "")),
                    stance=stance,
                    credibility=cred,
                    freshness=fresh,
                )
            )

    def _match_stances(self, claim: Claim, hits: list[dict]) -> dict:
        result: dict = {}
        if self.uses_llm:
            snippets = "\n".join(f"[{i}] {str(h.get('snippet', ''))}" for i, h in enumerate(hits))
            payload = self.llm.complete_json(
                _SYSTEM, _USER_TMPL.format(claim=claim.text, snippets=snippets)
            )
            if payload and isinstance(payload.get("items"), list):
                valid = {
                    EvidenceStance.SUPPORT,
                    EvidenceStance.REFUTE,
                    EvidenceStance.PARTIAL,
                    EvidenceStance.IRRELEVANT,
                    EvidenceStance.NOT_ENOUGH,
                }
                for item in payload["items"]:
                    if not isinstance(item, dict):
                        continue
                    try:
                        i = int(item.get("index", -1))
                    except (TypeError, ValueError):
                        continue
                    stance = str(item.get("stance", "")).strip()
                    if stance not in valid:
                        stance = EvidenceStance.NOT_ENOUGH
                    result[i] = (
                        stance,
                        _clamp(item.get("credibility", 0.5)),
                        _clamp(item.get("freshness", 0.5)),
                    )
        return result

    @staticmethod
    def _set_evidence_status(claim: Claim) -> None:
        if not claim.evidence:
            claim.evidence_status = EvidenceStance.NOT_ENOUGH
            return
        stances = [e.stance for e in claim.evidence]
        if EvidenceStance.REFUTE in stances:
            claim.evidence_status = EvidenceStance.REFUTE
        elif EvidenceStance.SUPPORT in stances:
            claim.evidence_status = EvidenceStance.SUPPORT
        elif EvidenceStance.PARTIAL in stances:
            claim.evidence_status = EvidenceStance.PARTIAL
        else:
            claim.evidence_status = EvidenceStance.NOT_ENOUGH


def _clamp(value: object, lo: float = 0.0, hi: float = 1.0) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.5
    return max(lo, min(hi, v))
