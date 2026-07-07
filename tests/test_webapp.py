"""Tests for the local web app (FastAPI)."""

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from narrative_audit.pipeline import NarrativeAuditPipeline  # noqa: E402
from narrative_audit.webapp import create_app  # noqa: E402

_TEXT = "我在公司勤勤恳恳工作了六年。上周五我被开除了。这是赤裸裸的压榨！"


def _client(llm) -> TestClient:
    return TestClient(create_app(NarrativeAuditPipeline(llm=llm)))


def test_index_serves_page(fake_llm):
    resp = _client(fake_llm).get("/")
    assert resp.status_code == 200
    assert "LACUNA" in resp.text
    assert "/api/audit" in resp.text


def test_audit_returns_card(fake_llm):
    resp = _client(fake_llm).post("/api/audit", json={"text": _TEXT, "context": "社媒发帖"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["card_html"].startswith("<!DOCTYPE html>")
    assert "没告诉你" in data["card_html"]
    assert data["gaps"] >= 1
    assert 0.0 <= data["confidence"] <= 1.0


def test_audit_rejects_empty_text(fake_llm):
    resp = _client(fake_llm).post("/api/audit", json={"text": "   "})
    assert resp.status_code == 400


def test_audit_rejects_oversized_text(fake_llm):
    resp = _client(fake_llm).post("/api/audit", json={"text": "字" * 4001})
    assert resp.status_code == 400


def test_audit_without_llm_returns_503():
    class _NoLLM:
        available = False
        model = "none"

        def complete_json(self, *_args, **_kwargs):
            return None

    resp = _client(_NoLLM()).post("/api/audit", json={"text": _TEXT})
    assert resp.status_code == 503
    assert "LLM" in resp.json()["error"]
