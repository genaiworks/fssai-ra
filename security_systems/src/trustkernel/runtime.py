"""Domain-independent dispatch for a trusted application boundary.

The transport authenticates the caller and supplies its identity separately.
Model-generated requests cannot select identities, contexts, roles or policies.
This module does not authenticate HTTP requests or isolate untrusted Python.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from .guard import AgentContext, Guard, _json_payload
from .kernel.exact_action import ActionProposal, Approval, ExecutionDenied


class GuardedDispatcher:
    """Reuse one guard with server-owned caller mappings and a strict request schema.

    Configure tools and contexts before serving requests. All tool calls are
    synchronous. Only ``tool`` and ``arguments`` belong in the request envelope.
    """

    def __init__(self, guard: Guard, callers: Mapping[str, AgentContext]) -> None:
        self._guard = guard
        bindings = dict(callers)
        for identity, context in bindings.items():
            if type(identity) is not str or not identity.strip():
                raise ValueError("caller identities must be nonempty strings")
            guard.label(context)  # validate issued context without trusting supplied fields
        self._callers = MappingProxyType(bindings)

    def _context(self, caller: str) -> AgentContext:
        if type(caller) is not str or caller not in self._callers:
            raise ExecutionDenied("CALLER_UNKNOWN", "caller has no server-side context binding")
        return self._callers[caller]

    @staticmethod
    def _request(request: dict) -> tuple[str, dict]:
        if type(request) is not dict or set(request) != {"tool", "arguments"}:
            raise ExecutionDenied("REQUEST_INVALID", "request must contain exactly tool and arguments")
        if type(request["tool"]) is not str or not request["tool"].strip() or type(request["arguments"]) is not dict:
            raise ExecutionDenied("REQUEST_INVALID", "tool must be a name and arguments an object")
        payload = json.loads(_json_payload(request))
        return payload["tool"], payload["arguments"]

    def propose(self, caller: str, request: dict) -> ActionProposal:
        """Prepare exact effective arguments for review; execution rechecks authority."""
        context = self._context(caller)
        tool, arguments = self._request(request)
        return self._guard.propose_call(context, tool, arguments)

    def dispatch(self, caller: str, request: dict, *, approval: Approval | None = None) -> Any:
        context = self._context(caller)
        tool, arguments = self._request(request)
        return self._guard.invoke(context, tool, arguments, approval=approval)

    def handoff(self, producer: str, consumer: str, content: Any) -> Any:
        """Trusted orchestration transfers JSON content and joins its source label."""
        sender, receiver = self._context(producer), self._context(consumer)
        snapshot = json.loads(_json_payload(content))
        self._guard.consume(receiver, sender)
        return snapshot

    def release(self, caller: str, content: str, *, recipient: str, purpose: str) -> str:
        """Check disclosure before the application writes the result to its sink."""
        if type(content) is not str:
            raise TypeError("release content must be text")
        return self._guard.release(self._context(caller), content, recipient=recipient, purpose=purpose)
