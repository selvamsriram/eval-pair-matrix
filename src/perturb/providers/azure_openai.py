"""Azure OpenAI Responses API (GPT 5.x). Default perturbation + validator provider.

Hardening invariants:
  - Inspect `status` on every response; "completed" or raise.
  - If "incomplete" with reason "max_output_tokens", retry once with doubled budget
    (capped). Still incomplete → TruncatedResponse.
  - Strict JSON: a non-parseable body raises TruncatedResponse — we never return
    half-baked records downstream.
"""
from __future__ import annotations

import json

import httpx

from ..config import env
from . import register
from .base import ProviderResponse


class ProviderError(RuntimeError):
    """Base class for provider-side failures the steps should catch."""


class ProviderIncomplete(ProviderError):
    """Model returned status='incomplete', 'failed', or unparseable JSON.

    `reason` is one of: max_output_tokens, content_filter, unparseable, failed, unknown.
    Steps inspect this to emit precise pipeline_state labels.
    """

    def __init__(self, message: str, *, reason: str = "unknown") -> None:
        super().__init__(message)
        self.reason = reason


# Back-compat alias so any external code that imported TruncatedResponse keeps working.
TruncatedResponse = ProviderIncomplete


MAX_BUDGET_CEILING = 32_768


class AzureOpenAIProvider:
    name = "azure-gpt"

    def __init__(self, endpoint: str, api_key: str, api_version: str, model: str) -> None:
        self.endpoint = endpoint
        self.api_key = api_key
        self.api_version = api_version
        self.model = model
        self.url = _build_url(endpoint, api_version)
        self._client = httpx.Client(timeout=180.0)

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

        input_msgs: list[dict] = []
        if sys_full:
            input_msgs.append({"role": "system", "content": sys_full})
        input_msgs.append({"role": "user", "content": user})

        budget = max(max_tokens, 1024)
        last_error: str | None = None
        last_text: str = ""
        last_data: dict | None = None

        for attempt in range(2):  # initial + one retry on truncation
            body: dict = {
                "model": self.model,
                "input": input_msgs,
                "max_output_tokens": budget,
                "text": {"format": {"type": "json_object"}},
            }
            if temperature is not None and temperature != 0.0:
                body["temperature"] = temperature

            data = self._post(body)
            last_data = data
            status = data.get("status")
            inc = data.get("incomplete_details") or {}
            text = _extract_text(data)
            last_text = text

            if status == "completed":
                parsed = _strict_json(text)
                if parsed is None:
                    raise ProviderIncomplete(
                        f"completed but JSON unparseable; "
                        f"text_len={len(text)} preview={text[:200]!r}",
                        reason="unparseable",
                    )
                usage = data.get("usage") or {}
                return ProviderResponse(
                    text=text,
                    parsed_json=parsed,
                    input_tokens=usage.get("input_tokens"),
                    output_tokens=usage.get("output_tokens"),
                    raw=data,
                )

            if status == "incomplete" and inc.get("reason") == "max_output_tokens":
                last_error = (
                    f"truncated at max_output_tokens={budget} "
                    f"(attempt {attempt + 1}/2)"
                )
                budget = min(budget * 2, MAX_BUDGET_CEILING)
                if budget == MAX_BUDGET_CEILING and attempt == 1:
                    break
                continue

            # Any other terminal status (content_filter / failed / etc) — don't retry.
            reason = inc.get("reason") if status == "incomplete" else (status or "unknown")
            err = data.get("error")
            raise ProviderIncomplete(
                f"status={status!r} incomplete_details={inc!r} error={err!r}",
                reason=str(reason),
            )

        usage = (last_data or {}).get("usage") or {}
        raise ProviderIncomplete(
            f"still incomplete after retry. last_error={last_error} "
            f"usage={usage} text_preview={last_text[:200]!r}",
            reason="max_output_tokens",
        )

    def _post(self, body: dict) -> dict:
        headers = {"api-key": self.api_key, "Content-Type": "application/json"}
        resp = self._client.post(self.url, json=body, headers=headers)
        resp.raise_for_status()
        return resp.json()


def _build_url(endpoint: str, api_version: str) -> str:
    """Accept either a bare endpoint or a fully-qualified responses URL."""
    e = endpoint.rstrip("/")
    if "/openai/responses" in e:
        if "api-version=" in e:
            return e
        sep = "&" if "?" in e else "?"
        return f"{e}{sep}api-version={api_version}"
    return f"{e}/openai/responses?api-version={api_version}"


def _extract_text(data: dict) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"]
    parts: list[str] = []
    for item in data.get("output", []) or []:
        if item.get("type") != "message":
            continue
        for c in item.get("content", []) or []:
            if c.get("type") in ("output_text", "text"):
                parts.append(c.get("text", ""))
    return "".join(parts)


def _strict_json(text: str):
    """Strict parse. No code-fence salvage — json_object mode shouldn't emit them,
    and accepting half-parsed output downstream is exactly what we want to avoid."""
    text = (text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _factory() -> AzureOpenAIProvider:
    endpoint = env("AZURE_GPT_ENDPOINT")
    key = env("AZURE_GPT_API_KEY")
    version = env("AZURE_GPT_API_VERSION", "2025-03-01-preview")
    model = env("AZURE_GPT_MODEL", "gpt-5")
    if not endpoint or not key:
        raise RuntimeError(
            "Azure OpenAI provider not configured: set AZURE_GPT_ENDPOINT and "
            "AZURE_GPT_API_KEY in .env."
        )
    return AzureOpenAIProvider(endpoint=endpoint, api_key=key, api_version=version, model=model)


register("azure-gpt", _factory)
