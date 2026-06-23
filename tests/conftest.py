"""Shared test fixtures.

`FakeLLM` is a deterministic, offline stand-in for the OpenRouter client. It
inspects the system prompt to figure out which agent is calling and returns a
schema-correct canned response, so tests exercise the LLM code paths without
network access.
"""

from __future__ import annotations

import json
import re

import pytest


class FakeLLM:
    available = True
    model = "fake"

    def complete_json(self, system_prompt: str, user_prompt: str):
        if "claim-splitting" in system_prompt:
            text = user_prompt.split("Text:\n", 1)[-1].strip()
            parts = [p.strip() for p in re.split(r"[。！？!?;；\n]+", text) if p.strip()]
            return {"claims": parts or [text]}

        if "statement-labeling" in system_prompt:
            claims = _claims_after(user_prompt, "Statements:\n")
            return {"items": [_fake_label(c) for c in claims]}

        if "missing-context" in system_prompt:
            claims = _claims_after(user_prompt, "Statements:\n")
            return {
                "items": [
                    {
                        "id": c["id"],
                        "missing_context": ["evidence"],
                        "suggested_questions": ["What evidence supports this?"],
                    }
                    for c in claims
                ]
            }

        if "evidence-matching" in system_prompt:
            idxs = re.findall(r"(?m)^\[(\d+)\]", user_prompt)
            return {
                "items": [
                    {
                        "index": int(i),
                        "stance": "support",
                        "credibility": 0.7,
                        "freshness": 0.6,
                    }
                    for i in idxs
                ]
            }

        return None


def _claims_after(prompt: str, marker: str) -> list[dict]:
    blob = prompt.split(marker, 1)[-1].strip()
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _fake_label(claim: dict) -> dict:
    text = claim.get("text", "")
    if re.search(r"\d|二十|周[一二三四五六日天]", text):
        return {"id": claim["id"], "labels": ["fact_claim"], "checkability": "high"}
    return {"id": claim["id"], "labels": ["opinion"], "checkability": "none"}


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()
