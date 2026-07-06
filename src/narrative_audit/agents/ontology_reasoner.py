"""
Agent — Ontology Reasoner (本体推理).

Aligns each event node with an ontology event type, then derives the
non-obvious nodes: participants and preconditions that the narrative entails
but never states (a dismissal entails an employer, a reason, a prior
employment relation...). Derived nodes/edges are marked `inferred` and role
fills are recorded as `role:<name>` edges so the gap detector can check
coverage deterministically.

With an LLM, typing and role filling are grounded in the text. Offline, the
fallback only types events by ontology keywords — it never invents content.
"""

from __future__ import annotations

import json

from ..graph import ROLE_RELATION_PREFIX, GraphEdge, GraphNode, NodeStatus
from ..ontology import DEFAULT_ONTOLOGY, EventType, catalogue_for_prompt, match_event_type
from ..state import AuditState
from .base import BaseAgent

_SYSTEM = (
    "You are an ontology reasoner for narrative auditing. Given a knowledge "
    "graph extracted from a narrative and an event-type catalogue, classify "
    "each event and fill its ontology roles — including implicit participants "
    "the text entails but never names. Respond with JSON only."
)
_USER_TMPL = (
    "Event-type catalogue (event types and their roles):\n{catalogue}\n\n"
    "Events extracted from the narrative:\n{events}\n\n"
    "Existing entity nodes:\n{entities}\n\n"
    "Original text:\n{text}\n\n"
    "For each event, return:\n"
    '{{"events": [{{"event_id": str, "event_type": str|null, '
    '"filled_roles": [{{"role": str, "filler_label": str, '
    '"existing_node_id": str|null, "stated": bool, "note": str}}]}}]}}\n'
    "Rules:\n"
    "- event_type must come from the catalogue, or null if nothing fits.\n"
    "- Fill a role only when the text states it OR logically entails it "
    "(e.g. 被开除 entails an employer even if unnamed). Never guess beyond "
    "logical entailment. Leave truly unknown roles unfilled.\n"
    "- NEVER fill a role with placeholders such as 未提及/未知/not "
    "provided/unknown/N/A. If the content is absent, omit the role entirely "
    "so it can be reported as a gap.\n"
    "- stated=true if the text explicitly provides the filler, false if it "
    "is only entailed.\n"
    "- Reuse existing_node_id when the filler is already a graph node.\n"
    "- Keep filler_label in the original language. No markdown fences."
)


# Filler labels that actually mean "absent" — treating them as fills would
# defeat the gap detector, so they are dropped.
_PLACEHOLDER_SUBSTRINGS = ("未提及", "未知", "不详", "unknown", "not provided", "not mentioned")
_PLACEHOLDER_EXACT = ("无", "none", "n/a", "null")


class OntologyReasonerAgent(BaseAgent):
    name = "ontology_reasoner"
    description = "事件对齐本体类型，推理不显然的隐含节点（标 inferred）"

    def __init__(self, llm=None, ontology: dict[str, EventType] | None = None) -> None:
        super().__init__(llm)
        self.ontology = ontology or DEFAULT_ONTOLOGY

    def _run(self, state: AuditState) -> str:
        events = state.graph.events()
        if not events:
            return "no events in graph"

        applied = False
        if self.uses_llm:
            applied = self._with_llm(state)
        if not applied:
            self._fallback(state)

        typed = sum(1 for n in state.graph.events() if n.event_type)
        inferred = sum(1 for n in state.graph.nodes if n.status == NodeStatus.INFERRED)
        mode = "llm" if applied else "keyword"
        return f"typed {typed} events, inferred {inferred} implicit nodes ({mode})"

    # ── LLM path ────────────────────────────────────────────────────────────

    def _with_llm(self, state: AuditState) -> bool:
        events_blob = json.dumps(
            [{"event_id": n.id, "text": n.label} for n in state.graph.events()],
            ensure_ascii=False,
        )
        entities_blob = json.dumps(
            [{"id": n.id, "label": n.label} for n in state.graph.nodes if n.node_type == "entity"],
            ensure_ascii=False,
        )
        payload = self.llm.complete_json(
            _SYSTEM,
            _USER_TMPL.format(
                catalogue=catalogue_for_prompt(self.ontology),
                events=events_blob,
                entities=entities_blob,
                text=state.text,
            ),
        )
        if not payload or not isinstance(payload.get("events"), list):
            return False

        for item in payload["events"]:
            if not isinstance(item, dict):
                continue
            event = state.graph.get_node(str(item.get("event_id", "")))
            if event is None or event.node_type != "event":
                continue
            event_type = str(item.get("event_type") or "").strip()
            if event_type in self.ontology:
                event.event_type = event_type
            fills = item.get("filled_roles", [])
            if isinstance(fills, list):
                for fill in fills:
                    if isinstance(fill, dict):
                        self._apply_fill(state, event, fill)
        return True

    def _apply_fill(self, state: AuditState, event: GraphNode, fill: dict) -> None:
        role = str(fill.get("role", "")).strip()
        label = str(fill.get("filler_label", "")).strip()
        if not role or not label:
            return
        lowered = label.lower()
        if lowered in _PLACEHOLDER_EXACT or any(p in lowered for p in _PLACEHOLDER_SUBSTRINGS):
            return
        stated = bool(fill.get("stated", False))
        existing_id = str(fill.get("existing_node_id") or "").strip()

        node = state.graph.get_node(existing_id) if existing_id else None
        if node is None:
            node = state.graph.add_node(
                GraphNode(
                    id=f"{event.id}::{role}",
                    label=label,
                    node_type="entity",
                    status=NodeStatus.STATED if stated else NodeStatus.INFERRED,
                    note=str(fill.get("note", "")).strip(),
                )
            )
        state.graph.add_edge(
            GraphEdge(
                source=event.id,
                target=node.id,
                relation=f"{ROLE_RELATION_PREFIX}{role}",
                status=NodeStatus.STATED if stated else NodeStatus.INFERRED,
                confidence=0.9 if stated else 0.6,
            )
        )

    # ── Offline fallback ─────────────────────────────────────────────────────

    def _fallback(self, state: AuditState) -> None:
        # Deterministic: keyword typing only. Role filling needs grounding in
        # the text, so without an LLM we leave roles empty and let the gap
        # detector surface them all as open questions.
        for event in state.graph.events():
            matched = match_event_type(event.label, self.ontology)
            if matched is not None:
                event.event_type = matched.name
