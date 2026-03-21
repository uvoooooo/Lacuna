"""
Temporal knowledge graph extractor baseline.

Goal:
- Build a minimal architecture for text -> temporal graph extraction.
- Keep implementation simple and easy to extend.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
import re
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple


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
    timestamp: str = "UNKNOWN"
    order: int = -1
    confidence: float = 0.5


@dataclass
class ExtractionResult:
    """Structured extraction output."""

    nodes: List[Node] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)
    timeline: List[Dict[str, str]] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "nodes": [n.__dict__ for n in self.nodes],
            "edges": [e.__dict__ for e in self.edges],
            "timeline": self.timeline,
            "metadata": self.metadata,
        }


class BaseExtractor:
    """Abstract extractor contract."""

    def extract(self, text: str) -> ExtractionResult:
        raise NotImplementedError


class OpenAITemporalExtractor(BaseExtractor):
    """
    LLM-based temporal extractor using OpenAI.

    Expected env:
    - OPENAI_API_KEY: required
    - OPENAI_MODEL: optional, defaults to gpt-4.1-mini
    - OPENAI_BASE_URL: optional, for proxy/compatible endpoints
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAITemporalExtractor")

        try:
            from openai import OpenAI  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "openai package is not installed. Run: pip install openai"
            ) from exc

        kwargs = {"api_key": self.api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        self.client = OpenAI(**kwargs)

    def extract(self, text: str) -> ExtractionResult:
        clean_text = (text or "").strip()
        if not clean_text:
            return ExtractionResult(
                metadata={"extractor": "openai_temporal", "message": "empty input"}
            )

        system_prompt = (
            "You are an information extraction engine. "
            "Extract a temporal knowledge graph from user text and return JSON only."
        )
        user_prompt = (
            "Return strict JSON with keys: nodes, edges, timeline, metadata.\n"
            "Schema:\n"
            "nodes: [{id: str, label: str, node_type: 'entity'|'event'|'time'}]\n"
            "edges: [{source: str, target: str, relation: str, timestamp: str, "
            "order: int, confidence: float}]\n"
            "timeline: [{event_id: str, time: str, order: str, text: str}]\n"
            "metadata: {extractor: str, sentence_count: str}\n"
            "Requirements:\n"
            "- Build event nodes in narrative order.\n"
            "- If time is unknown use 'UNKNOWN'.\n"
            "- Add before edges between consecutive events.\n"
            "- Keep ids stable and short.\n"
            "- Return JSON only, no markdown fences.\n\n"
            f"Text:\n{clean_text}"
        )

        response = self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
                {"role": "user", "content": [{"type": "text", "text": user_prompt}]},
            ],
        )
        raw_text = getattr(response, "output_text", "") or ""
        payload = self._safe_parse_json(raw_text)

        return self._to_result(payload, clean_text)

    def _safe_parse_json(self, text: str) -> Dict[str, object]:
        raw = (text or "").strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            raw = raw.replace("json", "", 1).strip()
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            raw = raw[start : end + 1]
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("OpenAI output is not a JSON object")
        return data

    def _to_result(self, payload: Dict[str, object], source_text: str) -> ExtractionResult:
        nodes: List[Node] = []
        edges: List[Edge] = []
        timeline: List[Dict[str, str]] = []

        raw_nodes = payload.get("nodes", [])
        if isinstance(raw_nodes, list):
            for item in raw_nodes:
                if not isinstance(item, dict):
                    continue
                node_id = str(item.get("id", "")).strip()
                label = str(item.get("label", "")).strip() or node_id
                node_type = str(item.get("node_type", "entity")).strip() or "entity"
                if not node_id:
                    continue
                nodes.append(Node(id=node_id, label=label, node_type=node_type))

        raw_edges = payload.get("edges", [])
        if isinstance(raw_edges, list):
            for item in raw_edges:
                if not isinstance(item, dict):
                    continue
                source = str(item.get("source", "")).strip()
                target = str(item.get("target", "")).strip()
                if not source or not target:
                    continue
                relation = str(item.get("relation", "related_to")).strip() or "related_to"
                timestamp = str(item.get("timestamp", "UNKNOWN")).strip() or "UNKNOWN"
                try:
                    order = int(item.get("order", -1))
                except (TypeError, ValueError):
                    order = -1
                try:
                    confidence = float(item.get("confidence", 0.5))
                except (TypeError, ValueError):
                    confidence = 0.5
                edges.append(
                    Edge(
                        source=source,
                        target=target,
                        relation=relation,
                        timestamp=timestamp,
                        order=order,
                        confidence=confidence,
                    )
                )

        raw_timeline = payload.get("timeline", [])
        if isinstance(raw_timeline, list):
            for item in raw_timeline:
                if not isinstance(item, dict):
                    continue
                timeline.append(
                    {
                        "event_id": str(item.get("event_id", "")).strip(),
                        "time": str(item.get("time", "UNKNOWN")).strip() or "UNKNOWN",
                        "order": str(item.get("order", "")),
                        "text": str(item.get("text", "")).strip(),
                    }
                )

        metadata = {
            "extractor": "openai_temporal",
            "sentence_count": str(max(1, len(re.split(r"[。！？!?;\n]+", source_text)))),
            "model": self.model,
        }
        if isinstance(payload.get("metadata"), dict):
            for k, v in payload["metadata"].items():
                metadata[str(k)] = str(v)

        return ExtractionResult(nodes=nodes, edges=edges, timeline=timeline, metadata=metadata)


