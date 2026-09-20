"""Credential-scoped SDK client for a model-side transport.

The transport takes (agent token, JSON) and returns a dictionary. Production
adapters must cross a process boundary; an in-process callable is a test fixture.
Administrative authority and database credentials never enter this client.
"""
from __future__ import annotations

from ..joined_workflow import canonical
from .contracts import AuthorityDenied


class SDKClient:
    def __init__(self, transport, token):
        self._transport, self._token = transport, token
        self.capability = None

    def request(self, primitive, **fields):
        request = {"op": primitive, **fields}
        if primitive != "request_capability":
            request["capability"] = self.capability
        result = self._transport(self._token, canonical(request))
        if not result.get("ok"):
            raise AuthorityDenied("DENIED")
        return result

    def request_capability(self, *, scope=None, ttl=None):
        fields = {}
        if scope is not None:
            fields["scope"] = scope.to_dict()
        if ttl is not None:
            fields["ttl"] = ttl
        result = self.request("request_capability", **fields)
        self.capability = result["capability"]
        return result

    def request_context(self, resource):
        return self.request("request_context", resource=resource)

    def invoke_tool(self, tool, artifact, *, max_chars=256):
        return self.request("invoke_tool", tool=tool, artifact=artifact, max_chars=max_chars)

    def persist_memory(self, artifact, namespace, *, retention):
        return self.request("persist_memory", artifact=artifact, namespace=namespace, retention=retention)

    def read_memory(self, memory):
        return self.request("read_memory", memory=memory)

    def derive_artifact(self, text):
        return self.request("derive_artifact", text=text)

    def propose_effect(self, context, operation, value, recipient):
        return self.request("propose_effect", context=context, operation=operation, value=value, recipient=recipient)

    def execute_effect(self, proposal, approval):
        return self.request("execute_effect", proposal=proposal, approval=approval)

    def release_artifact(self, artifact, destination, escrow):
        return self.request("release_artifact", artifact=artifact, destination=destination, escrow=escrow)
