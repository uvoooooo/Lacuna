"""
Agent — Graph Builder (叙述 → 知识图谱).

Turns the raw narrative into a knowledge graph: entities, events, time
anchors and relations, preserving narrative order. Everything produced here
is marked `stated` — it is what the text explicitly said.

Uses the LLM when available; falls back to the rule-based temporal extractor
(`extractor.TemporalRuleBasedExtractor`) offline.
"""

from __future__ import annotations

from ..extractor import TemporalRuleBasedExtractor
from ..graph import GraphEdge, GraphNode, NodeStatus
from ..state import AuditState
from .base import BaseAgent

_SYSTEM = (
    "You are a graph-extraction engine for narrative auditing. Extract a "
    "knowledge graph (entities, events, time anchors, relations) from the "
    "user's narrative, preserving narrative order. Respond with JSON only."
)
_USER_TMPL = (
    "Return strict JSON with keys: nodes, edges, timeline.\n"
    "Schema:\n"
    'nodes: [{{"id": str, "label": str, "node_type": "entity"|"event"|"time"}}]\n'
    'edges: [{{"source": str, "target": str, "relation": str, '
    '"timestamp": str, "order": int, "confidence": float}}]\n'
    'timeline: [{{"event_id": str, "time": str, "order": str, "text": str}}]\n'
    "Rules:\n"
    "- One event node per action/happening, in narrative order.\n"
    "- Use 'UNKNOWN' when time is not given.\n"
    "- Add 'before' edges between consecutive events.\n"
    "- Link participants to events with 'participates_in' edges.\n"
    "- Keep ids short and stable. Keep labels in the original language.\n"
    "- Only extract what the text actually states; do not infer.\n"
    "- No markdown fences.\n\n"
    "Text:\n{text}"
)


class GraphBuilderAgent(BaseAgent):
    name = "graph_builder"
    description = "叙述 → 知识图谱（实体/事件/时间/关系，标 stated）"

    def _run(self, state: AuditState) -> str:
        text = (state.text or "").strip()
        if not text:
            return "empty input"

        applied = False
        if self.uses_llm:
            applied = self._with_llm(state, text)
        if not applied:
            self._fallback(state, text)

        mode = "llm" if applied else "rule-based"
        return (
            f"built graph: {len(state.graph.nodes)} nodes, {len(state.graph.edges)} edges ({mode})"
        )

    def _with_llm(self, state: AuditState, text: str) -> bool:
        payload = self.llm.complete_json(_SYSTEM, _USER_TMPL.format(text=text))
        if not payload or not isinstance(payload.get("nodes"), list):
            return False

        for item in payload.get("nodes", []):
            if not isinstance(item, dict):
                continue
            node_id = str(item.get("id", "")).strip()
            if not node_id:
                continue
            state.graph.add_node(
                GraphNode(
                    id=node_id,
                    label=str(item.get("label", "")).strip() or node_id,
                    node_type=str(item.get("node_type", "entity")).strip() or "entity",
                    status=NodeStatus.STATED,
                )
            )

        for item in payload.get("edges", []):
            if not isinstance(item, dict):
                continue
            source = str(item.get("source", "")).strip()
            target = str(item.get("target", "")).strip()
            if not source or not target:
                continue
            try:
                order = int(item.get("order", -1))
            except (TypeError, ValueError):
                order = -1
            try:
                confidence = float(item.get("confidence", 0.5))
            except (TypeError, ValueError):
                confidence = 0.5
            state.graph.add_edge(
                GraphEdge(
                    source=source,
                    target=target,
                    relation=str(item.get("relation", "related_to")).strip() or "related_to",
                    status=NodeStatus.STATED,
                    timestamp=str(item.get("timestamp", "UNKNOWN")).strip() or "UNKNOWN",
                    order=order,
                    confidence=confidence,
                )
            )

        raw_timeline = payload.get("timeline", [])
        if isinstance(raw_timeline, list):
            for item in raw_timeline:
                if not isinstance(item, dict):
                    continue
                state.graph.timeline.append(
                    {
                        "event_id": str(item.get("event_id", "")).strip(),
                        "time": str(item.get("time", "UNKNOWN")).strip() or "UNKNOWN",
                        "order": str(item.get("order", "")),
                        "text": str(item.get("text", "")).strip(),
                    }
                )
        return not state.graph.is_empty

    @staticmethod
    def _fallback(state: AuditState, text: str) -> None:
        result = TemporalRuleBasedExtractor().extract(text)
        for node in result.nodes:
            state.graph.add_node(
                GraphNode(
                    id=node.id,
                    label=node.label,
                    node_type=node.node_type,
                    status=NodeStatus.STATED,
                )
            )
        for edge in result.edges:
            state.graph.add_edge(
                GraphEdge(
                    source=edge.source,
                    target=edge.target,
                    relation=edge.relation,
                    status=NodeStatus.STATED,
                    timestamp=edge.timestamp,
                    order=edge.order,
                    confidence=edge.confidence,
                )
            )
        state.graph.timeline.extend(result.timeline)
