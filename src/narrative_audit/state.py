"""
Shared state for the Narrative Audit Pipeline (表述审阅引擎).

The whole pipeline is built around a single mutable `AuditState` object that
every agent reads from and writes to. This is the "multi-agent + shared state"
design described in docs/MVP_items.md, as opposed to a fully serial chat.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from .graph import Conflict, Gap, NarrativeGraph

# ── Controlled vocabularies ─────────────────────────────────────────────────


class Label:
    """Output of the Label Agent. One claim can carry several labels."""

    FACT = "fact_claim"  # 事实陈述
    OPINION = "opinion"  # 主观评价
    INFERENCE = "inference"  # 推断
    EMOTIONAL = "emotional"  # 情绪化词
    QUOTE = "quote"  # 引用转述
    MISSING_CONTEXT = "missing_context"  # 缺失上下文

    ZH = {
        FACT: "事实陈述",
        OPINION: "主观评价",
        INFERENCE: "推断",
        EMOTIONAL: "情绪化词",
        QUOTE: "引用转述",
        MISSING_CONTEXT: "缺失上下文",
    }


class Checkability:
    """How much of a claim can be verified against external evidence."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class EvidenceStance:
    """Relation between a piece of evidence and a claim."""

    SUPPORT = "support"  # 支持
    REFUTE = "refute"  # 反驳
    PARTIAL = "partial_support"  # 部分支持
    IRRELEVANT = "irrelevant"  # 无关
    NOT_ENOUGH = "not_enough_info"  # 信息不足


# ── Data structures ─────────────────────────────────────────────────────────


@dataclass
class Evidence:
    """A single retrieved piece of evidence and how it relates to a claim."""

    snippet: str
    source: str = "unknown"
    url: str = ""
    stance: str = EvidenceStance.NOT_ENOUGH
    credibility: float = 0.5  # source trustworthiness, 0..1
    freshness: float = 0.5  # time relevance, 0..1

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class Claim:
    """An atomic statement extracted from the input text."""

    id: str
    text: str
    labels: list[str] = field(default_factory=list)
    checkability: str = Checkability.MEDIUM
    evidence_status: str = EvidenceStance.NOT_ENOUGH
    confidence: float = 0.5
    missing_context: list[str] = field(default_factory=list)
    suggested_questions: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)

    def has_label(self, label: str) -> bool:
        return label in self.labels

    @property
    def is_checkable(self) -> bool:
        return self.checkability in (Checkability.HIGH, Checkability.MEDIUM)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "claim": self.text,
            "labels": list(self.labels),
            "labels_zh": [Label.ZH.get(lbl, lbl) for lbl in self.labels],
            "checkability": self.checkability,
            "evidence_status": self.evidence_status,
            "confidence": round(self.confidence, 2),
            "missing_context": list(self.missing_context),
            "suggested_questions": list(self.suggested_questions),
            "evidence": [e.to_dict() for e in self.evidence],
        }


@dataclass
class StepLog:
    """A record of one agent run, for transparency / debugging."""

    agent: str
    message: str
    elapsed_ms: int = 0


@dataclass
class AuditState:
    """The single shared object passed through the whole pipeline."""

    text: str
    language: str = "zh-CN"
    context: str = ""
    claims: list[Claim] = field(default_factory=list)
    graph: NarrativeGraph = field(default_factory=NarrativeGraph)
    conflicts: list[Conflict] = field(default_factory=list)
    gaps: list[Gap] = field(default_factory=list)
    overall_confidence: float = 0.0
    report_markdown: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    log: list[StepLog] = field(default_factory=list)

    def add_log(self, agent: str, message: str, elapsed_ms: int = 0) -> None:
        self.log.append(StepLog(agent=agent, message=message, elapsed_ms=elapsed_ms))

    def to_dict(self) -> dict[str, Any]:
        return {
            "input": {
                "text": self.text,
                "language": self.language,
                "context": self.context,
            },
            "overall_confidence": round(self.overall_confidence, 2),
            "segments": [c.to_dict() for c in self.claims],
            "graph": self.graph.to_dict(),
            "conflicts": [c.to_dict() for c in self.conflicts],
            "gaps": [g.to_dict() for g in self.gaps],
            "report_markdown": self.report_markdown,
            "metadata": self.metadata,
            "log": [s.__dict__ for s in self.log],
        }


class _Timer:
    """Small helper so agents can record their own elapsed time."""

    def __init__(self) -> None:
        self.start = time.perf_counter()

    def ms(self) -> int:
        return int((time.perf_counter() - self.start) * 1000)
