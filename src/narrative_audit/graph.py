"""
Narrative graph structures (叙述图谱).

The graph track of the pipeline turns a narrative into a knowledge graph and
then audits the graph itself:

- `GraphNode` / `GraphEdge` carry a `status` field that separates what the
  text explicitly said (`stated`) from what ontology reasoning derived
  (`inferred`). The two are never mixed up in reports.
- `Conflict` records a contradiction found on the graph.
- `Gap` records a required/expected element that the ontology says should
  exist for an event but is absent from the graph — the "listen to what
  hasn't been said" signal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ── Controlled vocabularies ─────────────────────────────────────────────────


class NodeStatus:
    """Provenance of a node/edge: explicitly stated vs. logically inferred."""

    STATED = "stated"
    INFERRED = "inferred"


class ConflictKind:
    TIMELINE = "timeline"  # 时间线自相矛盾（A 在 B 前又在 B 后）
    EXCLUSIVE = "exclusive_relation"  # 同一对实体间互斥的关系
    ATTRIBUTE = "attribute"  # 同一实体的属性不一致
    SEMANTIC = "semantic"  # 陈述之间的语义矛盾（LLM 判定）


class GapImportance:
    REQUIRED = "required"  # 本体上必然存在的要素；缺失即可疑
    EXPECTED = "expected"  # 通常应该出现的要素；缺失值得追问


# ── Data structures ─────────────────────────────────────────────────────────

# Edges that fill an ontology role use relation = f"{ROLE_RELATION_PREFIX}{role}"
# so the gap detector can check role coverage deterministically.
ROLE_RELATION_PREFIX = "role:"


@dataclass
class GraphNode:
    id: str
    label: str
    node_type: str = "entity"  # entity | event | time
    status: str = NodeStatus.STATED
    event_type: str = ""  # ontology event type, filled by the reasoner
    note: str = ""  # e.g. why an inferred node must exist
    aliases: list[str] = field(default_factory=list)  # labels merged in by entity resolution

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class GraphEdge:
    source: str
    target: str
    relation: str = "related_to"
    status: str = NodeStatus.STATED
    timestamp: str = "UNKNOWN"
    order: int = -1
    confidence: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class Conflict:
    kind: str
    involved: list[str] = field(default_factory=list)  # node/edge descriptions
    description: str = ""
    severity: str = "medium"  # high | medium | low

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class Gap:
    event_id: str
    event_label: str
    role: str
    role_zh: str = ""
    importance: str = GapImportance.EXPECTED
    why_suspicious: str = ""
    suggested_question: str = ""

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class NarrativeGraph:
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    timeline: list[dict[str, str]] = field(default_factory=list)

    def get_node(self, node_id: str) -> GraphNode | None:
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def add_node(self, node: GraphNode) -> GraphNode:
        """Add a node unless one with the same id already exists."""
        existing = self.get_node(node.id)
        if existing is not None:
            return existing
        self.nodes.append(node)
        return node

    def add_edge(self, edge: GraphEdge) -> None:
        for e in self.edges:
            if e.source == edge.source and e.target == edge.target and e.relation == edge.relation:
                return
        self.edges.append(edge)

    def events(self) -> list[GraphNode]:
        return [n for n in self.nodes if n.node_type == "event"]

    def merge_nodes(self, keep_id: str, drop_id: str) -> bool:
        """
        Merge `drop_id` into `keep_id`: rewrite all edges and timeline entries
        to point at the kept node, record the dropped label as an alias, and
        remove the dropped node. Self-loops and duplicate edges created by the
        rewrite are discarded. Returns False if either id is missing or equal.
        """
        keep = self.get_node(keep_id)
        drop = self.get_node(drop_id)
        if keep is None or drop is None or keep_id == drop_id:
            return False

        rewired: list[GraphEdge] = []
        for edge in self.edges:
            source = keep_id if edge.source == drop_id else edge.source
            target = keep_id if edge.target == drop_id else edge.target
            if source == target:
                continue
            if any(
                e.source == source and e.target == target and e.relation == edge.relation
                for e in rewired
            ):
                continue
            edge.source, edge.target = source, target
            rewired.append(edge)
        self.edges = rewired

        for entry in self.timeline:
            if entry.get("event_id") == drop_id:
                entry["event_id"] = keep_id

        for label in (drop.label, *drop.aliases):
            if label and label != keep.label and label not in keep.aliases:
                keep.aliases.append(label)
        self.nodes.remove(drop)
        return True

    def edges_from(self, node_id: str) -> list[GraphEdge]:
        return [e for e in self.edges if e.source == node_id]

    def filled_roles(self, event_id: str) -> set[str]:
        """Ontology roles already attached to an event via role edges."""
        roles: set[str] = set()
        for e in self.edges:
            if e.relation.startswith(ROLE_RELATION_PREFIX) and event_id in (
                e.source,
                e.target,
            ):
                roles.add(e.relation[len(ROLE_RELATION_PREFIX) :])
        return roles

    @property
    def is_empty(self) -> bool:
        return not self.nodes

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "timeline": self.timeline,
        }
