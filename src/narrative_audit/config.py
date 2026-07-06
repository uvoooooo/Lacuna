"""
Lightweight runtime configuration loader.

Reads a TOML file (see configs/default.toml) and builds a configured
`NarrativeAuditPipeline`. Everything is optional: missing keys fall back to
code defaults and environment variables.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from .agents import (
    ClaimSplitterAgent,
    ConflictDetectorAgent,
    EvidenceAgent,
    GapDetectorAgent,
    GraphBuilderAgent,
    LabelAgent,
    MissingContextAgent,
    OntologyReasonerAgent,
    ReportAgent,
)
from .llm import LLMClient
from .pipeline import NarrativeAuditPipeline

DEFAULT_CONFIG_PATH = "configs/default.toml"


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    """Parse a TOML config file into a plain dict."""
    p = Path(path)
    if not p.exists():
        return {}
    with p.open("rb") as fh:
        return tomllib.load(fh)


def pipeline_from_config(
    config: dict[str, Any] | None = None,
    path: str | Path = DEFAULT_CONFIG_PATH,
) -> NarrativeAuditPipeline:
    """Build a pipeline from a config dict (or load it from `path`)."""
    cfg = config if config is not None else load_config(path)

    llm_cfg = cfg.get("llm", {})
    llm = LLMClient(
        model=llm_cfg.get("model"),
        base_url=llm_cfg.get("base_url"),
    )

    evidence_cfg = cfg.get("evidence", {})
    search_fn = None
    if evidence_cfg.get("backend") == "mock":
        from .search import make_mock_search

        search_fn = make_mock_search()

    agents = [
        ClaimSplitterAgent(llm),
        LabelAgent(llm),
        MissingContextAgent(llm),
        GraphBuilderAgent(llm),
        OntologyReasonerAgent(llm),
        ConflictDetectorAgent(llm),
        GapDetectorAgent(llm),
        EvidenceAgent(llm, search_fn=search_fn, max_hits=int(evidence_cfg.get("max_hits", 5))),
        ReportAgent(llm),
    ]
    return NarrativeAuditPipeline(llm=llm, agents=agents)
