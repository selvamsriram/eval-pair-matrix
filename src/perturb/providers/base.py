"""LLMProvider protocol and shared response shape."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class ProviderResponse:
    text: str
    parsed_json: Any | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    raw: dict | None = None


class LLMProvider(Protocol):
    name: str
    model: str

    def complete_json(
        self,
        *,
        system: str | None,
        user: str,
        schema_hint: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> ProviderResponse:
        """Single-turn completion. Implementations should request JSON output and parse it.

        `schema_hint` is a freeform description of the desired JSON shape, appended
        to the system prompt. Providers that support structured outputs natively may
        ignore it and use their own schema mechanism.
        """
        ...
