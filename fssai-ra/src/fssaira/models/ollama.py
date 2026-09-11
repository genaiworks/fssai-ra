"""Ollama backend -- the default local model for a sovereign deployment.

Ollama runs the weights on hardware the institution controls, which is the
minimum condition for the sovereignty claim: no prompt, no student record, and
no retrieved document leaves the boundary to be scored by a third party.

The backend is deliberately unexciting. It sends one prompt, takes one reply,
parses it through :func:`fssaira.models.base.parse_proposals`, and lets the
policy enforcement point decide everything that matters. If Ollama is
unreachable it raises :class:`ModelUnavailable`; the runtime factory then either
falls back to the deterministic backend (recording a configuration warning) or
fails closed, according to ``FSSAI_MODEL_FALLBACK``.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from ..accountable_action import ToolCall
from .base import CapabilityCatalogue, ModelUnavailable, build_prompt, parse_proposals

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2"


class OllamaModel:
    """Local inference over the Ollama HTTP API."""

    name = "ollama"

    def __init__(
        self,
        agent_id: str = "agent-1",
        *,
        model: str | None = None,
        host: str | None = None,
        timeout: float = 60.0,
        temperature: float = 0.0,
        catalogue: CapabilityCatalogue | None = None,
        num_ctx: int = 8192,
    ) -> None:
        self.agent_id = agent_id
        self.model = model or os.getenv("FSSAI_OLLAMA_MODEL", DEFAULT_MODEL)
        self.host = (host or os.getenv("FSSAI_OLLAMA_HOST", DEFAULT_HOST)).rstrip("/")
        self.timeout = timeout
        self.temperature = temperature
        self.num_ctx = num_ctx
        self.catalogue = catalogue or CapabilityCatalogue.default()

    # -- health ------------------------------------------------------------
    def health(self) -> dict:
        try:
            with urllib.request.urlopen(f"{self.host}/api/tags", timeout=5) as response:
                tags = json.loads(response.read())
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            return {"backend": self.name, "reachable": False, "host": self.host,
                    "model": self.model, "detail": str(exc)}
        installed = [item.get("name", "") for item in tags.get("models", [])]
        return {
            "backend": self.name,
            "reachable": True,
            "host": self.host,
            "model": self.model,
            "model_installed": any(name.split(":")[0] == self.model.split(":")[0] for name in installed),
            "installed_models": installed,
        }

    # -- inference ---------------------------------------------------------
    def propose(self, task: str, evidence: list | None = None) -> list[ToolCall]:
        prompt = build_prompt(task, evidence or [], self.catalogue)
        raw = self.generate(prompt)
        return parse_proposals(
            raw, agent_id=self.agent_id, catalogue=self.catalogue, model_name=f"{self.name}:{self.model}"
        )

    def generate(self, prompt: str) -> str:
        body = json.dumps({
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": self.temperature, "num_ctx": self.num_ctx, "seed": 7},
        }).encode()
        request = urllib.request.Request(
            f"{self.host}/api/generate", data=body, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read())
        except (urllib.error.URLError, OSError) as exc:
            raise ModelUnavailable(f"ollama unreachable at {self.host}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise ModelUnavailable(f"ollama returned malformed JSON: {exc}") from exc
        return payload.get("response", "")


__all__ = ["OllamaModel", "DEFAULT_HOST", "DEFAULT_MODEL"]
