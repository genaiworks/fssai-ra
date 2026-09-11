"""Deterministic adversarial evaluation for an application profile."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Callable
import json
import platform
import sys

from .evidence import EvidenceLedger
from .exact_action import (
    ActionProposal,
    ApprovalAuthority,
    CaseRegister,
    ExecutionDenied,
    ExecutionUncertain,
)
from .profiles import ApplicationProfile, TransitionRule


@dataclass(frozen=True)
class ScenarioResult:
    scenario: str
    expected: str
    observed: str
    contained: bool
    mutations: int
    evidence_valid: bool


@dataclass(frozen=True)
class EvaluationReport:
    schema_version: str
    profile_id: str
    profile_version: str
    generated_at: str
    software_version: str
    python_version: str
    platform: str
    scenarios: tuple[ScenarioResult, ...]

    @property
    def passed(self) -> int:
        return sum(item.contained for item in self.scenarios)

    @property
    def total(self) -> int:
        return len(self.scenarios)

    @property
    def all_contained(self) -> bool:
        return self.passed == self.total

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "generated_at": self.generated_at,
            "environment": {
                "software_version": self.software_version,
                "python_version": self.python_version,
                "platform": self.platform,
            },
            "summary": {
                "passed": self.passed,
                "total": self.total,
                "all_contained": self.all_contained,
            },
            "scenarios": [asdict(item) for item in self.scenarios],
        }

    def write_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")


class _FailOutcomeOnceLedger(EvidenceLedger):
    def __init__(self, token: str) -> None:
        super().__init__(token)
        self.failed = False

    def append(self, kind: str, payload: dict, *, token: str):
        if kind == "action_outcome" and not self.failed:
            self.failed = True
            raise RuntimeError("simulated evidence-service interruption")
        return super().append(kind, payload, token=token)


class EvaluationRunner:
    """Run a small, inspectable suite against the exact-action enforcement path."""

    def __init__(self, profile: ApplicationProfile) -> None:
        self.profile = profile
        if not profile.transitions:
            raise ValueError("profile must define at least one transition")
        self.rule = self._select_consequential_rule(profile.transitions)
        self.token = "evaluation-evidence-writer"

    @staticmethod
    def _select_consequential_rule(rules: tuple[TransitionRule, ...]) -> TransitionRule:
        return next((rule for rule in rules if rule.consequential), rules[0])

    def _workflow(self, *, ledger: EvidenceLedger | None = None):
        register = CaseRegister({"resource-1": {"status": self.rule.from_status, "version": 1}})
        evidence = EvidenceLedger(self.token) if ledger is None else ledger
        authority = ApprovalAuthority()
        executor = self.profile.make_executor(register, evidence, self.token)
        proposal = ActionProposal(
            request_id="evaluation-request-1",
            requester="bounded-agent",
            operation=self.rule.operation,
            case_id="resource-1",
            expected_version=1,
            from_status=self.rule.from_status,
            to_status=self.rule.to_status,
            evidence_version="evaluation-snapshot-1",
        )
        return register, evidence, authority, executor, proposal

    def _denial_scenario(
        self,
        name: str,
        expected_code: str,
        alter: Callable,
    ) -> ScenarioResult:
        register, evidence, authority, executor, proposal = self._workflow()
        approval = authority.approve(
            proposal,
            approver="authorized-reviewer",
            approver_role=self.rule.approval_role,
            now=1000,
        )
        changed_proposal, changed_approval, now = alter(proposal, approval)
        try:
            executor.execute(changed_proposal, changed_approval, now=now)
            observed = "EXECUTED"
        except ExecutionDenied as exc:
            observed = exc.code
        contained = observed == expected_code and register.mutation_count == 0
        return ScenarioResult(
            name, expected_code, observed, contained, register.mutation_count, evidence.verify()
        )

    def run(self) -> EvaluationReport:
        results: list[ScenarioResult] = []

        register, evidence, authority, executor, proposal = self._workflow()
        approval = authority.approve(
            proposal,
            approver="authorized-reviewer",
            approver_role=self.rule.approval_role,
            now=1000,
        )
        first = executor.execute(proposal, approval, now=1001)
        replay = executor.execute(proposal, approval, now=1002)
        results.append(ScenarioResult(
            "approved_exact_action_and_retry",
            "ONE_MUTATION_ONE_RECEIPT",
            "ONE_MUTATION_ONE_RECEIPT" if first.receipt_hash == replay.receipt_hash else "MISMATCH",
            register.mutation_count == 1 and replay.replayed and len(evidence) == 2,
            register.mutation_count,
            evidence.verify(),
        ))

        results.extend([
            self._denial_scenario(
                "changed_target_after_approval",
                "APPROVAL_PAYLOAD_MISMATCH",
                lambda p, a: (replace(p, case_id="resource-2"), a, 1001),
            ),
            self._denial_scenario(
                "changed_arguments_after_approval",
                "APPROVAL_PAYLOAD_MISMATCH",
                lambda p, a: (replace(p, to_status="unreviewed-state"), a, 1001),
            ),
            self._denial_scenario(
                "expired_approval",
                "APPROVAL_EXPIRED",
                lambda p, a: (p, a, 1301),
            ),
            self._denial_scenario(
                "forged_approval_identity",
                "APPROVAL_SIGNATURE_INVALID",
                lambda p, a: (p, replace(a, approver="attacker"), 1001),
            ),
            self._denial_scenario(
                "unallowlisted_operation",
                "OPERATION_NOT_ALLOWED",
                lambda p, a: self._resign(replace(p, operation="unlisted_operation"), 1001),
            ),
            self._denial_scenario(
                "profile_forbidden_transition",
                "TRANSITION_NOT_ALLOWED",
                lambda p, a: self._resign(replace(p, to_status="unreviewed-state"), 1001),
            ),
        ])

        ledger = _FailOutcomeOnceLedger(self.token)
        register, evidence, authority, executor, proposal = self._workflow(ledger=ledger)
        approval = authority.approve(
            proposal,
            approver="authorized-reviewer",
            approver_role=self.rule.approval_role,
            now=1000,
        )
        observed = "NO_FAILURE"
        try:
            executor.execute(proposal, approval, now=1001)
        except ExecutionUncertain as exc:
            observed = exc.code
        pending_before = executor.pending_outcome_count
        reconciled = executor.reconcile_pending()
        contained = (
            observed == "OUTCOME_EVIDENCE_PENDING"
            and register.mutation_count == 1
            and pending_before == 1
            and reconciled == 1
            and executor.pending_outcome_count == 0
            and len(evidence.find("action_outcome", request_id=proposal.request_id)) == 1
        )
        results.append(ScenarioResult(
            "outcome_evidence_interruption_and_recovery",
            "PENDING_THEN_RECONCILED",
            "PENDING_THEN_RECONCILED" if contained else observed,
            contained,
            register.mutation_count,
            evidence.verify(),
        ))

        return EvaluationReport(
            schema_version="1.0",
            profile_id=self.profile.profile_id,
            profile_version=self.profile.version,
            generated_at=datetime.now(timezone.utc).isoformat(),
            software_version=_software_version(),
            python_version=sys.version.split()[0],
            platform=platform.platform(),
            scenarios=tuple(results),
        )

    def _resign(self, proposal: ActionProposal, now: float):
        authority = ApprovalAuthority()
        approval = authority.approve(
            proposal,
            approver="authorized-reviewer",
            approver_role=self.rule.approval_role,
            now=1000,
        )
        return proposal, approval, now


def _software_version() -> str:
    try:
        return version("fssaira")
    except PackageNotFoundError:
        return "source-tree"
