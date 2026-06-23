"""
Thin LLM client wrapper (OpenRouter).

Agents call `LLMClient.complete_json(...)` to get structured output. The client
talks to OpenRouter via the OpenAI-compatible Chat Completions API. If no API
key is configured (or the SDK is missing / the call fails), `available` is
False and agents fall back to their structural heuristics, so the pipeline
still runs offline.
"""

from __future__ import annotations

import json
import os
from typing import Any

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-4o-mini"


class LLMClient:
    """OpenRouter-backed JSON completion with graceful offline fallback."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        self.model = model or os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL)
        self.base_url = base_url or os.getenv("OPENROUTER_BASE_URL", DEFAULT_BASE_URL)
        self._client = None

        if not self.api_key:
            return
        try:
            from openai import OpenAI  # type: ignore
        except ImportError:
            return

        kwargs: dict[str, Any] = {"api_key": self.api_key, "base_url": self.base_url}
        headers = self._optional_headers()
        if headers:
            kwargs["default_headers"] = headers
        try:
            self._client = OpenAI(**kwargs)
        except Exception:
            self._client = None

    @staticmethod
    def _optional_headers() -> dict[str, str]:
        # OpenRouter uses these for attribution/leaderboards; both optional.
        headers: dict[str, str] = {}
        site = os.getenv("OPENROUTER_SITE_URL")
        app = os.getenv("OPENROUTER_APP_NAME")
        if site:
            headers["HTTP-Referer"] = site
        if app:
            headers["X-Title"] = app
        return headers

    @property
    def available(self) -> bool:
        return self._client is not None

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> dict[str, Any] | None:
        """Return a parsed JSON object, or None if the call is unavailable/fails."""
        if self._client is None:
            return None
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        raw = self._chat(messages, json_mode=True)
        if raw is None:
            # Some models reject response_format; retry without it.
            raw = self._chat(messages, json_mode=False)
        if raw is None:
            return None
        return self._safe_parse_json(raw)

    def _chat(self, messages: list[dict[str, str]], json_mode: bool) -> str | None:
        kwargs: dict[str, Any] = {"model": self.model, "messages": messages}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            response = self._client.chat.completions.create(**kwargs)
            return response.choices[0].message.content or ""
        except Exception:
            return None

    @staticmethod
    def _safe_parse_json(text: str) -> dict[str, Any] | None:
        raw = (text or "").strip()
        if not raw:
            return None
        if raw.startswith("```"):
            raw = raw.strip("`")
            raw = raw.replace("json", "", 1).strip()
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            raw = raw[start : end + 1]
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None
