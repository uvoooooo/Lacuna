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

        if "graph-extraction" in system_prompt:
            text = user_prompt.split("Text:\n", 1)[-1].strip()
            sentences = [s.strip() for s in re.split(r"[。！？!?;；\n]+", text) if s.strip()]
            nodes = [
                {"id": f"e{i + 1}", "label": s, "node_type": "event"}
                for i, s in enumerate(sentences)
            ]
            edges = [
                {
                    "source": f"e{i + 1}",
                    "target": f"e{i + 2}",
                    "relation": "before",
                    "timestamp": "UNKNOWN",
                    "order": i,
                    "confidence": 0.9,
                }
                for i in range(len(sentences) - 1)
            ]
            timeline = [
                {"event_id": f"e{i + 1}", "time": "UNKNOWN", "order": str(i), "text": s}
                for i, s in enumerate(sentences)
            ]
            return {"nodes": nodes, "edges": edges, "timeline": timeline}

        if "entity-resolution" in system_prompt:
            blob = user_prompt.split("Entity nodes:\n", 1)[-1]
            blob = blob.split("\n\nOriginal text:", 1)[0].strip()
            try:
                entities = json.loads(blob)
            except json.JSONDecodeError:
                entities = []
            # Canned coreference: merge when one label contains the other,
            # keeping the node with the more specific (longer) label.
            merges = []
            absorbed: set[str] = set()
            for a in entities:
                if a["id"] in absorbed:
                    continue
                drops = [
                    b["id"]
                    for b in entities
                    if b["id"] != a["id"]
                    and b["id"] not in absorbed
                    and b["label"] in a["label"]
                    and len(b["label"]) < len(a["label"])
                ]
                if drops:
                    absorbed.update(drops)
                    merges.append(
                        {
                            "keep_id": a["id"],
                            "drop_ids": drops,
                            "canonical_label": a["label"],
                            "reason": "same referent, shorter mention",
                            "confidence": 0.9,
                        }
                    )
            return {"merges": merges}

        if "ontology reasoner" in system_prompt:
            blob = user_prompt.split("Events extracted from the narrative:\n", 1)[-1]
            blob = blob.split("\n\nExisting entity nodes:", 1)[0].strip()
            try:
                events = json.loads(blob)
            except json.JSONDecodeError:
                events = []
            out = []
            for ev in events:
                if "开除" in ev.get("text", ""):
                    out.append(
                        {
                            "event_id": ev["event_id"],
                            "event_type": "dismissal",
                            "filled_roles": [
                                {
                                    "role": "employer",
                                    "filler_label": "部门经理",
                                    "existing_node_id": None,
                                    "stated": True,
                                    "note": "",
                                },
                                {
                                    "role": "prior_employment",
                                    "filler_label": "在先劳动关系（被开除即蕴含）",
                                    "existing_node_id": None,
                                    "stated": False,
                                    "note": "被开除必然存在在先劳动关系",
                                },
                            ],
                        }
                    )
                else:
                    out.append({"event_id": ev["event_id"], "event_type": None, "filled_roles": []})
            return {"events": out}

        if "contradiction detector" in system_prompt:
            return {"conflicts": []}

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
