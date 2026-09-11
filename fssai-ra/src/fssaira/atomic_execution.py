"""Single-transaction accountable execution.

:class:`AccountableExecutor` is correct but structurally limited: it writes the
intent record, performs the mutation, then writes the outcome record. Between
step two and step three there is a window. If the process dies there, the case
has moved and nothing says who moved it. The v0.5.0 architecture handled that
honestly -- report ``OUTCOME_EVIDENCE_PENDING``, keep a pending outcome,
reconcile later -- and documented the residual risk.

:class:`AtomicExecutor` removes the window when the register and the evidence
ledger live in one database. Authorization is checked, then the intent record,
the mutation, the execution receipt, and the outcome record are written in a
single transaction. A crash at any instant leaves either a case that never moved
or a case that moved *with* a complete, hash-chained record of why.

Both executors share :meth:`AccountableExecutor.validate_authorization`, so the
two profiles cannot drift apart on what counts as authorized. The conformance
suite runs the identical scenario list against both.

What this does not solve: atomicity with a *foreign* system. If the real side
effect is an email, a payment, or a write into a vendor student-information
system, no database transaction can include it. That case still needs the
outbox, the idempotency key, and the reconciliation protocol -- which is why
both are kept, and why ``docs/ASSURANCE.md`` states the boundary per profile.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict

from .exact_action import (
    AccountableExecutor,
    ActionProposal,
    Approval,
    ExecutionDenied,
    ExecutionResult,
    PendingOutcome,
    validate_replay,
)
from .sql_backend import SqlDatabase


class AtomicExecutor(AccountableExecutor):
    """Accountable execution where evidence and mutation commit together."""

    #: Advertised on ``/health`` and recorded in evaluation reports, so a reader
    #: can tell which durability claim a result was produced under.
    durability = "single-transaction"

    def __init__(
        self,
        database: SqlDatabase,
        evidence_token: str,
        *,
        audience: str = "case-register-executor",
        approval_keys: dict[str, str] | None = None,
        allowed_operations: set[str] | None = None,
        transition_rules: dict[str, Iterable[tuple[str, str]]] | None = None,
        required_approval_roles: dict[tuple[str, str, str], Iterable[str]] | None = None,
    ) -> None:
        self.database = database
        super().__init__(
            register=_DatabaseRegisterView(database),
            evidence=_DatabaseEvidenceView(database),
            evidence_token=evidence_token,
            audience=audience,
            approval_keys=approval_keys,
            allowed_operations=allowed_operations,
            transition_rules=transition_rules,
            required_approval_roles=required_approval_roles,
            outcome_store=_DatabaseOutboxView(database),
            approval_use_store=_DatabaseApprovalUseView(database),
        )

    def execute(
        self,
        proposal: ActionProposal,
        approval: Approval,
        *,
        now: float | None = None,
    ) -> ExecutionResult:
        # Authorization first, outside any write. A denial must never leave a
        # transaction open or a partial record behind.
        self.validate_authorization(proposal, approval, now=now)

        with self.database.transaction() as unit:
            prior = unit.register.result_for(proposal.request_id)
            if prior is not None:
                validate_replay(proposal, prior)
                return ExecutionResult(**{**asdict(prior), "replayed": True})
            used_by, newly_bound = unit.approvals.bind(approval.approval_id, proposal.request_id)
            if used_by != proposal.request_id:
                raise ExecutionDenied("APPROVAL_REUSED", "approval was already bound to another request")
            if not newly_bound:
                prior = unit.register.result_for(proposal.request_id)
                if prior is None:
                    raise ExecutionDenied(
                        "EXECUTION_STATE_INCONSISTENT",
                        "approval use exists without a stored execution result",
                    )
                validate_replay(proposal, prior)
                return ExecutionResult(**{**asdict(prior), "replayed": True})

            unit.evidence.append(
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
            result = unit.register.transition(proposal)
            unit.evidence.append(
                "action_outcome",
                {
                    "request_id": result.request_id,
                    "case_id": result.case_id,
                    "version": result.version,
                    "status": result.status,
                    "receipt_hash": result.receipt_hash,
                    "replayed": result.replayed,
                },
                token=self._token,
            )
            return result

    def reconcile_pending(self) -> int:
        """Always zero: this profile cannot produce a pending outcome.

        Kept so the executor satisfies the same interface, and so an operator
        running the recovery procedure against the wrong profile gets a clear
        answer rather than an AttributeError.
        """
        return 0

    @property
    def pending_outcome_count(self) -> int:
        with self.database.transaction() as unit:
            return len(unit.outbox)


# ---------------------------------------------------------------------------
# Short-transaction views, for reads and for the non-atomic call sites
# ---------------------------------------------------------------------------


class _DatabaseRegisterView:
    """Register operations outside the executor's own transaction."""

    def __init__(self, database: SqlDatabase) -> None:
        self._db = database

    def get(self, case_id: str) -> dict:
        with self._db.transaction() as unit:
            return unit.register.get(case_id)

    def seed(self, case_id: str, *, status: str, version: int = 1) -> bool:
        with self._db.transaction() as unit:
            return unit.register.seed(case_id, status=status, version=version)

    def result_for(self, request_id: str):
        with self._db.transaction() as unit:
            return unit.register.result_for(request_id)

    def transition(self, proposal: ActionProposal) -> ExecutionResult:
        with self._db.transaction() as unit:
            return unit.register.transition(proposal)

    @property
    def mutation_count(self) -> int:
        with self._db.transaction() as unit:
            return unit.register.mutation_count


