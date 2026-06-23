"""
Agent 3 — Missing Context Agent.

For each claim, decides what is missing in order to evaluate it: cause,
evidence, time/place, third-party records, opposing view, follow-up handling.
Also produces follow-up questions the reader should ask.

The LLM does the real work. The offline fallback is structural (driven by
whether a claim is checkable), not keyword-based.
"""

from __future__ import annotations

import json

from ..state import AuditState, Claim
from .base import BaseAgent

_DIMENSIONS = (
    "cause",
    "evidence",
    "time_place",
    "third_party_record",
    "opposing_view",
    "follow_up",
)

_SYSTEM = (
    "You are a missing-context analyzer for narrative auditing. For each "
    "statement, identify what key information is missing in order to evaluate "
    "it, and propose follow-up questions. Respond with JSON only."
)
_USER_TMPL = (
    "Reference dimensions for what may be missing: "
    "cause / evidence / time_place / third_party_record / opposing_view / follow_up.\n"
    "Ask the follow-up questions in the same language as the statement.\n"
    'Return strict JSON: {{"items": [{{"id": "c1", "missing_context": ["..."], '
    '"suggested_questions": ["..."]}}]}}. No markdown.\n\n'
    "Statements:\n{claims}"
)


class MissingContextAgent(BaseAgent):
    name = "missing_context"
    description = "Find what's missing to evaluate a claim + what to ask"

    def _run(self, state: AuditState) -> str:
        if not state.claims:
            return "no claims"

        applied = False
        if self.uses_llm:
            applied = self._with_llm(state)

        if not applied:
            for claim in state.claims:
                self._heuristic(claim)

        total = sum(len(c.missing_context) for c in state.claims)
        mode = "llm" if applied else "heuristic"
        return f"flagged {total} gaps ({mode})"

    def _with_llm(self, state: AuditState) -> bool:
        claims_blob = json.dumps(
            [{"id": c.id, "text": c.text, "labels": c.labels} for c in state.claims],
            ensure_ascii=False,
        )
        payload = self.llm.complete_json(_SYSTEM, _USER_TMPL.format(claims=claims_blob))
        if not payload or not isinstance(payload.get("items"), list):
            return False
        by_id = {c.id: c for c in state.claims}
        for item in payload["items"]:
            if not isinstance(item, dict):
                continue
            claim = by_id.get(str(item.get("id", "")))
            if not claim:
                continue
            claim.missing_context = [
                str(x).strip() for x in item.get("missing_context", []) if str(x).strip()
            ]
            claim.suggested_questions = [
                str(x).strip() for x in item.get("suggested_questions", []) if str(x).strip()
            ]
        return True

    def _heuristic(self, claim: Claim) -> None:
        # Structural fallback: checkable claims need evidence/records; the rest
        # mainly need the opposing view. No keyword matching.
        if claim.is_checkable:
            missing = ["evidence", "third_party_record"]
            questions = ["What verifiable record or third-party evidence supports this?"]
        else:
            missing = ["opposing_view", "cause"]
            questions = ["How would the other side describe the same thing?"]

        claim.missing_context = list(dict.fromkeys(missing))
        claim.suggested_questions = list(dict.fromkeys(questions))
