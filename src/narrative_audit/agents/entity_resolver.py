"""
Agent — Entity Resolver (实体消解 / 共指合并).

Runs right after GraphBuilder. Narratives name the same actor many ways
(部门经理 / 经理 / 他); left unmerged, those duplicates silently break the
rest of the graph track — conflicts don't fire because contradicting
attributes sit on "different" nodes, and gaps false-positive because the role
is filled by an unmerged twin.

The LLM proposes which entity nodes co-refer (this genuinely needs judgement,
especially in Chinese where pronouns drop); applying a merge is deterministic
(`NarrativeGraph.merge_nodes`) and every accepted merge is validated: ids must
exist, both nodes must be entities, and low-confidence proposals are ignored.
Merged labels are kept as `aliases` on the surviving node, and the merge log
lands in `state.metadata["entity_merges"]` so reports stay auditable.

Offline the fallback only merges entities whose labels are exactly equal after
whitespace stripping — it never guesses.
"""

from __future__ import annotations

import json

from ..state import AuditState
from .base import BaseAgent

_SYSTEM = (
    "You are an entity-resolution engine for narrative auditing. Given the "
    "entity nodes extracted from one narrative, decide which nodes refer to "
    "the same real-world referent (the same person, organization or thing "
    "mentioned via different names, titles or pronouns). Respond with JSON "
    "only."
)
_USER_TMPL = (
    "Entity nodes:\n{entities}\n\n"
    "Original text:\n{text}\n\n"
    "Return:\n"
    '{{"merges": [{{"keep_id": str, "drop_ids": [str], "canonical_label": str, '
    '"reason": str, "confidence": float}}]}}\n'
    "Rules:\n"
    "- Merge only when the text makes it clear the mentions denote the same "
    "referent. When in doubt, do not merge — a wrong merge is worse than a "
    "missed one.\n"
    "- keep_id and drop_ids must be ids from the list; keep_id must not "
    "appear in drop_ids.\n"
    "- canonical_label: the most specific mention (proper name > title > "
    "pronoun), in the original language.\n"
    "- confidence in [0,1]. Return an empty list when nothing co-refers.\n"
    "- No markdown fences."
)


class EntityResolverAgent(BaseAgent):
    name = "entity_resolver"
    description = "实体消解：合并同指实体（不同称呼/代词 → 同一节点）"

    def __init__(self, llm=None, min_confidence: float = 0.6) -> None:
        super().__init__(llm)
        self.min_confidence = min_confidence

    def _run(self, state: AuditState) -> str:
        entities = [n for n in state.graph.nodes if n.node_type == "entity"]
        if len(entities) < 2:
            return "fewer than 2 entities, nothing to resolve"

        merged = 0
        mode = "exact-label"
        if self.uses_llm:
            result = self._with_llm(state)
            if result is not None:
                merged, mode = result, "llm"
        if mode != "llm":
            merged = self._fallback(state)

        return f"merged {merged} entity nodes ({mode})"

    # ── LLM path ────────────────────────────────────────────────────────────

    def _with_llm(self, state: AuditState) -> int | None:
        entities = [n for n in state.graph.nodes if n.node_type == "entity"]
        blob = json.dumps([{"id": n.id, "label": n.label} for n in entities], ensure_ascii=False)
        payload = self.llm.complete_json(_SYSTEM, _USER_TMPL.format(entities=blob, text=state.text))
        if not payload or not isinstance(payload.get("merges"), list):
            return None

        merged = 0
        for item in payload["merges"]:
            if not isinstance(item, dict):
                continue
            merged += self._apply_merge(state, item)
        return merged

    def _apply_merge(self, state: AuditState, item: dict) -> int:
        keep_id = str(item.get("keep_id", "")).strip()
        drop_ids = item.get("drop_ids", [])
        if not keep_id or not isinstance(drop_ids, list):
            return 0
        try:
            confidence = float(item.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        if confidence < self.min_confidence:
            return 0

        keep = state.graph.get_node(keep_id)
        if keep is None or keep.node_type != "entity":
            return 0

        merged = 0
        for raw in drop_ids:
            drop_id = str(raw).strip()
            drop = state.graph.get_node(drop_id)
            if drop_id == keep_id or drop is None or drop.node_type != "entity":
                continue
            dropped_label = drop.label
            if not state.graph.merge_nodes(keep_id, drop_id):
                continue
            merged += 1
            state.metadata.setdefault("entity_merges", []).append(
                {
                    "kept": keep_id,
                    "dropped": drop_id,
                    "dropped_label": dropped_label,
                    "reason": str(item.get("reason", "")).strip(),
                    "confidence": confidence,
                }
            )

        canonical = str(item.get("canonical_label", "")).strip()
        if merged and canonical and canonical != keep.label:
            if keep.label not in keep.aliases:
                keep.aliases.append(keep.label)
            if canonical in keep.aliases:
                keep.aliases.remove(canonical)
            keep.label = canonical
        return merged

    # ── Offline fallback ─────────────────────────────────────────────────────

    def _fallback(self, state: AuditState) -> int:
        """Deterministic: merge only exact duplicate labels, never guess."""
        seen: dict[str, str] = {}  # normalized label -> node id to keep
        merged = 0
        for node in list(state.graph.nodes):
            if node.node_type != "entity":
                continue
            key = node.label.strip()
            if not key:
                continue
            if key in seen:
                if state.graph.merge_nodes(seen[key], node.id):
                    merged += 1
                    state.metadata.setdefault("entity_merges", []).append(
                        {
                            "kept": seen[key],
                            "dropped": node.id,
                            "dropped_label": key,
                            "reason": "identical label",
                            "confidence": 1.0,
                        }
                    )
            else:
                seen[key] = node.id
        return merged
