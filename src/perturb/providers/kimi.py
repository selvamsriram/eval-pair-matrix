"""Kimi K2.x via Azure AI Foundry's OpenAI-compatible chat completions endpoint.

Tuned for reasoning models that spend most of their output budget on internal
thinking. Differences from azure_openai:
  - max_tokens floor = 32k (no cascade-retry; Kimi burns minutes per attempt)
  - Single shot on length truncation (retrying just doubles cost)
  - 600s socket timeout (Kimi calls routinely take 60-300s)
  - reasoning_effort='medium' in request body (Azure Foundry passes it through
    for reasoning models when supported; ignored when not — observable via 400)

Env (see .env.example):
  AZURE_KIMI_ENDPOINT  full URL incl. /models/chat/completions and api-version
  AZURE_KIMI_API_KEY
  AZURE_KIMI_MODEL     e.g. "Kimi-K2.6"
"""
from __future__ import annotations

import json

import httpx

from ..config import env
from . import register
from .azure_openai import ProviderIncomplete  # shared exception class
from .base import ProviderResponse


# Reasoning models spend most of their output budget on internal thinking;
# starting low and retrying just wastes wall-clock + tokens.
KIMI_TOKEN_FLOOR = 32_768
KIMI_TIMEOUT_S = 600.0
KIMI_REASONING_EFFORT = "medium"  # low | medium | high; passed through if model accepts


class KimiProvider:
    name = "kimi"

    def __init__(self, endpoint: str, api_key: str, model: str) -> None:
        self.endpoint = endpoint
        self.api_key = api_key
        self.model = model
        self._client = httpx.Client(timeout=KIMI_TIMEOUT_S)

    def complete_json(
        self,
        *,
        system: str | None,
        user: str,
        schema_hint: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> ProviderResponse:
        sys_full = system or ""
        if schema_hint:
            sys_full = (sys_full + "\n\n" if sys_full else "") + (
                "Return a single JSON object. No prose, no code fences. "
                "Conform to this shape:\n" + schema_hint
            )

        messages: list[dict] = []
        if sys_full:
            messages.append({"role": "system", "content": sys_full})
        messages.append({"role": "user", "content": user})

        # Always run at the floor — see module docstring.
        budget = max(max_tokens, KIMI_TOKEN_FLOOR)

        body: dict = {
            "model": self.model,
            "messages": messages,
            "max_tokens": budget,
            "response_format": {"type": "json_object"},
            "reasoning_effort": KIMI_REASONING_EFFORT,
        }
        if temperature is not None:
            body["temperature"] = temperature

        data = self._post(body)
        choice = (data.get("choices") or [{}])[0]
        finish = choice.get("finish_reason")
        text = (choice.get("message") or {}).get("content") or ""

        if finish == "stop":
            parsed = _strict_json(text)
            if parsed is None:
                raise ProviderIncomplete(
                    f"finish_reason=stop but JSON unparseable; "
                    f"text_len={len(text)} preview={text[:200]!r}",
                    reason="unparseable",
                )
            usage = data.get("usage") or {}
            return ProviderResponse(
                text=text,
                parsed_json=parsed,
                input_tokens=usage.get("prompt_tokens"),
                output_tokens=usage.get("completion_tokens"),
                raw=data,
            )

        # Length / content_filter / tool_calls / etc — no retry on Kimi.
        reason = "max_output_tokens" if finish == "length" else (str(finish) or "unknown")
        usage = data.get("usage") or {}
        raise ProviderIncomplete(
            f"finish_reason={finish!r} budget={budget} "
            f"usage={usage} text_preview={text[:200]!r}",
            reason=reason,
        )

    def _post(self, body: dict) -> dict:
        headers = {"api-key": self.api_key, "Content-Type": "application/json"}
        resp = self._client.post(self.endpoint, json=body, headers=headers)
        if resp.status_code >= 400:
            try:
                err_body = resp.json()
            except Exception:  # noqa: BLE001
                err_body = {"text": resp.text[:500]}
            err = (err_body or {}).get("error") or {}
            code = err.get("code") or str(resp.status_code)
            msg = err.get("message") or str(err_body)[:400]
            raise ProviderIncomplete(
                f"HTTP {resp.status_code} {code}: {msg}",
                reason=f"http_{resp.status_code}",
            )
        return resp.json()


def _strict_json(text: str):
    text = (text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _factory() -> KimiProvider:
    endpoint = env("AZURE_KIMI_ENDPOINT")
    key = env("AZURE_KIMI_API_KEY")
    model = env("AZURE_KIMI_MODEL", "kimi-k2")
    if not endpoint or not key:
        raise RuntimeError(
            "Kimi provider not configured: set AZURE_KIMI_ENDPOINT and "
            "AZURE_KIMI_API_KEY in .env."
        )
    return KimiProvider(endpoint=endpoint, api_key=key, model=model)


register("kimi", _factory)