class TemporalRuleBasedExtractor(BaseExtractor):
    """
    Very simple temporal baseline:
    1) Split text into sentences
    2) Extract time anchors and entities
    3) Build event nodes in sentence order
    4) Link entities/events/time in a temporal graph
    """

    _SENTENCE_SPLIT = re.compile(r"[。！？!?;\n]+")
    _TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fffA-Za-z0-9_]{2,}")
    _TIME_PATTERN = re.compile(
        r"(\d{4}年\d{1,2}月\d{1,2}日|\d{1,2}月\d{1,2}日|\d{1,2}:\d{2}|"
        r"周[一二三四五六日天]|今天|昨天|前天|今晚|当天|次日|随后|T[+-]?\d+)"
    )
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
        "今天",
        "昨天",
        "随后",
        "然后",
    }

    def extract(self, text: str) -> ExtractionResult:
        clean_text = (text or "").strip()
        if not clean_text:
            return ExtractionResult(
                metadata={"extractor": "temporal_rule_based", "message": "empty input"}
            )

        sentences = self._split_sentences(clean_text)
        nodes, edges, timeline = self._build_temporal_graph(sentences)

        return ExtractionResult(
            nodes=nodes,
            edges=edges,
            timeline=timeline,
            metadata={
                "extractor": "temporal_rule_based",
                "sentence_count": str(len(sentences)),
            },
        )

    def _split_sentences(self, text: str) -> List[str]:
        parts = [p.strip() for p in self._SENTENCE_SPLIT.split(text)]
        return [p for p in parts if p]

    def _extract_entities(self, sentence: str) -> List[str]:
        sentence_no_time = self._TIME_PATTERN.sub(" ", sentence)
        candidates = self._TOKEN_PATTERN.findall(sentence_no_time)
        uniq: List[str] = []
        seen: Set[str] = set()
        for token in candidates:
            if token in self._STOPWORDS:
                continue
            if token not in seen:
                seen.add(token)
                uniq.append(token)
        return uniq

    def _extract_time_anchor(self, sentence: str) -> Optional[str]:
        found = self._TIME_PATTERN.findall(sentence)
        if not found:
            return None
        return found[0]

    def _detect_relation(self, sentence: str) -> str:
        for hint, relation in self._RELATION_HINTS:
            if hint in sentence:
                return relation
        return "co_occurs_with"

    def _build_temporal_graph(
        self, sentences: Iterable[str]
    ) -> Tuple[List[Node], List[Edge], List[Dict[str, str]]]:
        nodes: Dict[str, Node] = {}
        edges: Dict[Tuple[str, str, str, int], Edge] = {}
        timeline: List[Dict[str, str]] = []

        current_time = "UNKNOWN"
        previous_event_id: Optional[str] = None

        for idx, sent in enumerate(sentences):
            time_anchor = self._extract_time_anchor(sent)
            if time_anchor:
                current_time = time_anchor
                time_node_id = f"time::{time_anchor}"
                nodes[time_node_id] = Node(
                    id=time_node_id, label=time_anchor, node_type="time"
                )

            event_id = f"event::{idx + 1}"
            nodes[event_id] = Node(id=event_id, label=sent, node_type="event")
            timeline.append(
                {
                    "event_id": event_id,
                    "time": current_time,
                    "order": str(idx),
                    "text": sent,
                }
            )

            if current_time != "UNKNOWN":
                key = (event_id, f"time::{current_time}", "occurs_at", idx)
                edges[key] = Edge(
                    source=event_id,
                    target=f"time::{current_time}",
                    relation="occurs_at",
                    timestamp=current_time,
                    order=idx,
                    confidence=0.9,
                )

            if previous_event_id:
                key = (previous_event_id, event_id, "before", idx)
                edges[key] = Edge(
                    source=previous_event_id,
                    target=event_id,
                    relation="before",
                    timestamp=current_time,
                    order=idx,
                    confidence=0.95,
                )

            entities = self._extract_entities(sent)
            if len(entities) < 2:
                previous_event_id = event_id
                continue
            relation = self._detect_relation(sent)
            for i in range(len(entities) - 1):
                src, dst = entities[i], entities[i + 1]
                if src == dst:
                    continue
                if src not in nodes:
                    nodes[src] = Node(id=src, label=src, node_type="entity")
                if dst not in nodes:
                    nodes[dst] = Node(id=dst, label=dst, node_type="entity")

                key = (src, dst, relation, idx)
                if key not in edges:
                    edges[key] = Edge(
                        source=src,
                        target=dst,
                        relation=relation,
                        timestamp=current_time,
                        order=idx,
                        confidence=0.6 if relation != "co_occurs_with" else 0.4,
                    )

                event_link_1 = (src, event_id, "participates_in", idx)
                if event_link_1 not in edges:
                    edges[event_link_1] = Edge(
                        source=src,
                        target=event_id,
                        relation="participates_in",
                        timestamp=current_time,
                        order=idx,
                        confidence=0.8,
                    )
                event_link_2 = (dst, event_id, "participates_in", idx)
                if event_link_2 not in edges:
                    edges[event_link_2] = Edge(
                        source=dst,
                        target=event_id,
                        relation="participates_in",
                        timestamp=current_time,
                        order=idx,
                        confidence=0.8,
                    )

            previous_event_id = event_id

        return list(nodes.values()), list(edges.values()), timeline


def extract_graph(text: str, extractor: BaseExtractor | None = None) -> ExtractionResult:
    """Convenience entrypoint used by callers."""
    if extractor is not None:
        return extractor.extract(text)

    if os.getenv("OPENAI_API_KEY"):
        try:
            return OpenAITemporalExtractor().extract(text)
        except Exception:
            # Fallback keeps local development usable even when API call fails.
            return TemporalRuleBasedExtractor().extract(text)

    return TemporalRuleBasedExtractor().extract(text)
