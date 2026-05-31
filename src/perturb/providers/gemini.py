"""Gemini 3.5 Flash via google-genai SDK.

Three auth modes detected from env (first match wins):
  1. Vertex Express (vertexai=True + api_key) — DEFAULT.
     Trigger: GOOGLE_CLOUD_API_KEY (preferred name) or GEMINI_API_KEY.
  2. Vertex Full (vertexai=True + project + ADC).
     Trigger: GOOGLE_CLOUD_PROJECT set and no api key. Requires
     `gcloud auth application-default login` or GOOGLE_APPLICATION_CREDENTIALS.
  3. Developer API (genai.Client(api_key=...)).
     Used only if explicitly forced via GEMINI_USE_DEVELOPER_API=1.

Config: response_mime_type='application/json', thinking_level=medium,
safety_settings=OFF for all four categories (we perturb sensitive topics).
"""
from __future__ import annotations

import json

from ..config import env
from . import register
from .azure_openai import ProviderIncomplete  # shared exception class
from .base import ProviderResponse


THINKING_LEVEL = "HIGH"  # OFF | LOW | MEDIUM | HIGH

# Reasoning models burn most of max_output_tokens on internal thinking. At HIGH
# we saw MAX_TOKENS hits at 12K caller budget; 32K floor gives safe headroom.
GEMINI_TOKEN_FLOOR = 32_768

# Safety thresholds — perturbation candidates frequently touch politics, health,
# violence; the SDK default ('BLOCK_MEDIUM_AND_ABOVE') drops too many records.
_SAFETY_CATEGORIES = (
    "HARM_CATEGORY_HATE_SPEECH",
    "HARM_CATEGORY_DANGEROUS_CONTENT",
    "HARM_CATEGORY_SEXUALLY_EXPLICIT",
    "HARM_CATEGORY_HARASSMENT",
)


class GeminiProvider:
    name = "gemini"

    def __init__(
        self,
        *,
        api_key: str | None,
        project: str | None,
        location: str,
        model: str,
        force_developer_api: bool = False,
    ) -> None:
        from google import genai  # type: ignore

        self.model = model
        if force_developer_api and api_key:
            self._client = genai.Client(api_key=api_key)
            self._auth_mode = "developer_api"
        elif api_key and not project:
            # Vertex Express: API key, no project needed — matches user's working snippet
            self._client = genai.Client(vertexai=True, api_key=api_key)
            self._auth_mode = "vertex_express"
        elif project:
            self._client = genai.Client(vertexai=True, project=project, location=location)
            self._auth_mode = f"vertex(project={project}, loc={location})"
        else:
            raise RuntimeError(
                "Gemini provider needs GOOGLE_CLOUD_API_KEY (Vertex Express, "
                "preferred), or GOOGLE_CLOUD_PROJECT (Vertex with ADC), or "
                "GEMINI_API_KEY+GEMINI_USE_DEVELOPER_API=1."
            )

    def complete_json(
        self,
        *,
        system: str | None,
        user: str,
        schema_hint: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> ProviderResponse:
        from google.genai import types  # type: ignore

        sys_full = system or ""
        if schema_hint:
            sys_full = (sys_full + "\n\n" if sys_full else "") + (
                "Return a single JSON object. No prose, no code fences. "
                "Conform to this shape:\n" + schema_hint
            )

        config_kwargs: dict = {
            "temperature": temperature,
            "max_output_tokens": max(max_tokens, GEMINI_TOKEN_FLOOR),
            "response_mime_type": "application/json",
            "safety_settings": [
                types.SafetySetting(category=c, threshold="OFF") for c in _SAFETY_CATEGORIES
            ],
        }
        if sys_full:
            config_kwargs["system_instruction"] = sys_full
        # ThinkingConfig is only honored by reasoning-capable models; passing it
        # to a non-reasoning model is ignored (or 400s — we'd see http_400).
        try:
            config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_level=THINKING_LEVEL)
        except (TypeError, AttributeError):
            pass  # older SDK builds may not expose ThinkingConfig

        config = types.GenerateContentConfig(**config_kwargs)

        try:
            resp = self._client.models.generate_content(
                model=self.model,
                contents=user,
                config=config,
            )
        except Exception as exc:  # noqa: BLE001
            raise ProviderIncomplete(f"SDK error: {type(exc).__name__}: {exc}", reason="sdk_error")

        cand = (resp.candidates or [None])[0]
        finish_obj = getattr(cand, "finish_reason", None) if cand else None
        finish = getattr(finish_obj, "name", str(finish_obj)) if finish_obj else "UNKNOWN"
        text = _extract_text(resp)

        if finish == "STOP":
            parsed = _strict_json(text)
            if parsed is None:
                raise ProviderIncomplete(
                    f"finish=STOP but JSON unparseable; text_len={len(text)} "
                    f"preview={text[:200]!r}",
                    reason="unparseable",
                )
            usage = getattr(resp, "usage_metadata", None)
            return ProviderResponse(
                text=text,
                parsed_json=parsed,
                input_tokens=getattr(usage, "prompt_token_count", None) if usage else None,
                output_tokens=getattr(usage, "candidates_token_count", None) if usage else None,
                raw=None,
            )

        reason_map = {
            "MAX_TOKENS": "max_output_tokens",
            "SAFETY": "content_filter",
            "RECITATION": "recitation",
            "PROHIBITED_CONTENT": "content_filter",
            "BLOCKLIST": "content_filter",
            "SPII": "content_filter",
            "MALFORMED_FUNCTION_CALL": "malformed_function_call",
        }
        raise ProviderIncomplete(
            f"finish_reason={finish} text_len={len(text)} preview={text[:200]!r}",
            reason=reason_map.get(finish, finish.lower() if finish else "unknown"),
        )


def _extract_text(resp) -> str:
    t = getattr(resp, "text", None)
    if isinstance(t, str) and t:
        return t
    parts: list[str] = []
    for cand in resp.candidates or []:
        content = getattr(cand, "content", None)
        for p in getattr(content, "parts", []) or []:
            txt = getattr(p, "text", None)
            if isinstance(txt, str):
                parts.append(txt)
    return "".join(parts)


def _strict_json(text: str):
    text = (text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _factory() -> GeminiProvider:
    api_key = env("GOOGLE_CLOUD_API_KEY") or env("GEMINI_API_KEY")
    project = env("GOOGLE_CLOUD_PROJECT")
    location = env("GEMINI_VERTEX_LOCATION", "global")
    model = env("GEMINI_MODEL", "gemini-3.5-flash")
    force_dev = (env("GEMINI_USE_DEVELOPER_API") or "").lower() in ("1", "true", "yes")
    if not api_key and not project:
        raise RuntimeError(
            "Gemini provider not configured: set GOOGLE_CLOUD_API_KEY (Vertex Express) "
            "or GOOGLE_CLOUD_PROJECT (Vertex full) in .env."
        )
    return GeminiProvider(
        api_key=api_key,
        project=project,
        location=location,
        model=model,
        force_developer_api=force_dev,
    )


register("gemini", _factory)
