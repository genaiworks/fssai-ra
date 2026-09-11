"""Pluggable model backends. Local-first, with Ollama as the default.

    from fssaira.models import build_model
    model = build_model()                      # honours FSSAI_MODEL, default "ollama"
    model = build_model("deterministic")       # offline, reproducible
    model = build_model("mypkg.models:Mine")   # your own, via dotted path

A backend only has to provide ``name``, ``propose(task, evidence) -> [ToolCall]``
and (optionally) ``health() -> dict``. It is never trusted: the policy
enforcement point re-derives the action class from the capability catalogue and
re-checks every call against the agent's grant before anything executes.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from .. import plugins
from .adversarial import ClassDowngradingModel, CompromisedModel, NullModel
from .base import (
    Capability,
    CapabilityCatalogue,
    ModelUnavailable,
    build_prompt,
    parse_proposals,
    wrap_untrusted,
)
from .deterministic import DeterministicModel, RuleBasedLocalModel
from .ollama import DEFAULT_MODEL as DEFAULT_OLLAMA_MODEL
from .ollama import OllamaModel
from .openai_compat import OpenAICompatibleModel

#: The default backend. Local inference, institution-controlled hardware.
DEFAULT_BACKEND = "ollama"

#: Used when the default backend is unreachable and fallback is permitted.
FALLBACK_BACKEND = "deterministic"

_BUILTIN = {
    "ollama": OllamaModel,
    "deterministic": DeterministicModel,
    "rule-based": DeterministicModel,
    "openai-compatible": OpenAICompatibleModel,
    "vllm": OpenAICompatibleModel,
    "llama-cpp": OpenAICompatibleModel,
    "null": NullModel,
    "compromised": CompromisedModel,
    "class-downgrading": ClassDowngradingModel,
}

for _name, _cls in _BUILTIN.items():
    plugins.register(
        "model", _name, _cls, origin="built-in",
        summary=(_cls.__doc__ or "").strip().splitlines()[0] if _cls.__doc__ else "",
        replace=True,
    )


@dataclass(frozen=True)
class ModelSelection:
    """What was actually built, and why -- surfaced on ``/health``."""

    requested: str
    backend: object
    fell_back: bool = False
    detail: str = ""

    @property
    def name(self) -> str:
        return getattr(self.backend, "name", type(self.backend).__name__)

    def to_dict(self) -> dict:
        return {
            "requested": self.requested,
            "active": self.name,
            "fell_back": self.fell_back,
            "detail": self.detail,
        }


def build_model(name: str | None = None, /, **kwargs) -> object:
    """Build one backend by name, dotted path, or entry point."""
    chosen = name or os.getenv("FSSAI_MODEL", DEFAULT_BACKEND)
    return plugins.create("model", chosen, **kwargs)


def select_model(
    name: str | None = None,
    *,
    allow_fallback: bool | None = None,
    probe: bool = True,
    **kwargs,
) -> ModelSelection:
    """Build a backend, optionally probing it and falling back when unreachable.

    ``FSSAI_MODEL_FALLBACK=deny`` makes an unreachable model a hard failure,
    which is the correct setting for a deployment that must never silently
    downgrade to a rule-based stand-in.
    """
    requested = name or os.getenv("FSSAI_MODEL", DEFAULT_BACKEND)
    if allow_fallback is None:
        allow_fallback = os.getenv("FSSAI_MODEL_FALLBACK", "allow").lower() != "deny"

    backend = plugins.create("model", requested, **kwargs)
    if not probe:
        return ModelSelection(requested, backend)

    health = getattr(backend, "health", None)
    if health is None:
        return ModelSelection(requested, backend, detail="backend reports no health check")
    status = health()
    if status.get("reachable", True):
        return ModelSelection(requested, backend, detail=status.get("sovereignty_warning", ""))

    detail = f"{requested} unreachable: {status.get('detail', 'no detail')}"
    if not allow_fallback:
        raise ModelUnavailable(detail + " (FSSAI_MODEL_FALLBACK=deny)")
    fallback = plugins.create("model", FALLBACK_BACKEND, **{
        k: v for k, v in kwargs.items() if k in ("agent_id", "catalogue")
    })
    return ModelSelection(requested, fallback, fell_back=True, detail=detail)


def available_models() -> list[dict]:
    return [
        {"name": info.name, "origin": info.origin, "summary": info.summary}
        for info in plugins.available("model")
    ]


__all__ = [
    "DEFAULT_BACKEND", "FALLBACK_BACKEND", "DEFAULT_OLLAMA_MODEL",
    "ModelSelection", "ModelUnavailable",
    "Capability", "CapabilityCatalogue",
    "DeterministicModel", "RuleBasedLocalModel", "OllamaModel", "OpenAICompatibleModel",
    "NullModel", "CompromisedModel", "ClassDowngradingModel",
    "build_model", "select_model", "available_models",
    "build_prompt", "parse_proposals", "wrap_untrusted",
]
