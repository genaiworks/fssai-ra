"""Drop-in authority for your own agent stack.

Every agent framework has one place where a model's tool call becomes a function call:
the tool dispatcher. :class:`Guard` sits there. It adds no model, no network, and no
framework dependency, and it enforces the three rules the evaluation suites measure:

1. **Whole-chain delegation.** An agent acts under an :class:`AgentContext`: a root
   grant plus the signed chain of hops that led to it. Every call re-derives authority
   from the root (attenuation, provenance, rooting, expiry, acyclicity, depth,
   non-delegable consequence, holder binding) instead of trusting the caller's claimed
   scope or checking only the last hop.
2. **Exact-action approval.** A consequential tool runs only with an Ed25519 human
   approval bound to *this* principal, tool, resource, and argument digest, from the
   declared role, unexpired, and cached after successful execution in this instance. A replayed call returns the
   first result; it does not repeat the side effect.
3. **Labels survive summarization.** Each context carries the join of every data class
   it has read, and a worker's label flows into whoever consumes its output. Release to
   a recipient is refused unless the recipient's clearance covers the label. There is
   no API to lower a label, so a model cannot declassify its own output.

The checks are the kernel's own: :class:`~trustkernel.kernel.delegation.DelegationAuthority`,
:class:`~trustkernel.kernel.exact_action.AccountableExecutor`, and the pack's
:class:`~trustkernel.kernel.disclosure.RecipientRule` policy. Denials raise
:class:`~trustkernel.kernel.exact_action.ExecutionDenied` or
:class:`~trustkernel.kernel.disclosure.DisclosureDenied` with a stable ``code``.

    guard = Guard.from_pack("worlds/devtools/pack.yaml")
    lead = guard.root("coordinator", tools={"read_repo", "trigger_deploy"}, resources={"acme-api"})
    worker = guard.spawn(lead, "reader-agent", tools={"read_repo"})

    @guard.tool(resource="service")
    def read_repo(service: str) -> str: ...

    @guard.tool(resource="service", action_class=ActionClass.HIGH_IMPACT, approver_role="release_manager")
    def trigger_deploy(service: str, build: str) -> str: ...

    read_repo(worker, service="acme-api")                     # allowed
    trigger_deploy(worker, service="acme-api", build="v43")   # ExecutionDenied: not delegated
"""
from __future__ import annotations

import copy
import functools
import inspect
import hashlib
import json
import secrets
import threading
import time
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .kernel.accountable_action import ActionClass
from .kernel.delegation import (
    ANY,
    DELEGATION_KEY_ID,
    AuthorityScope,
    ChainVerdict,
    Delegation,
    DelegationAuthority,
    DelegationPolicy,
    RootGrant,
)
from .kernel.disclosure import DisclosureDenied, DisclosurePolicy
from .kernel.evidence import EvidenceLedger
from .kernel.exact_action import (
    AccountableExecutor,
    ActionProposal,
    Approval,
    ApprovalUseStore,
    AsymmetricApprovalAuthority,
    CaseRegister,
    ExecutionDenied,
)
from .kernel.pack_floor import load_governed_pack

_EVIDENCE_TOKEN = "guard-evidence-writer"


@dataclass(frozen=True)
class AgentContext:
    """Who is acting, the authority it descends from, and what it has read."""

    principal: str
    root: RootGrant
    chain: tuple[Delegation, ...] = ()
    session: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    @property
    def depth(self) -> int:
        return len(self.chain)


@dataclass(frozen=True)
class Decision:
    """One guard decision, kept for audit and for demos."""

    at: float
    principal: str
    action: str
    target: str
    allowed: bool
    code: str

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def _json_payload(value: Any) -> str:
    """Reject coercions that could bind different Python values to one approval."""
    def validate(item: Any) -> None:
        if type(item) is dict:
            for key, child in item.items():
                if type(key) is not str:
                    raise TypeError("tool argument object keys must be strings")
                validate(child)
        elif type(item) is list:
            for child in item:
                validate(child)
        elif item is not None and type(item) not in (str, int, float, bool):
            raise TypeError("tool arguments must contain only JSON values")
    validate(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_json_payload(value).encode()).hexdigest()


