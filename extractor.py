"""
graph extractor baseline.

- Build a minimal architecture for text -> graph extraction.
- Keep implementation simple and easy to extend.
- （Web search integration later）
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Dict, Iterable, List, Sequence, Set, Tuple


@dataclass(frozen=True)
class Node:
    """Graph node."""

    id: str
    label: str
    node_type: str = "entity"


@dataclass(frozen=True)
class Edge:
    """Directed edge between two nodes."""

    source: str
    target: str
    relation: str = "related_to"
    confidence: float = 0.5


@dataclass
class ExtractionResult:
    """Structured extraction output."""

    nodes: List[Node] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "nodes": [n.__dict__ for n in self.nodes],
            "edges": [e.__dict__ for e in self.edges],
            "metadata": self.metadata,
        }


class BaseExtractor:
    """Abstract extractor contract."""

    def extract(self, text: str) -> ExtractionResult:
        raise NotImplementedError


class RuleBasedExtractor(BaseExtractor):
    """
    Very simple baseline:
    1) Split text into sentences
    2) Extract entity candidates with regex
    3) Link nearby entities by co-occurrence
    """

    _SENTENCE_SPLIT = re.compile(r"[。！？!?;\n]+")
    _TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fffA-Za-z0-9_]{2,}")
    _RELATION_HINTS: Sequence[Tuple[str, str]] = (
        ("导致", "causes"),
        ("引发", "causes"),
        ("负责", "responsible_for"),
        ("属于", "belongs_to"),
        ("汇报", "reports_to"),
        ("发现", "finds"),
    )
    _STOPWORDS: Set[str] = {
        "我们",
        "你们",
        "他们",
        "这个",
        "那个",
        "以及",
        "进行",
        "可以",
        "一个",
        "一些",
        "如果",
    }

    def extract(self, text: str) -> ExtractionResult:
        clean_text = (text or "").strip()
        if not clean_text:
            return ExtractionResult(
                metadata={"extractor": "rule_based", "message": "empty input"}
            )

        sentences = self._split_sentences(clean_text)
        nodes = self._build_nodes(sentences)
        edges = self._build_edges(sentences)

        return ExtractionResult(
            nodes=nodes,
            edges=edges,
            metadata={
                "extractor": "rule_based",
                "sentence_count": str(len(sentences)),
            },
        )

    def _split_sentences(self, text: str) -> List[str]:
        parts = [p.strip() for p in self._SENTENCE_SPLIT.split(text)]
        return [p for p in parts if p]

    def _extract_entities(self, sentence: str) -> List[str]:
        candidates = self._TOKEN_PATTERN.findall(sentence)
        uniq: List[str] = []
        seen: Set[str] = set()
        for token in candidates:
            if token in self._STOPWORDS:
                continue
            if token not in seen:
                seen.add(token)
                uniq.append(token)
        return uniq

    def _build_nodes(self, sentences: Iterable[str]) -> List[Node]:
        entity_set: Set[str] = set()
        for sent in sentences:
            entity_set.update(self._extract_entities(sent))
        return [Node(id=e, label=e) for e in sorted(entity_set)]

    def _detect_relation(self, sentence: str) -> str:
        for hint, relation in self._RELATION_HINTS:
            if hint in sentence:
                return relation
        return "co_occurs_with"

    def _build_edges(self, sentences: Iterable[str]) -> List[Edge]:
        edge_map: Dict[Tuple[str, str, str], Edge] = {}
        for sent in sentences:
            entities = self._extract_entities(sent)
            if len(entities) < 2:
                continue
            relation = self._detect_relation(sent)
            for i in range(len(entities) - 1):
                src, dst = entities[i], entities[i + 1]
                if src == dst:
                    continue
                key = (src, dst, relation)
                if key not in edge_map:
                    edge_map[key] = Edge(
                        source=src,
                        target=dst,
                        relation=relation,
                        confidence=0.6 if relation != "co_occurs_with" else 0.4,
                    )
        return list(edge_map.values())


def extract_graph(text: str, extractor: BaseExtractor | None = None) -> ExtractionResult:
    """Convenience entrypoint used by callers."""
    extractor = extractor or RuleBasedExtractor()
    return extractor.extract(text)
