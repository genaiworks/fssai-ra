"""OpenAI-compatible chat backend for self-hosted servers.

Covers vLLM, llama.cpp's server, LM Studio, Text Generation Inference, and any
gateway that speaks ``/v1/chat/completions``. It exists so that "pluggable
model" means something concrete: point ``FSSAI_MODEL_BASE_URL`` at your own
inference service and nothing else in the architecture changes.

Sovereignty note: this backend will happily talk to a hosted commercial API. If
you configure one, the data-residency claim in ``docs/ASSURANCE.md`` no longer
holds for prompts or retrieved evidence, and the control plane records a
configuration warning saying so.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from ..accountable_action import ToolCall
from .base import CapabilityCatalogue, ModelUnavailable, build_prompt, parse_proposals

LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1", "host.docker.internal")


class OpenAICompatibleModel:
    """Chat-completions client with no vendor SDK dependency."""

    name = "openai-compatible"

    def __init__(
        self,
        agent_id: str = "agent-1",
        *,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        timeout: float = 60.0,
        temperature: float = 0.0,
        catalogue: CapabilityCatalogue | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.base_url = (base_url or os.getenv("FSSAI_MODEL_BASE_URL", "http://localhost:8000/v1")).rstrip("/")
        self.model = model or os.getenv("FSSAI_MODEL_NAME", "local-model")
        self.api_key = api_key or os.getenv("FSSAI_MODEL_API_KEY", "")
        self.timeout = timeout
        self.temperature = temperature
        self.catalogue = catalogue or CapabilityCatalogue.default()

    @property
    def is_local(self) -> bool:
        return any(host in self.base_url for host in LOCAL_HOSTS)

    def health(self) -> dict:
        status = {"backend": self.name, "base_url": self.base_url,
                  "model": self.model, "local": self.is_local}
        try:
            request = urllib.request.Request(f"{self.base_url}/models", headers=self._headers())
            with urllib.request.urlopen(request, timeout=5) as response:
                response.read()
            status["reachable"] = True
        except (urllib.error.URLError, OSError) as exc:
            status.update(reachable=False, detail=str(exc))
        if not self.is_local:
            status["sovereignty_warning"] = (
                "model endpoint is not local: prompts and retrieved evidence leave the boundary"
            )
        return status

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def propose(self, task: str, evidence: list | None = None) -> list[ToolCall]:
        prompt = build_prompt(task, evidence or [], self.catalogue)
        body = json.dumps({
            "model": self.model,
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": "You propose tool calls as JSON. You never execute them."},
                {"role": "user", "content": prompt},
            ],
        }).encode()
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions", data=body, headers=self._headers()
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read())
        except (urllib.error.URLError, OSError) as exc:
            raise ModelUnavailable(f"model endpoint unreachable at {self.base_url}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise ModelUnavailable(f"model endpoint returned malformed JSON: {exc}") from exc
        try:
            raw = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelUnavailable(f"unexpected chat-completions shape: {exc}") from exc
        return parse_proposals(
            raw, agent_id=self.agent_id, catalogue=self.catalogue, model_name=f"{self.name}:{self.model}"
        )


__all__ = ["OpenAICompatibleModel"]
