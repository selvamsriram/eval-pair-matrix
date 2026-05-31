"""Provider registry. Adding a new model = one file + one register() call."""
from __future__ import annotations

from typing import Callable

from .base import LLMProvider, ProviderResponse  # re-exported

_REGISTRY: dict[str, Callable[[], LLMProvider]] = {}


def register(name: str, factory: Callable[[], LLMProvider]) -> None:
    if name in _REGISTRY:
        raise ValueError(f"Provider '{name}' already registered.")
    _REGISTRY[name] = factory


def get(name: str) -> LLMProvider:
    if name not in _REGISTRY:
        known = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise KeyError(f"Unknown provider '{name}'. Available: {known}")
    return _REGISTRY[name]()


def available() -> list[str]:
    return sorted(_REGISTRY)


# Eager registration of built-in providers. Failures here are deferred to get() time
# so `perturb providers` can still list models even when keys are missing.
from . import azure_openai as _azure  # noqa: E402,F401
from . import anthropic as _anthropic  # noqa: E402,F401
from . import kimi as _kimi  # noqa: E402,F401
from . import grok as _grok  # noqa: E402,F401
from . import gemini as _gemini  # noqa: E402,F401

__all__ = ["LLMProvider", "ProviderResponse", "register", "get", "available"]
