"""
Agent 1 — Claim Splitter (声明拆分).

Splits raw input into atomic statements (facts / time / place / action /
damage / attribution / evaluation). Uses the LLM when available, otherwise a
sentence-boundary heuristic.
"""

from __future__ import annotations

import re

from ..state import AuditState, Claim
from .base import BaseAgent

_SENTENCE_SPLIT = re.compile(r"[。！？!?;；\n]+")

_SYSTEM = (
    "You are a claim-splitting engine. Break the input text into atomic "
    "statements, where each statement carries a single fact, time, place, "
    "action, harm, attribution, or evaluation. Respond with JSON only."
)
_USER_TMPL = (
    'Return strict JSON: {{"claims": ["statement 1", "statement 2", ...]}}\n'
    "Rules:\n"
    "- Each statement should express only one idea; split when possible.\n"
    "- Keep the original wording and language; do not rewrite or evaluate.\n"
    "- Do not output markdown code fences.\n\n"
    "Text:\n{text}"
)


class ClaimSplitterAgent(BaseAgent):
    name = "claim_splitter"
    description = "Split source text into atomic statements"

    def _run(self, state: AuditState) -> str:
        text = (state.text or "").strip()
        if not text:
            return "empty input"

        raw_claims: list[str] = []
        if self.uses_llm:
            payload = self.llm.complete_json(_SYSTEM, _USER_TMPL.format(text=text))
            if payload and isinstance(payload.get("claims"), list):
                raw_claims = [str(c).strip() for c in payload["claims"] if str(c).strip()]

        if not raw_claims:
            raw_claims = self._heuristic_split(text)

        for idx, claim_text in enumerate(raw_claims, start=1):
            state.claims.append(Claim(id=f"c{idx}", text=claim_text))

        mode = "llm" if self.uses_llm and raw_claims else "heuristic"
        return f"拆出 {len(state.claims)} 条原子陈述 ({mode})"

    @staticmethod
    def _heuristic_split(text: str) -> list[str]:
        parts = [p.strip() for p in _SENTENCE_SPLIT.split(text)]
        claims: list[str] = []
        for part in parts:
            if not part:
                continue
            for sub in re.split(r"[，,]", part):
                sub = sub.strip()
                if len(sub) >= 4:
                    claims.append(sub)
            if not any(len(s.strip()) >= 4 for s in re.split(r"[，,]", part)):
                claims.append(part)
        return claims or [text]
