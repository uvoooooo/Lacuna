"""
Agent: Gap Detector (要素识别 / 图空缺检测).

The "listen to what hasn't been said" step. For every typed event, compares
the roles the ontology declares against the roles actually present in the
graph. Missing `required` roles are elements that must exist for the event to
have happened at all; their absence from a self-supportive narrative is
itself a signal. Missing `expected` roles become follow-up questions.

Detection is fully deterministic: the role checklist comes from the ontology,
coverage comes from `role:` edges on the graph. No model judgement decides
whether something is a gap.

What the LLM adds is a second look at the *candidates*: the worst failure
mode of gap reporting is accusing the narrative of omitting something it
actually said (because upstream extraction missed it). With an LLM available,
every candidate gap is checked against the original text in one batched call;
a candidate is suppressed only if the model quotes an exact span of the text
that addresses it (the quote is verified to appear verbatim, so the model
cannot suppress a gap by hallucination). Suppressions are recorded in
`state.metadata["gaps_suppressed"]` for auditability. Offline, all candidates
are reported unchanged.
"""

from __future__ import annotations

import json

from ..graph import Gap, GapImportance, GraphNode
from ..ontology import DEFAULT_ONTOLOGY, EventType, RoleSpec
from ..state import AuditState
from .base import BaseAgent

_VERIFY_SYSTEM = (
    "You are a gap-verification engine for narrative auditing. A deterministic "
    "checker flagged ontology elements as missing from a narrative's knowledge "
    "graph. Your job is to catch extraction misses: for each candidate, check "
    "whether the original text does in fact address that element. Respond with "
    "JSON only."
)
_VERIFY_USER_TMPL = (
    "Original text:\n{text}\n\n"
    "Candidate missing elements:\n{candidates}\n\n"
    'Return: {{"items": [{{"index": int, "addressed": bool, "quote": str}}]}}\n'
    "Rules:\n"
    "- addressed=true ONLY if the text explicitly provides the element; quote "
    "must be the exact verbatim span of the text that provides it.\n"
    "- Vague, emotional or evasive mentions do not count as addressing an "
    "element.\n"
    "- When unsure, addressed=false: reporting a real gap matters more than "
    "suppressing a false one.\n"
    "- No markdown fences."
)


class GapDetectorAgent(BaseAgent):
    name = "gap_detector"
    description = "对照本体查必要要素空缺，关键空缺 = 可疑信号"

    def __init__(self, llm=None, ontology: dict[str, EventType] | None = None) -> None:
        super().__init__(llm)
        self.ontology = ontology or DEFAULT_ONTOLOGY

    def _run(self, state: AuditState) -> str:
        typed_events = [n for n in state.graph.events() if n.event_type in self.ontology]
        if not typed_events:
            return "no typed events"

        candidates: list[Gap] = []
        for event in typed_events:
            event_type = self.ontology[event.event_type]
            filled = state.graph.filled_roles(event.id)
            for role in event_type.roles:
                if role.name not in filled:
                    candidates.append(self._to_gap(event, event_type, role))

        kept = candidates
        suppressed = 0
        if candidates and self.uses_llm:
            kept = self._verify(state, candidates)
            suppressed = len(candidates) - len(kept)
        state.gaps.extend(kept)

        required = sum(1 for g in kept if g.importance == GapImportance.REQUIRED)
        message = f"found {len(kept)} gaps ({required} required)"
        if suppressed:
            message += f", suppressed {suppressed} addressed in text"
        return message

    # ── LLM second look ──────────────────────────────────────────────────────

    def _verify(self, state: AuditState, candidates: list[Gap]) -> list[Gap]:
        blob = json.dumps(
            [
                {
                    "index": i,
                    "event": g.event_label,
                    "element": g.role_zh or g.role,
                    "question": g.suggested_question,
                }
                for i, g in enumerate(candidates)
            ],
            ensure_ascii=False,
        )
        payload = self.llm.complete_json(
            _VERIFY_SYSTEM, _VERIFY_USER_TMPL.format(text=state.text, candidates=blob)
        )
        if not payload or not isinstance(payload.get("items"), list):
            return candidates  # verification unavailable: keep every candidate

        addressed: dict[int, str] = {}
        for item in payload["items"]:
            if not isinstance(item, dict) or item.get("addressed") is not True:
                continue
            try:
                index = int(item.get("index", -1))
            except (TypeError, ValueError):
                continue
            quote = str(item.get("quote", "")).strip()
            # Deterministic anchor: a suppression counts only when its quote
            # appears verbatim in the text, so the model cannot dismiss a gap
            # with invented evidence.
            if quote and quote in state.text:
                addressed[index] = quote

        kept: list[Gap] = []
        for i, gap in enumerate(candidates):
            if i in addressed:
                state.metadata.setdefault("gaps_suppressed", []).append(
                    {
                        "event": gap.event_label,
                        "role": gap.role,
                        "role_zh": gap.role_zh,
                        "quote": addressed[i],
                    }
                )
            else:
                kept.append(gap)
        return kept

    @staticmethod
    def _to_gap(event: GraphNode, event_type: EventType, role: RoleSpec) -> Gap:
        if role.importance == GapImportance.REQUIRED:
            why = (
                f"「{event_type.label_zh}」事件必然存在「{role.label_zh}」，"
                f"但叙述中完全没有出现，这个空缺本身值得注意。"
            )
        else:
            why = (
                f"完整的「{event_type.label_zh}」叙述通常会交代「{role.label_zh}」，此处没有提及。"
            )
        return Gap(
            event_id=event.id,
            event_label=event.label,
            role=role.name,
            role_zh=role.label_zh,
            importance=role.importance,
            why_suspicious=why,
            suggested_question=role.question,
        )
