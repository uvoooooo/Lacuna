"""
Narrative Audit Pipeline (表述审阅引擎).

A multi-agent + shared-state pipeline that takes a piece of narrative text and
breaks it down into: what it says, what it implies, what it leaves out, and
whether the evidence is sufficient — without judging who is right or wrong.

Quick start:

    from narrative_audit import audit
    state = audit("我勤勤恳恳工作六年，上周五突然被开除，连补偿都没有。")
    print(state.report_markdown)
"""

from .config import load_config, pipeline_from_config
from .graph import (
    Conflict,
    Gap,
    GraphEdge,
    GraphNode,
    NarrativeGraph,
    NodeStatus,
)
from .llm import LLMClient
from .ontology import DEFAULT_ONTOLOGY, EventType, OntologyError, RoleSpec, load_ontology
from .pipeline import NarrativeAuditPipeline, audit
from .state import (
    AuditState,
    Checkability,
    Claim,
    Evidence,
    EvidenceStance,
    Label,
)
from .viz import to_dot, to_mermaid

__all__ = [
    "NarrativeAuditPipeline",
    "audit",
    "load_config",
    "pipeline_from_config",
    "AuditState",
    "Claim",
    "Evidence",
    "Label",
    "Checkability",
    "EvidenceStance",
    "NarrativeGraph",
    "GraphNode",
    "GraphEdge",
    "NodeStatus",
    "Conflict",
    "Gap",
    "DEFAULT_ONTOLOGY",
    "EventType",
    "RoleSpec",
    "OntologyError",
    "load_ontology",
    "to_dot",
    "to_mermaid",
    "LLMClient",
]

__version__ = "0.1.0"
