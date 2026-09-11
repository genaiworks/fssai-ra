"""Exact-action approval and idempotent execution for the teaching profile.

The model can propose an action, but it never receives the credential that
changes the case register. A human approval is bound to the canonical proposal
digest. The executor rechecks the digest, expiry, approval use, and current case
version before it records intent and attempts the transition.

This is deliberately a small in-memory reference. Production deployments must
replace its identities, keys, clock, register, and evidence store while keeping
the same observable contract and tests.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Iterable

from .evidence import EvidenceLedger


TEACHING_APPROVAL_KEY_ID = "teaching-approval-key-1"
TEACHING_APPROVAL_SIGNING_KEY = "non-secret-demo-key-replace-in-production"


def _canonical_digest(value: dict) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ActionProposal:
    request_id: str
    requester: str
    operation: str
    case_id: str
    expected_version: int
    from_status: str
    to_status: str
    evidence_version: str

    @property
    def digest(self) -> str:
        return _canonical_digest(asdict(self))


@dataclass(frozen=True)
class Approval:
    approval_id: str
    proposal_digest: str
    approver: str
    approver_role: str
    audience: str
    expires_at: float
    key_id: str
    signature: str


@dataclass(frozen=True)
class ExecutionResult:
    request_id: str
    case_id: str
    version: int
    status: str
    receipt_hash: str
    replayed: bool = False


class ExecutionDenied(RuntimeError):
    """A fail-secure denial with a stable, testable reason code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class ExecutionUncertain(RuntimeError):
    """The mutation completed but its outcome evidence still needs reconciliation."""

    def __init__(self, result: ExecutionResult) -> None:
        super().__init__(
            "OUTCOME_EVIDENCE_PENDING: the authoritative mutation completed; "
            "do not repeat it blindly"
        )
        self.code = "OUTCOME_EVIDENCE_PENDING"
        self.result = result


@dataclass(frozen=True)
class PendingOutcome:
    """Durable-outbox-shaped representation of an outcome awaiting evidence append."""

    request_id: str
    payload: dict


class PendingOutcomeStore:
    """In-memory teaching stand-in for a durable transactional outbox."""

    def __init__(self) -> None:
        self._pending: dict[str, PendingOutcome] = {}

    def put(self, outcome: PendingOutcome) -> None:
        self._pending[outcome.request_id] = outcome

    def remove(self, request_id: str) -> None:
        self._pending.pop(request_id, None)

    def get(self, request_id: str) -> PendingOutcome | None:
        return self._pending.get(request_id)

    def values(self) -> tuple[PendingOutcome, ...]:
        return tuple(self._pending.values())

    def __len__(self) -> int:
        return len(self._pending)


class CaseRegister:
    """Minimal authoritative register with version and idempotency checks."""

    def __init__(self, cases: dict[str, dict]) -> None:
        self._cases = {key: dict(value) for key, value in cases.items()}
        self._results: dict[str, ExecutionResult] = {}
        self.mutation_count = 0

    def get(self, case_id: str) -> dict:
        return dict(self._cases[case_id])

    def result_for(self, request_id: str) -> ExecutionResult | None:
        """Return a prior result without exposing the mutable internal store."""
        result = self._results.get(request_id)
        return None if result is None else ExecutionResult(**asdict(result))

    def transition(self, proposal: ActionProposal) -> ExecutionResult:
        if proposal.request_id in self._results:
            prior = self._results[proposal.request_id]
            return ExecutionResult(**{**asdict(prior), "replayed": True})

        case = self._cases.get(proposal.case_id)
        if case is None:
            raise ExecutionDenied("CASE_NOT_FOUND", "the target case does not exist")
        if case["version"] != proposal.expected_version:
            raise ExecutionDenied("CASE_VERSION_CONFLICT", "the reviewed case version is no longer current")
        if case["status"] != proposal.from_status:
            raise ExecutionDenied("CASE_STATE_CONFLICT", "the reviewed starting state is no longer current")

        case["status"] = proposal.to_status
        case["version"] += 1
        self.mutation_count += 1
        receipt = _canonical_digest({
            "request_id": proposal.request_id,
            "case_id": proposal.case_id,
            "version": case["version"],
            "status": case["status"],
        })
        result = ExecutionResult(
            proposal.request_id, proposal.case_id, case["version"], case["status"], receipt
        )
        self._results[proposal.request_id] = result
        return result


