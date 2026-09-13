"""Compatibility import for the maintained local Ollama model adapter."""
from __future__ import annotations

from fssaira.models.ollama import OllamaModel as _OllamaModel


class OllamaModel(_OllamaModel):
    """Backward-compatible signature; all behaviour lives in ``fssaira.models``."""

    def __init__(
        self,
        agent_id: str = "bounded-agent",
        model: str = "llama3.2",
        host: str = "http://localhost:11434",
    ) -> None:
        super().__init__(agent_id=agent_id, model=model, host=host)