class _DatabaseEvidenceView:
    def __init__(self, database: SqlDatabase) -> None:
        self._db = database

    def append(self, kind: str, payload: dict, *, token: str):
        with self._db.transaction() as unit:
            return unit.evidence.append(kind, payload, token=token)

    def verify(self) -> bool:
        with self._db.transaction() as unit:
            return unit.evidence.verify()

    def find(self, kind: str | None = None, **match):
        with self._db.transaction() as unit:
            return unit.evidence.find(kind, **match)

    def records(self) -> list:
        with self._db.transaction() as unit:
            return unit.evidence.records()

    def __iter__(self):
        return iter(self.records())

    def __len__(self) -> int:
        return len(self.records())


class _DatabaseObjectStoreView:
    def __init__(self, database: SqlDatabase) -> None:
        self._db = database

    def put(self, namespace: str, key: str, value: dict) -> None:
        with self._db.transaction() as unit:
            unit.objects.put(namespace, key, value)

    def get(self, namespace: str, key: str) -> dict | None:
        with self._db.transaction() as unit:
            return unit.objects.get(namespace, key)


class _DatabaseApprovalUseView:
    def __init__(self, database: SqlDatabase) -> None:
        self._db = database

    def bind(self, approval_id: str, request_id: str) -> tuple[str, bool]:
        with self._db.transaction() as unit:
            return unit.approvals.bind(approval_id, request_id)


class _DatabaseOutboxView:
    def __init__(self, database: SqlDatabase) -> None:
        self._db = database

    def put(self, outcome: PendingOutcome) -> None:
        with self._db.transaction() as unit:
            unit.outbox.put(outcome)

    def remove(self, request_id: str) -> None:
        with self._db.transaction() as unit:
            unit.outbox.remove(request_id)

    def get(self, request_id: str):
        with self._db.transaction() as unit:
            return unit.outbox.get(request_id)

    def values(self) -> tuple:
        with self._db.transaction() as unit:
            return unit.outbox.values()

    def __len__(self) -> int:
        with self._db.transaction() as unit:
            return len(unit.outbox)


def sql_object_store(database: SqlDatabase) -> _DatabaseObjectStoreView:
    """Object store for proposals, approvals, and receipts."""
    return _DatabaseObjectStoreView(database)


def sql_evidence(database: SqlDatabase) -> _DatabaseEvidenceView:
    return _DatabaseEvidenceView(database)


def sql_register(database: SqlDatabase) -> _DatabaseRegisterView:
    return _DatabaseRegisterView(database)


__all__ = ["AtomicExecutor", "sql_evidence", "sql_object_store", "sql_register"]