class ApprovalAuthority:
    """Teaching-profile stand-in for an authenticated human approval service."""

    def __init__(
        self,
        audience: str = "case-register-executor",
        *,
        key_id: str = TEACHING_APPROVAL_KEY_ID,
        signing_key: str = TEACHING_APPROVAL_SIGNING_KEY,
    ) -> None:
        if not key_id:
            raise ValueError("key_id must be non-empty")
        if not signing_key:
            raise ValueError("signing_key must be non-empty")
        self.audience = audience
        self.key_id = key_id
        self._signing_key = signing_key

    def approve(
        self,
        proposal: ActionProposal,
        *,
        approver: str,
        approver_role: str = "authorized_reviewer",
        ttl_seconds: int = 300,
        now: float | None = None,
    ) -> Approval:
        if approver == proposal.requester:
            raise ExecutionDenied("SEPARATION_OF_DUTIES", "requester cannot approve their own proposal")
        issued_at = time.time() if now is None else now
        unsigned = Approval(
            approval_id=str(uuid.uuid4()),
            proposal_digest=proposal.digest,
            approver=approver,
            approver_role=approver_role,
            audience=self.audience,
            expires_at=issued_at + ttl_seconds,
            key_id=self.key_id,
            signature="",
        )
        return Approval(**{**asdict(unsigned), "signature": self._sign(unsigned)})

    def _sign(self, approval: Approval) -> str:
        payload = _approval_signing_payload(approval)
        return hmac.new(
            self._signing_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()


def _approval_signing_payload(approval: Approval) -> str:
    """Canonical payload authenticated by the teaching approval authority."""
    return json.dumps(
        {
            "approval_id": approval.approval_id,
            "proposal_digest": approval.proposal_digest,
            "approver": approval.approver,
            "approver_role": approval.approver_role,
            "audience": approval.audience,
            "expires_at": approval.expires_at,
            "key_id": approval.key_id,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


class AccountableExecutor:
    """The sole teaching-profile write path for consequential transitions."""

    def __init__(
        self,
        register: CaseRegister,
        evidence: EvidenceLedger,
        evidence_token: str,
        *,
        audience: str = "case-register-executor",
        approval_keys: dict[str, str] | None = None,
        allowed_operations: set[str] | None = None,
        transition_rules: dict[str, Iterable[tuple[str, str]]] | None = None,
        required_approval_roles: dict[tuple[str, str, str], Iterable[str]] | None = None,
        outcome_store: PendingOutcomeStore | None = None,
    ) -> None:
        self._register = register
        self._evidence = evidence
        self._token = evidence_token
        self._audience = audience
        self._approval_keys = dict(
            {TEACHING_APPROVAL_KEY_ID: TEACHING_APPROVAL_SIGNING_KEY}
            if approval_keys is None
            else approval_keys
        )
        self._allowed_operations = frozenset(
            {"prepare_case_for_review"}
            if allowed_operations is None
            else allowed_operations
        )
        self._transition_rules = {
            operation: frozenset(transitions)
            for operation, transitions in (transition_rules or {}).items()
        }
        self._required_approval_roles = {
            transition: frozenset(roles)
            for transition, roles in (required_approval_roles or {}).items()
        }
        self._outcomes = PendingOutcomeStore() if outcome_store is None else outcome_store
        self._approval_uses: dict[str, str] = {}

    def execute(
        self,
        proposal: ActionProposal,
        approval: Approval,
        *,
        now: float | None = None,
    ) -> ExecutionResult:
        checked_at = time.time() if now is None else now
        if proposal.operation not in self._allowed_operations:
            raise ExecutionDenied("OPERATION_NOT_ALLOWED", "executor does not permit this operation")
        signing_key = self._approval_keys.get(approval.key_id)
        if signing_key is None:
            raise ExecutionDenied("APPROVAL_KEY_UNTRUSTED", "approval key is not trusted by executor")
        expected_signature = hmac.new(
            signing_key.encode("utf-8"),
            _approval_signing_payload(approval).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(approval.signature, expected_signature):
            raise ExecutionDenied("APPROVAL_SIGNATURE_INVALID", "approval fields were not authenticated")
        if approval.audience != self._audience:
            raise ExecutionDenied("APPROVAL_AUDIENCE_MISMATCH", "approval targets another executor")
        if approval.proposal_digest != proposal.digest:
            raise ExecutionDenied("APPROVAL_PAYLOAD_MISMATCH", "proposal changed after review")
        required_roles = self._required_approval_roles.get(
            (proposal.operation, proposal.from_status, proposal.to_status)
        )
        if required_roles is not None and approval.approver_role not in required_roles:
            raise ExecutionDenied(
                "APPROVER_ROLE_NOT_ALLOWED",
                "the authenticated approver role is not permitted for this transition",
            )
        valid_transitions = self._transition_rules.get(proposal.operation)
        if valid_transitions is not None and (
            proposal.from_status,
            proposal.to_status,
        ) not in valid_transitions:
            raise ExecutionDenied(
                "TRANSITION_NOT_ALLOWED",
                "the domain profile does not permit this state transition",
            )

        used_by = self._approval_uses.get(approval.approval_id)
        if used_by is not None and used_by != proposal.request_id:
            raise ExecutionDenied("APPROVAL_REUSED", "approval was already bound to another request")
        if used_by == proposal.request_id:
            prior = self._register.result_for(proposal.request_id)
            if prior is None:
                raise ExecutionDenied(
                    "EXECUTION_STATE_INCONSISTENT",
                    "approval use exists without a stored execution result",
                )
            if self._outcomes.get(proposal.request_id) is not None:
                raise ExecutionUncertain(prior)
            return ExecutionResult(**{**asdict(prior), "replayed": True})
        if approval.expires_at <= checked_at:
            raise ExecutionDenied("APPROVAL_EXPIRED", "approval is no longer valid")

        self._evidence.append(
            "action_intent",
            {
                "request_id": proposal.request_id,
                "proposal_digest": proposal.digest,
                "approval_id": approval.approval_id,
                "approver": approval.approver,
                "approval_key_id": approval.key_id,
                "evidence_version": proposal.evidence_version,
            },
            token=self._token,
        )
        self._approval_uses[approval.approval_id] = proposal.request_id
        result = self._register.transition(proposal)
        outcome = PendingOutcome(
            result.request_id,
            {
                "request_id": result.request_id,
                "case_id": result.case_id,
                "version": result.version,
                "status": result.status,
                "receipt_hash": result.receipt_hash,
                "replayed": result.replayed,
            },
        )
        self._outcomes.put(outcome)
        try:
            self._append_outcome(outcome)
        except Exception as exc:
            raise ExecutionUncertain(result) from exc
        return result

    def reconcile_pending(self) -> int:
        """Append pending outcomes and return the number successfully reconciled.

        A production adapter should back ``PendingOutcomeStore`` with storage that
        commits atomically with the authoritative mutation. This in-memory version
        exposes and tests the recovery protocol without claiming that guarantee.
        """
        reconciled = 0
        for outcome in self._outcomes.values():
            if self._evidence.find("action_outcome", request_id=outcome.request_id):
                self._outcomes.remove(outcome.request_id)
                reconciled += 1
                continue
            self._append_outcome(outcome)
            reconciled += 1
        return reconciled

    @property
    def pending_outcome_count(self) -> int:
        return len(self._outcomes)

    def _append_outcome(self, outcome: PendingOutcome) -> None:
        self._evidence.append("action_outcome", outcome.payload, token=self._token)
        self._outcomes.remove(outcome.request_id)
