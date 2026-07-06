"""
Agent — Gap Detector (要素识别 / 图空缺检测).

The "listen to what hasn't been said" step. For every typed event, compares
the roles the ontology declares against the roles actually present in the
graph. Missing `required` roles are elements that must exist for the event to
have happened at all — their absence from a self-supportive narrative is
itself a signal. Missing `expected` roles become follow-up questions.

This agent is fully deterministic: the role checklist comes from the
ontology, coverage comes from `role:` edges on the graph. No model judgement.
"""

from __future__ import annotations

from ..graph import Gap, GapImportance, GraphNode
from ..ontology import DEFAULT_ONTOLOGY, EventType, RoleSpec
from ..state import AuditState
from .base import BaseAgent


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

        for event in typed_events:
            event_type = self.ontology[event.event_type]
            filled = state.graph.filled_roles(event.id)
            for role in event_type.roles:
                if role.name not in filled:
                    state.gaps.append(self._to_gap(event, event_type, role))

        required = sum(1 for g in state.gaps if g.importance == GapImportance.REQUIRED)
        return f"found {len(state.gaps)} gaps ({required} required)"

    @staticmethod
    def _to_gap(event: GraphNode, event_type: EventType, role: RoleSpec) -> Gap:
        if role.importance == GapImportance.REQUIRED:
            why = (
                f"「{event_type.label_zh}」事件必然存在「{role.label_zh}」，"
                f"但叙述中完全没有出现——这个空缺本身值得注意。"
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
