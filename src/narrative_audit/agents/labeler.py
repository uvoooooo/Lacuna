"""
Agent 2 — Label Agent.

Tags each claim with one or more of:
fact_claim / opinion / inference / emotional / quote / missing_context
and assigns a checkability level. This decides what the Evidence Agent is even
allowed to search for: emotional / subjective claims are NOT sent to search.

Labeling is a semantic judgment, so this agent REQUIRES an LLM. There is no
heuristic fallback by design: without an LLM it raises rather than emit guessed
labels. (Set OPENROUTER_API_KEY; see .env.example.)
"""

from __future__ import annotations

import json

from ..state import AuditState, Checkability, Label
from .base import BaseAgent

_SYSTEM = (
    "You are a statement-labeling engine for narrative auditing. "
    "Label each statement and judge how verifiable it is. Respond with JSON only."
)
_USER_TMPL = (
    "For each statement, choose 1-3 labels from:\n"
    "  fact_claim   - a concrete, checkable factual assertion\n"
    "  opinion      - a subjective evaluation or judgment\n"
    "  inference    - a guess / speculation / conclusion drawn by the speaker\n"
    "  emotional    - emotionally charged or loaded wording\n"
    "  quote        - reported speech / hearsay / attribution to someone else\n"
    "  missing_context - the statement only makes sense with context not given\n"
    "Also set checkability: high | medium | low | none "
    "(can it be verified against external evidence?).\n"
    "Keep the original language of each statement; do not rewrite it.\n"
    'Return strict JSON: {{"items": [{{"id": "c1", "labels": ["..."], '
    '"checkability": "..."}}]}}. No markdown.\n\n'
    "Statements:\n{claims}"
)


class LabelAgent(BaseAgent):
    name = "label"
    description = "Label each statement + judge verifiability"

    def _run(self, state: AuditState) -> str:
        if not state.claims:
            return "no claims"

        if not self.uses_llm:
            raise RuntimeError(
                "LabelAgent requires an LLM. Set OPENROUTER_API_KEY (see .env.example)."
            )
        if not self._label_with_llm(state):
            raise RuntimeError(
                "LabelAgent: the LLM returned no valid labels. Check the model/output."
            )

        facts = sum(1 for c in state.claims if c.has_label(Label.FACT))
        checkable = sum(1 for c in state.claims if c.is_checkable)
        return f"labeled {len(state.claims)} (llm); facts {facts}, checkable {checkable}"

    def _label_with_llm(self, state: AuditState) -> bool:
        claims_blob = json.dumps(
            [{"id": c.id, "text": c.text} for c in state.claims],
            ensure_ascii=False,
        )
        payload = self.llm.complete_json(_SYSTEM, _USER_TMPL.format(claims=claims_blob))
        if not payload or not isinstance(payload.get("items"), list):
            return False
        by_id = {c.id: c for c in state.claims}
        valid_labels = set(Label.ZH.keys())
        valid_check = {Checkability.HIGH, Checkability.MEDIUM, Checkability.LOW, Checkability.NONE}
        for item in payload["items"]:
            if not isinstance(item, dict):
                continue
            claim = by_id.get(str(item.get("id", "")))
            if not claim:
                continue
            labels = [str(x) for x in item.get("labels", []) if str(x) in valid_labels]
            claim.labels = labels or [Label.OPINION]
            check = str(item.get("checkability", "")).lower()
            claim.checkability = (
                check if check in valid_check else self._infer_checkability(claim.labels)
            )
        return True

    @staticmethod
    def _infer_checkability(labels: list[str]) -> str:
        if Label.FACT in labels and not (set(labels) & {Label.EMOTIONAL, Label.OPINION}):
            return Checkability.HIGH
        if Label.FACT in labels:
            return Checkability.MEDIUM
        if Label.INFERENCE in labels or Label.QUOTE in labels:
            return Checkability.LOW
        return Checkability.NONE
