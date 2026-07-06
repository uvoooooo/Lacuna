"""
Agent — Conflict Detector (冲突识别).

Finds contradictions on the narrative graph:

- timeline: cycles in `before` edges (A happens before B and B before A);
- exclusive_relation: the same node pair carries relations that cannot
  coexist;
- attribute: one event is anchored to two different time anchors;
- semantic: contradictions between event statements (LLM only).

The first three checks are deterministic graph checks; only the semantic
check uses the LLM.
"""

from __future__ import annotations

import json

from ..graph import Conflict, ConflictKind, NarrativeGraph
from ..state import AuditState
from .base import BaseAgent

# Relations that cannot both hold between the same ordered node pair.
_EXCLUSIVE_PAIRS: tuple[tuple[str, str], ...] = (
    ("causes", "prevents"),
    ("supports", "opposes"),
    ("hires", "dismisses"),
    ("owns", "stole_from"),
)

_SYSTEM = (
    "You are a contradiction detector for narrative auditing. Given the event "
    "statements of a narrative in order, find pairs that logically contradict "
    "each other (facts, timeline, quantities, attributions). Respond with "
    "JSON only."
)
_USER_TMPL = (
    "Events in narrative order:\n{events}\n\n"
    'Return strict JSON: {{"conflicts": [{{"event_ids": [str, str], '
    '"description": str, "severity": "high"|"medium"|"low"}}]}}\n'
    "Only report genuine logical contradictions, not mere tension or "
    "emotional inconsistency. Empty list if none. Describe in the same "
    "language as the events. No markdown fences."
)


class ConflictDetectorAgent(BaseAgent):
    name = "conflict_detector"
    description = "图上找矛盾：时间线冲突/互斥关系/属性不一致/语义矛盾"

    def _run(self, state: AuditState) -> str:
        if state.graph.is_empty:
            return "no graph"

        self._check_timeline(state)
        self._check_exclusive_relations(state)
        self._check_time_attributes(state)
        semantic = self._check_semantic(state) if self.uses_llm else False

        mode = "graph+llm" if semantic else "graph"
        return f"found {len(state.conflicts)} conflicts ({mode})"

    # ── Deterministic graph checks ──────────────────────────────────────────

    def _check_timeline(self, state: AuditState) -> None:
        """A `before` cycle means the narrative's own order contradicts itself."""
        before: dict[str, set[str]] = {}
        for e in state.graph.edges:
            if e.relation == "before":
                before.setdefault(e.source, set()).add(e.target)

        def reachable(start: str, goal: str) -> bool:
            stack, seen = [start], set()
            while stack:
                cur = stack.pop()
                if cur == goal:
                    return True
                if cur in seen:
                    continue
                seen.add(cur)
                stack.extend(before.get(cur, ()))
            return False

        reported: set[frozenset[str]] = set()
        for src, targets in before.items():
            for dst in targets:
                key = frozenset((src, dst))
                if key in reported:
                    continue
                if reachable(dst, src):
                    reported.add(key)
                    state.conflicts.append(
                        Conflict(
                            kind=ConflictKind.TIMELINE,
                            involved=[self._label(state.graph, src), self._label(state.graph, dst)],
                            description=(
                                f"时间线自相矛盾：「{self._label(state.graph, src)}」与"
                                f"「{self._label(state.graph, dst)}」互为先后。"
                            ),
                            severity="high",
                        )
                    )

    def _check_exclusive_relations(self, state: AuditState) -> None:
        relations: dict[tuple[str, str], set[str]] = {}
        for e in state.graph.edges:
            relations.setdefault((e.source, e.target), set()).add(e.relation)

        for (src, dst), rels in relations.items():
            for a, b in _EXCLUSIVE_PAIRS:
                if a in rels and b in rels:
                    state.conflicts.append(
                        Conflict(
                            kind=ConflictKind.EXCLUSIVE,
                            involved=[self._label(state.graph, src), self._label(state.graph, dst)],
                            description=(
                                f"互斥关系并存：「{self._label(state.graph, src)}」对"
                                f"「{self._label(state.graph, dst)}」同时存在 {a} 与 {b}。"
                            ),
                            severity="high",
                        )
                    )

    def _check_time_attributes(self, state: AuditState) -> None:
        anchors: dict[str, set[str]] = {}
        for e in state.graph.edges:
            if e.relation == "occurs_at":
                anchors.setdefault(e.source, set()).add(e.target)

        for event_id, times in anchors.items():
            if len(times) > 1:
                state.conflicts.append(
                    Conflict(
                        kind=ConflictKind.ATTRIBUTE,
                        involved=[self._label(state.graph, event_id)],
                        description=(
                            f"同一事件被锚定到多个时间：「{self._label(state.graph, event_id)}」"
                            f"({', '.join(sorted(self._label(state.graph, t) for t in times))})。"
                        ),
                        severity="medium",
                    )
                )

    # ── LLM semantic check ──────────────────────────────────────────────────

    def _check_semantic(self, state: AuditState) -> bool:
        events = state.graph.events()
        if len(events) < 2:
            return False
        events_blob = json.dumps(
            [{"id": n.id, "text": n.label} for n in events], ensure_ascii=False
        )
        payload = self.llm.complete_json(_SYSTEM, _USER_TMPL.format(events=events_blob))
        if not payload or not isinstance(payload.get("conflicts"), list):
            return False

        for item in payload["conflicts"]:
            if not isinstance(item, dict):
                continue
            description = str(item.get("description", "")).strip()
            if not description:
                continue
            ids = [str(x) for x in item.get("event_ids", []) if str(x).strip()]
            severity = str(item.get("severity", "medium")).strip()
            state.conflicts.append(
                Conflict(
                    kind=ConflictKind.SEMANTIC,
                    involved=[self._label(state.graph, i) for i in ids],
                    description=description,
                    severity=severity if severity in ("high", "medium", "low") else "medium",
                )
            )
        return True

    @staticmethod
    def _label(graph: NarrativeGraph, node_id: str) -> str:
        node = graph.get_node(node_id)
        return node.label if node else node_id
