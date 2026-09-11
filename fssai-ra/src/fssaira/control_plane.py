"""Application-neutral orchestration for proposals, approvals, and execution."""
from __future__ import annotations

from dataclasses import asdict
from typing import Protocol, TypeVar
import uuid

from .event_transport import EventLog, KafkaLike
from .exact_action import (
    ActionProposal,
    Approval,
    ApprovalAuthority,
    CaseRegister,
    ExecutionDenied,
)
from .evidence import EvidenceLedger
from .profiles import ApplicationProfile

T = TypeVar("T")


class ObjectStore(Protocol):
    def put(self, namespace: str, key: str, value: dict) -> None: ...
    def get(self, namespace: str, key: str) -> dict | None: ...


class MemoryObjectStore:
    def __init__(self) -> None:
        self._objects: dict[tuple[str, str], dict] = {}

    def put(self, namespace: str, key: str, value: dict) -> None:
        self._objects[(namespace, key)] = dict(value)

    def get(self, namespace: str, key: str) -> dict | None:
        value = self._objects.get((namespace, key))
        return None if value is None else dict(value)


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
        objects: ObjectStore | None = None,
        events: KafkaLike | None = None,
        outcome_store=None,
        approval_use_store=None,
        approval_keys: dict[str, str] | None = None,
    ) -> None:
        self.profile = profile
        self.register = CaseRegister({}) if register is None else register
        self.evidence = EvidenceLedger(evidence_token) if evidence is None else evidence
        self.authority = ApprovalAuthority() if authority is None else authority
        self.objects = MemoryObjectStore() if objects is None else objects
        self.events = EventLog() if events is None else events
        self.executor = profile.make_executor(
            self.register,
            self.evidence,
            evidence_token,
            approval_keys=approval_keys,
            outcome_store=outcome_store,
            approval_use_store=approval_use_store,
        )

    def register_resource(self, resource_id: str, *, status: str, version: int = 1) -> dict:
        if status not in {rule.from_status for rule in self.profile.transitions}:
            raise ExecutionDenied("INITIAL_STATE_NOT_ALLOWED", "state is not a profiled starting state")
        if not self.register.seed(resource_id, status=status, version=version):
            raise ExecutionDenied("RESOURCE_ALREADY_EXISTS", "resource already exists")
        resource = {"resource_id": resource_id, "status": status, "version": version}
        self._emit("resource.registered", resource, resource_id)
        return resource

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
        proposal = ActionProposal(
            request_id=request_id or str(uuid.uuid4()),
            requester=requester,
            operation=operation,
            case_id=resource_id,
            expected_version=self.register.get(resource_id)["version"],
            from_status=from_status,
            to_status=to_status,
            evidence_version=evidence_version,
        )
        allowed = self.profile.transition_rules.get(operation, set())
        if (from_status, to_status) not in allowed:
            raise ExecutionDenied("TRANSITION_NOT_ALLOWED", "transition is not declared by profile")
        self.objects.put("proposal", proposal.request_id, asdict(proposal))
        self._emit("action.proposed", asdict(proposal), resource_id)
        return proposal

    def approve(
        self,
        request_id: str,
        *,
        approver: str,
        approver_role: str,
        ttl_seconds: int = 300,
    ) -> Approval:
        proposal = self.get_proposal(request_id)
        approval = self.authority.approve(
            proposal,
            approver=approver,
            approver_role=approver_role,
            ttl_seconds=ttl_seconds,
        )
        self.objects.put("approval", request_id, asdict(approval))
        self._emit(
            "action.approved",
            {"request_id": request_id, "approval_id": approval.approval_id,
             "approver": approver, "approver_role": approver_role},
            proposal.case_id,
        )
        return approval

    def execute(self, request_id: str):
        proposal = self.get_proposal(request_id)
        approval = self.get_approval(request_id)
        result = self.executor.execute(proposal, approval)
        self.objects.put("result", request_id, asdict(result))
        self._emit("action.executed", asdict(result), proposal.case_id)
        return result

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

    def evidence_for(self, request_id: str) -> list[dict]:
        return [asdict(record) for record in self.evidence if record.payload.get("request_id") == request_id]

    def reconcile(self) -> int:
        return self.executor.reconcile_pending()

    def _emit(self, kind: str, payload: dict, key: str) -> None:
        self.events.append({"kind": kind, "payload": payload}, key=key)
