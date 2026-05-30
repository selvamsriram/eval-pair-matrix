"""Anthropic Messages API. Used to swap providers via --model flag."""
from __future__ import annotations

import json

import httpx

from ..config import env
from . import register
from .base import ProviderResponse


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model
        self._client = httpx.Client(timeout=120.0)

    def complete_json(
        self,
        *,
        system: str | None,
        user: str,
        schema_hint: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> ProviderResponse:
        sys_full = system or ""
        if schema_hint:
            sys_full = (sys_full + "\n\n" if sys_full else "") + (
                "Return a single JSON object only. No prose, no code fences.\n"
                "Conform to this shape:\n" + schema_hint
            )

        body: dict = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": user}],
        }
        if sys_full:
            body["system"] = sys_full

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        resp = self._client.post("https://api.anthropic.com/v1/messages", json=body, headers=headers)
        resp.raise_for_status()
        data = resp.json()

        text = "".join(
            block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"
        )
        parsed = _safe_json(text)
        usage = data.get("usage") or {}
        return ProviderResponse(
            text=text,
            parsed_json=parsed,
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            raw=data,
        )


def _safe_json(text: str):
    text = text.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        if text.startswith("```"):
            stripped = text.strip("`")
            if "\n" in stripped:
                stripped = stripped.split("\n", 1)[1]
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                return None
        return None


def _factory() -> AnthropicProvider:
    key = env("ANTHROPIC_API_KEY")
    model = env("ANTHROPIC_MODEL", "claude-sonnet-4-5")
    if not key:
        raise RuntimeError("Anthropic provider not configured: set ANTHROPIC_API_KEY in .env.")
    return AnthropicProvider(api_key=key, model=model)


register("anthropic", _factory)
