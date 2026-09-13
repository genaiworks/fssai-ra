"""Application-neutral orchestration for proposals, approvals, and execution.

The control plane is the use-case layer shared by the HTTP API, the CLI, the
React console, and direct Python integrations. It owns no policy of its own: the
profile decides which transitions exist, the executor decides whether an approval
authorizes one, and the evidence ledger records what happened. What the control
plane contributes is sequencing and durability of the request-scoped artifacts --
the proposal, the approval, and the receipt -- so that every interface performs
the same steps in the same order.

Two things are deliberately not here. There is no authentication (see
:mod:`fssaira.security`): the plane is told who is calling. And there is no
model (see :mod:`fssaira.models`): a proposal reaches the plane as structured
data, whether a person, a script, or an agent produced it. Both exclusions are
what let the same object serve a fully automated pipeline and a purely manual
one without changing a line.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import asdict
from typing import Protocol, TypeVar

from .event_transport import EventLog, KafkaLike
from .evidence import EvidenceLedger
from .exact_action import (
    ActionProposal,
    Approval,
    ApprovalAuthority,
    CaseRegister,
    ExecutionDenied,
)
from .metrics import Metrics
from .profiles import ApplicationProfile

T = TypeVar("T")


class ObjectStore(Protocol):
    def put(self, namespace: str, key: str, value: dict) -> None: ...
    def get(self, namespace: str, key: str) -> dict | None: ...


class MemoryObjectStore:
    def __init__(self) -> None:
        self._objects: dict[tuple[str, str], dict] = {}
        self._lock = threading.RLock()

    def put(self, namespace: str, key: str, value: dict) -> None:
        with self._lock:
            self._objects[(namespace, key)] = dict(value)

    def put_if_absent(self, namespace: str, key: str, value: dict) -> bool:
        with self._lock:
            identity = (namespace, key)
            if identity in self._objects:
                return False
            self._objects[identity] = dict(value)
            return True

    def get(self, namespace: str, key: str) -> dict | None:
        with self._lock:
            value = self._objects.get((namespace, key))
            return None if value is None else dict(value)

    def keys(self, namespace: str) -> list[str]:
        with self._lock:
            return [key for space, key in self._objects if space == namespace]


class ControlPlane:
    """Use-case service shared by the HTTP API and direct Python integrations."""

    def __init__(
        self,
        profile: ApplicationProfile,
        *,
        register=None,
        evidence=None,
        evidence_token: str = "teaching-evidence-writer",
        authority: ApprovalAuthority | None = None,
        oversight=None,
        objects: ObjectStore | None = None,
        events: KafkaLike | None = None,
        outcome_store=None,
        approval_use_store=None,
        approval_keys: dict[str, str] | None = None,
        executor=None,
        metrics: Metrics | None = None,
        model=None,
        durability: str = "best-effort",
    ) -> None:
        self.profile = profile
        self.register = CaseRegister({}) if register is None else register
        self.evidence = EvidenceLedger(evidence_token) if evidence is None else evidence
        #: Retained so other enforcement points held by this plane, such as the
        #: disclosure gate, append to the same evidence chain rather than a second one.
        self.evidence_token = evidence_token
        #: Optional :class:`fssaira.oversight.OversightMonitor`. Supplied here it
        #: is attached to the authority this plane builds, so the HTTP API and the
        #: console enforce review capacity on the same path the CLI does. An
        #: explicitly supplied ``authority`` carries its own; passing both is a
        #: configuration error rather than a merge.
        if authority is not None and oversight is not None:
            raise ValueError(
                "pass oversight to the ApprovalAuthority you supplied, not to the plane"
            )
        self.oversight = oversight
        self.authority = (
            ApprovalAuthority(oversight=oversight) if authority is None else authority
        )
        self.objects = MemoryObjectStore() if objects is None else objects
        self.events = EventLog() if events is None else events
        self.metrics = metrics or Metrics()
        self.model = model
        #: ``single-transaction`` when the register and evidence share a
        #: transaction, ``best-effort`` when an interrupted outcome is possible
        #: and must be reconciled. Reported on ``/health`` so a reader knows
        #: which durability claim a given result was produced under.
        self.durability = durability
        self.executor = executor if executor is not None else profile.make_executor(
            self.register,
            self.evidence,
            evidence_token,
            approval_keys=approval_keys,
            outcome_store=outcome_store,
            approval_use_store=approval_use_store,
        )

    # -- resources ---------------------------------------------------------
    def register_resource(self, resource_id: str, *, status: str, version: int = 1) -> dict:
        if status not in {rule.from_status for rule in self.profile.transitions}:
            raise ExecutionDenied("INITIAL_STATE_NOT_ALLOWED", "state is not a profiled starting state")
        if not self.register.seed(resource_id, status=status, version=version):
            raise ExecutionDenied("RESOURCE_ALREADY_EXISTS", "resource already exists")
        resource = {"resource_id": resource_id, "status": status, "version": version}
        self._emit("resource.registered", resource, resource_id)
        return resource

    def get_resource(self, resource_id: str) -> dict:
        return {"resource_id": resource_id, **self.register.get(resource_id)}

    # -- the three-step protocol ------------------------------------------
    def propose(
        self,
        *,
        requester: str,
        operation: str,
        resource_id: str,
        from_status: str,
        to_status: str,
        evidence_version: str,
        request_id: str | None = None,
    ) -> ActionProposal:
        current = self.register.get(resource_id)
        if current["status"] != from_status:
            raise ExecutionDenied(
                "CASE_STATE_CONFLICT",
                "the proposed starting state is not the current authoritative state",
            )
        proposal = ActionProposal(
            request_id=request_id or str(uuid.uuid4()),
            requester=requester,
            operation=operation,
            case_id=resource_id,
            expected_version=current["version"],
            from_status=from_status,
            to_status=to_status,
            evidence_version=evidence_version,
        )
        allowed = self.profile.transition_rules.get(operation, set())
        if (from_status, to_status) not in allowed:
            raise ExecutionDenied("TRANSITION_NOT_ALLOWED", "transition is not declared by profile")
        put_once = getattr(self.objects, "put_if_absent", None)
        inserted = (
            put_once("proposal", proposal.request_id, asdict(proposal))
            if put_once is not None
            else self.objects.get("proposal", proposal.request_id) is None
        )
        if put_once is None and inserted:
            self.objects.put("proposal", proposal.request_id, asdict(proposal))
        if not inserted:
            existing = self.objects.get("proposal", proposal.request_id)
            existing_proposal = ActionProposal(**existing)
            if existing_proposal.digest == proposal.digest:
                return existing_proposal
            raise ExecutionDenied(
                "REQUEST_ID_CONFLICT", "request ID already belongs to another proposal"
            )
        self._emit("action.proposed", asdict(proposal), resource_id)
        return proposal

    def begin_review(self, request_id: str, *, reviewer: str) -> dict:
        """Record when this server first presented a proposal to one reviewer.

        The operation is idempotent: refreshing a page cannot reset the clock and
        manufacture a shorter or ambiguous deliberation interval.
        """
        proposal = self.get_proposal(request_id)
        key = f"{request_id}:{reviewer}"
        existing = self.objects.get("review_session", key)
        if existing is not None:
            if existing.get("proposal_digest") != proposal.digest:
                raise ExecutionDenied(
                    "REVIEW_SESSION_CONFLICT", "the proposal changed after review began"
                )
            return existing
        session = {
            "request_id": request_id,
            "reviewer": reviewer,
            "proposal_digest": proposal.digest,
            "presented_at": time.time(),
        }
        put_once = getattr(self.objects, "put_if_absent", None)
        if put_once is None:
            self.objects.put("review_session", key, session)
            return session
        if put_once("review_session", key, session):
            return session
        # Another worker won the first-presentation race. Its time is the one
        # every worker must now use.
        return self.objects.get("review_session", key)

    def review_started_at(self, request_id: str, *, reviewer: str) -> float | None:
        session = self.objects.get("review_session", f"{request_id}:{reviewer}")
        return None if session is None else float(session["presented_at"])

    def endorse_review(self, request_id: str, *, reviewer: str, reviewer_role: str) -> dict:
        """Persist a distinct authenticated reviewer's escalation endorsement."""
        proposal = self.get_proposal(request_id)
        if reviewer == proposal.requester:
            raise ExecutionDenied(
                "SEPARATION_OF_DUTIES", "requester cannot endorse their own proposal"
            )
        presented_at = self.review_started_at(request_id, reviewer=reviewer)
        if presented_at is None:
            raise ExecutionDenied(
                "DELIBERATION_UNVERIFIABLE", "begin the second review before endorsing it"
            )
        monitor = getattr(self.authority, "_oversight", None)
        now = time.time()
        floor = 0.0 if monitor is None else monitor.policy.min_deliberation_seconds
        if now - presented_at < floor:
            raise ExecutionDenied(
                "DELIBERATION_TOO_SHORT",
                f"second review returned in {now - presented_at:.1f}s, below the declared "
                f"deliberation floor of {floor:.1f}s",
            )
        endorsement = {
            "request_id": request_id,
            "reviewer": reviewer,
            "reviewer_role": reviewer_role,
            "proposal_digest": proposal.digest,
            "presented_at": presented_at,
            "endorsed_at": now,
        }
        put_once = getattr(self.objects, "put_if_absent", None)
        if put_once is None:
            existing = self.objects.get("review_endorsement", request_id)
            if existing is None:
                self.objects.put("review_endorsement", request_id, endorsement)
                return endorsement
        elif put_once("review_endorsement", request_id, endorsement):
            return endorsement
        existing = self.objects.get("review_endorsement", request_id)
        if (
            existing is not None
            and existing.get("reviewer") == reviewer
            and existing.get("reviewer_role") == reviewer_role
            and existing.get("proposal_digest") == proposal.digest
        ):
            return existing
        raise ExecutionDenied(
            "REVIEW_ENDORSEMENT_CONFLICT",
            "this proposal already has a different second-review endorsement",
        )

    def review_endorser(self, request_id: str) -> str | None:
        endorsement = self.objects.get("review_endorsement", request_id)
        if endorsement is None:
            return None
        proposal = self.get_proposal(request_id)
        if endorsement.get("proposal_digest") != proposal.digest:
            raise ExecutionDenied(
                "REVIEW_SESSION_CONFLICT", "the proposal changed after endorsement"
            )
        return str(endorsement["reviewer"])

    def review_endorsement(self, request_id: str) -> dict | None:
        """Return the digest-bound second-review record, if one exists."""
        endorsement = self.objects.get("review_endorsement", request_id)
        if endorsement is None:
            return None
        proposal = self.get_proposal(request_id)
        if endorsement.get("proposal_digest") != proposal.digest:
            raise ExecutionDenied(
                "REVIEW_SESSION_CONFLICT", "the proposal changed after endorsement"
            )
        if not endorsement.get("reviewer") or not endorsement.get("reviewer_role"):
            raise ExecutionDenied(
                "REVIEW_ENDORSEMENT_INVALID", "second-review identity or role is missing"
            )
        return endorsement

    def approve(
        self,
        request_id: str,
        *,
        approver: str,
        approver_role: str,
        ttl_seconds: int = 300,
        presented_at: float | None = None,
        second_approver: str | None = None,
        second_approver_role: str | None = None,
    ) -> Approval:
        """Issue an approval, subject to the review-load policy if one is configured.

        ``presented_at`` is when this proposal was **put in front of this
        reviewer**, and the caller must supply it because only the caller knows.
        It is deliberately not inferred from the proposal's creation time: a
        proposal that sat in a queue for an hour and was then approved in two
        seconds has an hour of elapsed time and two seconds of deliberation, and
        using the former would let exactly the behaviour the floor exists to catch
        pass as careful review.

        When a deliberation floor is configured and ``presented_at`` is absent,
        the oversight monitor fails closed rather than assuming.
        """
        proposal = self.get_proposal(request_id)
        approval = self.authority.approve(
            proposal,
            approver=approver,
            approver_role=approver_role,
            ttl_seconds=ttl_seconds,
            presented_at=presented_at,
            second_approver=second_approver,
            second_approver_role=second_approver_role,
        )
        self.objects.put("approval", request_id, asdict(approval))
        self._emit(
            "action.approved",
            {"request_id": request_id, "approval_id": approval.approval_id,
             "approver": approver, "approver_role": approver_role,
             "second_approver": approval.second_approver,
             "second_approver_role": approval.second_approver_role},
            proposal.case_id,
        )
        return approval

    def execute(self, request_id: str):
        proposal = self.get_proposal(request_id)
        approval = self.get_approval(request_id)
        result = self.executor.execute(proposal, approval)
        if not result.replayed:
            self.metrics.mutations += 1
        self.objects.put("result", request_id, asdict(result))
        self._emit("action.executed", asdict(result), proposal.case_id)
        return result

    # -- lookups -----------------------------------------------------------
    def get_proposal(self, request_id: str) -> ActionProposal:
        value = self.objects.get("proposal", request_id)
        if value is None:
            raise ExecutionDenied("PROPOSAL_NOT_FOUND", "proposal does not exist")
        return ActionProposal(**value)

    def get_approval(self, request_id: str) -> Approval:
        value = self.objects.get("approval", request_id)
        if value is None:
            raise ExecutionDenied("APPROVAL_NOT_FOUND", "approval does not exist")
        return Approval(**value)

    def get_result(self, request_id: str) -> dict | None:
        return self.objects.get("result", request_id)

    def evidence_for(self, request_id: str) -> list[dict]:
        return [
            asdict(record) for record in self.evidence
            if record.payload.get("request_id") == request_id
        ]

    def evidence_page(self, *, offset: int = 0, limit: int = 100, kind: str | None = None) -> dict:
        records = [
            asdict(record) for record in self.evidence
            if kind is None or record.kind == kind
        ]
        window = records[offset: offset + limit]
        return {
            "total": len(records),
            "offset": offset,
            "limit": limit,
            "chain_valid": self.evidence.verify(),
            "records": window,
        }

    # -- recovery ----------------------------------------------------------
    def reconcile(self) -> int:
        reconciled = self.executor.reconcile_pending()
        self.metrics.outcomes_reconciled += reconciled
        return reconciled

    @property
    def pending_outcomes(self) -> int:
        return getattr(self.executor, "pending_outcome_count", 0)

    def _emit(self, kind: str, payload: dict, key: str) -> None:
        self.events.append({"kind": kind, "payload": payload}, key=key)


__all__ = ["ControlPlane", "MemoryObjectStore", "ObjectStore"]
