"""Tests for the TOML config loader."""

from narrative_audit.config import load_config, pipeline_from_config


def test_load_default_config():
    cfg = load_config("configs/default.toml")
    assert cfg["evidence"]["max_hits"] == 5
    assert cfg["llm"]["model"]


def test_missing_config_returns_empty_dict():
    assert load_config("configs/does_not_exist.toml") == {}


def test_pipeline_from_config_builds_all_agents():
    pipeline = pipeline_from_config(path="configs/default.toml")
    assert len(pipeline.agents) == 10


def test_pipeline_from_config_mock_backend_enables_search():
    from narrative_audit.agents import EvidenceAgent

    cfg = {"evidence": {"backend": "mock", "max_hits": 3}}
    pipeline = pipeline_from_config(cfg)
    evidence_agent = next(a for a in pipeline.agents if isinstance(a, EvidenceAgent))
    assert evidence_agent.search_fn is not None
    assert evidence_agent.max_hits == 3