class Guard:
    """Reference guard for a trusted dispatcher, with in-memory replay state.

    Authenticate callers outside this class. Issuance APIs and tool callbacks
    belong to trusted control-plane code, never to arbitrary agent Python.
    This library does not provide crash-safe exactly-once external effects.
    """

    def __init__(self, *, owner: str = "tool_owner", audience: str = "guarded-tools", max_depth: int = 3,
                 policy: DisclosurePolicy | None = None, clock: Callable[[], float] = time.time,
                 approval_seed: bytes | None = None) -> None:
        self.owner = owner
        self.audience = audience
        self.policy = policy
        self.clock = clock
        self.delegation = DelegationAuthority(policy=DelegationPolicy(max_depth=max_depth),
                                              keys={DELEGATION_KEY_ID: secrets.token_hex(32)})
        self.approvals = AsymmetricApprovalAuthority(audience, seed=approval_seed)
        self.ledger = EvidenceLedger(_EVIDENCE_TOKEN)
        self.decisions: list[Decision] = []
        self._uses = ApprovalUseStore()
        self._proposals: dict[str, ActionProposal] = {}
        self._done: dict[str, Any] = {}
        self._labels: dict[str, frozenset[str]] = {}
        self._contexts: dict[str, AgentContext] = {}
        self._tools: dict[str, tuple[inspect.Signature, Any, Callable]] = {}
        self._lock = threading.RLock()

    @classmethod
    def from_pack(cls, pack_path: str | Path, **kwargs) -> Guard:
        """Take the delegation depth bound and the release policy from a floor-checked pack."""
        pack = load_governed_pack(pack_path, repo_root=kwargs.pop("repo_root", None))
        kwargs.setdefault("owner", pack.profile.owner)
        kwargs.setdefault("max_depth", int(pack.delegation.get("max_depth", 3)))
        return cls(policy=pack.profile.disclosure, **kwargs)

    # -- bookkeeping --------------------------------------------------------------------
    def _record(self, ctx: AgentContext, action: str, target: str, allowed: bool, code: str) -> None:
        decision = Decision(self.clock(), ctx.principal, action, target, allowed, code)
        with self._lock:
            self.decisions.append(decision)
            self.ledger.append("guard_decision", decision.to_dict(), token=_EVIDENCE_TOKEN)

    def _register(self, ctx: AgentContext) -> AgentContext:
        with self._lock:
            self._contexts[ctx.session] = ctx
        return ctx

    def _check_context(self, ctx: AgentContext) -> None:
        # Contexts are server-issued handles, not caller-authenticated identities.
        with self._lock:
            if self._contexts.get(ctx.session) != ctx:
                self._record(ctx, "context", ctx.session, False, "CONTEXT_NOT_ISSUED")
                raise ExecutionDenied("CONTEXT_NOT_ISSUED", "context was not issued by this guard or was modified")

    # -- authority --------------------------------------------------------------------
    @staticmethod
    def scope(tools: Iterable[str], resources: Iterable[str] = (ANY,),
              max_action_class: ActionClass = ActionClass.REVERSIBLE) -> AuthorityScope:
        tools = frozenset(tools)
        return AuthorityScope(tools=tools, operations=tools, resources=frozenset(resources),
                              max_action_class=max_action_class)

    def root(self, principal: str, *, tools: Iterable[str], resources: Iterable[str] = (ANY,),
             max_action_class: ActionClass = ActionClass.HIGH_IMPACT, ttl_seconds: float = 3600.0) -> AgentContext:
        """The institutional grant a top-level agent starts from. Issued by the tool owner."""
        grant = RootGrant(principal=principal, scope=self.scope(tools, resources, max_action_class),
                          owner=self.owner, expires_at=self.clock() + ttl_seconds)
        return self._register(AgentContext(principal, grant))

    def spawn(self, parent: AgentContext, child: str, *, tools: Iterable[str],
              resources: Iterable[str] | None = None, max_action_class: ActionClass = ActionClass.REVERSIBLE,
              ttl_seconds: float = 900.0, human_approved: bool = False, purpose: str = "") -> AgentContext:
        """Hand ``child`` a signed hop after validating the parent context handle.

        Chain authority is checked from the root at every use.

        Two defaults keep honest trees valid: the hop's expiry is clamped to the parent's
        (a delegate may never outlive its delegator, D4), and ``resources`` defaults to the
        parent's. Tools and action class are never widened by default. A hop that asks for
        more than its parent holds is issued as asked and refused at use, where the refusal
        is recorded.
        """
        self._check_context(parent)
        now = self.clock()
        held = parent.chain[-1] if parent.chain else parent.root
        parent_expiry = held.expires_at
        # Unless narrowed, a child works on exactly the resources its parent holds, never "any".
        scope = self.scope(tools, resources if resources is not None else held.scope.resources, max_action_class)
        hop = self.delegation.issue(delegator=parent.principal, delegate=child, scope=scope, issued_at=now,
                                    expires_at=min(now + ttl_seconds, parent_expiry),
                                    human_approved=human_approved, purpose=purpose)
        return self._register(AgentContext(child, parent.root, (*parent.chain, hop)))

    def authorize(self, ctx: AgentContext, tool: str, *, resource: str = ANY,
                  action_class: ActionClass = ActionClass.REVERSIBLE,
                  on_behalf_of: AgentContext | None = None) -> ChainVerdict:
        """Recompute what the chain confers and check one concrete call. Raises on refusal."""
        try:
            verdict = self.delegation.admit_strict(
                ctx.chain, ctx.root, now=self.clock(), requester=ctx.principal, tool=tool, operation=tool,
                resource=resource, action_class=action_class,
                on_behalf_of=on_behalf_of.principal if on_behalf_of else None,
                beneficiary_chain=on_behalf_of.chain if on_behalf_of else None)
        except ExecutionDenied as exc:
            self._record(ctx, tool, resource, False, exc.code)
            raise
        self._check_context(ctx)
        if on_behalf_of is not None:
            self._check_context(on_behalf_of)
        self._record(ctx, tool, resource, True, verdict.code)
        return verdict

    # -- exact-action approval ------------------------------------------------------------
    def _proposal(self, ctx: AgentContext, tool: str, resource: str, arguments: dict, request_id: str) -> ActionProposal:
        return ActionProposal(request_id=request_id, requester=ctx.principal, operation=tool, case_id=resource,
                              expected_version=1, from_status="proposed", to_status="args:" + _digest(arguments),
                              evidence_version=ctx.session)

    def propose(self, ctx: AgentContext, tool: str, *, resource: str = ANY, **arguments: Any) -> ActionProposal:
        """What a human is asked to approve: this principal, this tool, this resource, these arguments."""
        self._check_context(ctx)
        if tool in self._tools:
            target, arguments = self.prepare(tool, arguments)
            if resource != ANY and resource != target:
                raise ValueError("proposal resource differs from the tool's effective target")
            resource = target
        proposal = self._proposal(ctx, tool, resource, arguments, "req-" + uuid.uuid4().hex[:12])
        with self._lock:
            self._proposals[proposal.digest] = proposal
        return proposal

    def approve(self, proposal: ActionProposal, *, approver: str, role: str, ttl_seconds: int = 900) -> Approval:
        """A human's signed approval of one exact proposal. Stand-in for your approval service."""
        return self.approvals.approve(proposal, approver=approver, approver_role=role, now=self.clock(),
                                      ttl_seconds=ttl_seconds)

    def _execute_approved(self, ctx: AgentContext, tool: str, resource: str, arguments: dict, role: str,
                          approval: Approval | None, run: Callable[[], Any]) -> Any:
        if approval is None:
            self._record(ctx, tool, resource, False, "APPROVAL_REQUIRED")
            raise ExecutionDenied("APPROVAL_REQUIRED", f"{tool} is consequential and needs a signed human approval")
        with self._lock:
            approved = self._proposals.get(approval.proposal_digest)
        # The call the agent is actually making, under the request id the human approved.
        actual = self._proposal(ctx, tool, resource, arguments,
                                approved.request_id if approved else "req-unknown-" + uuid.uuid4().hex[:8])
        with self._lock:
            transition = (actual.from_status, actual.to_status)
            executor = AccountableExecutor(
                CaseRegister({resource: {"status": "proposed", "version": 1}}), self.ledger, _EVIDENCE_TOKEN,
                audience=self.audience, approval_keys=self.approvals.verification_keys,
                allowed_operations={tool}, transition_rules={tool: {transition}},
                required_approval_roles={(tool, *transition): {role}}, approval_use_store=self._uses)
            try:
                executor.validate_authorization(actual, approval, now=self.clock())
                if actual.request_id in self._done:
                    self._record(ctx, tool, resource, True, "REPLAYED_SAME_RESULT")
                    return copy.deepcopy(self._done[actual.request_id])
                executor.execute(actual, approval, now=self.clock())
            except ExecutionDenied as exc:
                self._record(ctx, tool, resource, False, exc.code)
                raise
            result = run()
            self._done[actual.request_id] = copy.deepcopy(result)
        self._record(ctx, tool, resource, True, "EXECUTED")
        return result

    def prepare(self, tool: str, arguments: dict) -> tuple[str, dict]:
        """Bind defaults and validate a registered tool before approval or execution.

        Resource names refer to function parameters. For a constant or composite
        resource, register an explicit pure callable returning its string ID.
        """
        with self._lock:
            definition = self._tools.get(tool)
        if definition is None:
            raise ExecutionDenied("TOOL_UNKNOWN", f"unregistered tool: {tool}")
        signature, resource, _ = definition
        if type(arguments) is not dict:
            raise TypeError("tool arguments must be an object")
        arguments = json.loads(_json_payload(arguments))
        bound = signature.bind(**arguments)
        bound.apply_defaults()
        arguments = json.loads(_json_payload(dict(bound.arguments)))
        target = resource(copy.deepcopy(arguments)) if callable(resource) else (
            ANY if resource == ANY else arguments[resource])
        if type(target) is not str or not target.strip():
            raise TypeError("tool resource must resolve to a nonempty string")
        return target, arguments

    def invoke(self, ctx: AgentContext, tool: str, arguments: dict, *, approval: Approval | None = None) -> Any:
        """Invoke a registered tool; caller identity must already be authenticated."""
        with self._lock:
            definition = self._tools.get(tool)
        if definition is None:
            raise ExecutionDenied("TOOL_UNKNOWN", f"unregistered tool: {tool}")
        return definition[2](ctx, approval=approval, **arguments)

    # -- the decorator ------------------------------------------------------------------
    def tool(self, name: str | None = None, *, resource: str | Callable[[dict], str] = ANY,
             action_class: ActionClass = ActionClass.REVERSIBLE, approver_role: str | None = None,
             reads: Iterable[str] = ()) -> Callable:
        """Wrap a tool so every call is authorized from the root, and approved if consequential.

        ``resource`` names the keyword argument holding the target (or a callable over the
        keyword arguments). ``reads`` lists the data classes the tool returns; the caller's
        label absorbs them. The wrapped function takes the :class:`AgentContext` first and
        an optional ``approval=`` keyword.
        """
        if action_class == ActionClass.HIGH_IMPACT and (not approver_role or not approver_role.strip()):
            raise ValueError("high-impact tools require a nonempty approver_role")
        if not isinstance(action_class, ActionClass):
            raise TypeError("action_class must be an ActionClass")
        reads = frozenset(reads)

        def decorate(fn: Callable) -> Callable:
            tool_name = name or fn.__name__
            if not isinstance(tool_name, str) or not tool_name.strip():
                raise ValueError("tool name must be nonempty")
            if inspect.iscoroutinefunction(fn) or inspect.isgeneratorfunction(fn) or inspect.isasyncgenfunction(fn):
                raise TypeError("this guard supports synchronous non-streaming tools only")
            signature = inspect.signature(fn)
            unsupported = (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.VAR_POSITIONAL,
                           inspect.Parameter.VAR_KEYWORD)
            if any(p.kind in unsupported for p in signature.parameters.values()):
                raise TypeError("tools require explicit keyword-compatible parameters; wrap dynamic tools")
            if "approval" in signature.parameters:
                raise ValueError("approval is reserved for the guard")
            if not callable(resource) and resource != ANY and resource not in signature.parameters:
                raise ValueError("resource must name a tool parameter or be an explicit resolver")

            @functools.wraps(fn)
            def wrapper(ctx: AgentContext, /, *args: Any, approval: Approval | None = None, **kwargs: Any) -> Any:
                if args:
                    raise TypeError(f"{tool_name}: pass tool arguments by keyword so they can be bound to approvals")
                # Snapshot arguments before hashing and execution; callers retain no mutable alias.
                target, kwargs = self.prepare(tool_name, kwargs)
                self.authorize(ctx, tool_name, resource=str(target), action_class=action_class)
                # Taint before invoking: callbacks and exception paths may expose data too.
                if reads:
                    self.observe(ctx, reads)
                if approver_role is not None:
                    result = self._execute_approved(ctx, tool_name, str(target), kwargs, approver_role, approval,
                                                    lambda: fn(**kwargs))
                else:
                    result = fn(**kwargs)
                return result

            wrapper.guarded_tool = tool_name  # type: ignore[attr-defined]
            with self._lock:
                if tool_name in self._tools:
                    raise ValueError(f"tool already registered: {tool_name}")
                self._tools[tool_name] = (signature, resource, wrapper)
            return wrapper
        return decorate

    # -- labels and release -------------------------------------------------------------
    def label(self, ctx: AgentContext) -> frozenset[str]:
        self._check_context(ctx)
        with self._lock:
            return self._labels.get(ctx.session, frozenset())

    def observe(self, ctx: AgentContext, classes: Iterable[str]) -> frozenset[str]:
        """Record that ``ctx`` has read data of these classes. Labels only ever grow."""
        self._check_context(ctx)
        classes = frozenset(classes)
        if self.policy is not None:
            unknown = classes - set(self.policy.field_classes.values()) - set(self.policy.class_zones)
            if unknown:
                raise ValueError(f"unknown data classes: {sorted(unknown)}")
        with self._lock:
            self._labels[ctx.session] = self._labels.get(ctx.session, frozenset()) | classes
            return self._labels[ctx.session]

    def consume(self, consumer: AgentContext, producer: AgentContext) -> frozenset[str]:
        """``consumer`` took ``producer``'s output: the producer's label flows with it."""
        return self.observe(consumer, self.label(producer))

    def release(self, ctx: AgentContext, content: str, *, recipient: str, purpose: str) -> str:
        """Send ``content`` to ``recipient`` only if its clearance covers everything ``ctx`` read."""
        if self.policy is None:
            raise RuntimeError("release needs a disclosure policy; build the guard with Guard.from_pack")
        rule = self.policy.recipients.get(recipient)
        label = self.label(ctx)
        if rule is None:
            code, detail = "RECIPIENT_UNKNOWN", f"{recipient!r} is not a declared recipient"
        elif purpose not in rule.purposes:
            code, detail = "RECIPIENT_PURPOSE_NOT_ALLOWED", f"{recipient} does not receive data for {purpose}"
        elif not label <= rule.classes:
            code, detail = "RECIPIENT_CLASS_NOT_CLEARED", f"{recipient} is not cleared for {sorted(label - rule.classes)}"
        else:
            self._record(ctx, "release", recipient, True, "RELEASED")
            return content
        self._record(ctx, "release", recipient, False, code)
        raise DisclosureDenied(code, detail)


__all__ = ["ActionClass", "AgentContext", "Decision", "Guard"]
