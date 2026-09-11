"""Bounded model checking of a profile's authority properties.

The control contract says what must be true. The test suite shows it holds for
the cases someone thought to write. This module closes the gap between them: it
enumerates the declared state space of an application profile and runs the *real*
executor against every combination, then checks five invariants over the results.

Why this is worth doing
-----------------------
A hand-written adversarial suite proves that the attacks the author imagined are
contained. It says nothing about the attack the author did not imagine -- and
the interesting failures in authorization systems are almost always a
combination nobody enumerated: a valid approval for the right operation but a
stale version, a correctly-signed approval whose audience belongs to a different
executor, a role that is permitted for one transition being reused on another.

The space of such combinations is small enough to enumerate exactly. For a
profile with S statuses, O operations, and V approval variants, the checker
visits ``S x S x (O+1) x V x identities x versions`` configurations, executes
each one, and records what the register did. Because every configuration runs the
production code path, a violation is a real defect rather than a modelling
artifact.

What the result means, precisely
--------------------------------
A clean run states: *within the declared bounds*, there is no configuration in
which the executor mutates the register without a valid, unexpired,
correctly-scoped, single-use approval bound to that exact proposal and that
exact resource version, and every mutation leaves a complete, verifiable
evidence pair.

It is bounded model checking, not a proof. Unbounded version numbers, arbitrary
identity strings, concurrent interleavings, and any behaviour of the surrounding
infrastructure are outside the bounds and stated as such in the report. What it
replaces is the weaker sentence "we tested some attacks".
"""
from __future__ import annotations

import itertools
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone

from .evidence import EvidenceLedger
from .exact_action import (
    ActionProposal,
    Approval,
    ApprovalAuthority,
    CaseRegister,
    ExecutionDenied,
    ExecutionUncertain,
)
from .profiles import ApplicationProfile

TOKEN = "verification-evidence-writer"
NOW = 1_000_000.0
TTL = 300.0

#: Ways an approval can be wrong. ``valid`` is the only one that may mutate.
#:
#: Several variants are deliberately *authentically signed*. Tampering with a
#: signed field is caught by the signature and never reaches the checks behind
#: it, so a suite built only from tampered approvals would silently leave the
#: audience, digest, role, and expiry checks unexercised. The realistic threat is
#: not a forged approval but a genuine one pointed at the wrong thing: a real
#: reviewer's real signature, for a different proposal, a different executor, or
#: a transition their role does not cover. Those variants below carry a valid
#: signature from a real authority and must still be denied.
APPROVAL_VARIANTS = (
    "valid",
    "absent",
    "authentic_expired",             # genuine signature, past its expiry
    "forged_signature",              # field tampering; signature must catch it
    "untrusted_key",                 # signed by a key the executor does not trust
    "authentic_wrong_audience",      # genuine signature, addressed to another executor
    "authentic_wrong_role",          # genuine signature, role not permitted here
    "authentic_other_proposal",      # genuine signature, for a different proposal
    "digest_mismatch",               # field tampering on the binding itself
    "self_approved",                 # separation of duties
)


@dataclass(frozen=True)
class Configuration:
    """One point in the enumerated space."""

    operation: str
    from_status: str
    to_status: str
    approval_variant: str
    version_is_current: bool
    resource_exists: bool

    def key(self) -> str:
        return "|".join([
            self.operation, self.from_status, self.to_status, self.approval_variant,
            "v=current" if self.version_is_current else "v=stale",
            "exists" if self.resource_exists else "missing",
        ])


@dataclass(frozen=True)
class Observation:
    """What actually happened when that configuration was executed."""

    configuration: Configuration
    mutated: bool
    outcome: str
    intent_records: int
    outcome_records: int
    chain_valid: bool
    approver_equals_requester: bool


@dataclass(frozen=True)
class Violation:
    invariant: str
    configuration: str
    detail: str


@dataclass
class VerificationReport:
    profile_id: str
    profile_version: str
    generated_at: str
    states_explored: int
    mutations_observed: int
    invariants: tuple[str, ...]
    violations: tuple[Violation, ...]
    bounds: dict = field(default_factory=dict)
    outcome_histogram: dict = field(default_factory=dict)

    @property
    def holds(self) -> bool:
        return not self.violations

    def to_dict(self) -> dict:
        return {
            "schema_version": "1.0",
            "kind": "bounded-model-check",
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "generated_at": self.generated_at,
            "summary": {
                "states_explored": self.states_explored,
                "mutations_observed": self.mutations_observed,
                "invariants_checked": len(self.invariants),
                "violations": len(self.violations),
                "holds": self.holds,
            },
            "invariants": list(self.invariants),
            "bounds": self.bounds,
            "outcome_histogram": self.outcome_histogram,
            "violations": [asdict(v) for v in self.violations],
        }


INVARIANTS = (
    "INV-1 no mutation without a valid, in-scope, unexpired, single-use approval "
    "bound to this exact proposal and resource version",
    "INV-2 every mutation is accompanied by exactly one intent record and one outcome record",
    "INV-3 no configuration produces more than one mutation for one request identifier",
    "INV-4 the evidence chain verifies in every reachable state, mutating or not",
    "INV-5 no mutation is authorized by the requester approving their own proposal",
)


class ProfileVerifier:
    """Enumerate and execute the declared authority space of one profile."""

    def __init__(self, profile: ApplicationProfile) -> None:
        if not profile.transitions:
            raise ValueError("profile must declare at least one transition")
        self.profile = profile
        self.statuses = sorted(
            {rule.from_status for rule in profile.transitions}
            | {rule.to_status for rule in profile.transitions}
        )
        self.operations = sorted(profile.allowed_operations) + ["operation_not_in_profile"]
        self.roles = sorted({rule.approval_role for rule in profile.transitions}) or ["authorized_reviewer"]

    # -- enumeration -------------------------------------------------------
    def configurations(self) -> Iterable[Configuration]:
        for operation, from_status, to_status, variant, current, exists in itertools.product(
            self.operations, self.statuses, self.statuses, APPROVAL_VARIANTS, (True, False), (True, False)
        ):
            if from_status == to_status:
                continue  # a no-op transition is not an authority question
            yield Configuration(operation, from_status, to_status, variant, current, exists)

    # -- execution ---------------------------------------------------------
    def observe(self, configuration: Configuration) -> Observation:
        cases = (
            {"resource-1": {"status": configuration.from_status, "version": 3}}
            if configuration.resource_exists else {}
        )
        register = CaseRegister(cases)
        evidence = EvidenceLedger(TOKEN)
        executor = self.profile.make_executor(register, evidence, TOKEN)
        authority = ApprovalAuthority()

        proposal = ActionProposal(
            request_id="verify-1",
            requester="bounded-agent",
            operation=configuration.operation,
            case_id="resource-1",
            expected_version=3 if configuration.version_is_current else 2,
            from_status=configuration.from_status,
            to_status=configuration.to_status,
            evidence_version="verification-snapshot-1",
        )
        approval, approver_is_requester = self._approval_for(configuration, proposal, authority)

        outcome = "EXECUTED"
        try:
            if approval is None:
                raise ExecutionDenied("APPROVAL_NOT_FOUND", "no approval supplied")
            executor.execute(proposal, approval, now=NOW + 1)
        except ExecutionDenied as exc:
            outcome = exc.code
        except ExecutionUncertain as exc:  # pragma: no cover - no fault injected here
            outcome = exc.code

        return Observation(
            configuration=configuration,
            mutated=register.mutation_count > 0,
            outcome=outcome,
            intent_records=len(evidence.find("action_intent")),
            outcome_records=len(evidence.find("action_outcome")),
            chain_valid=evidence.verify(),
            approver_equals_requester=approver_is_requester,
        )

    def _approval_for(
        self, configuration: Configuration, proposal: ActionProposal, authority: ApprovalAuthority
    ) -> tuple[Approval | None, bool]:
        variant = configuration.approval_variant
        if variant == "absent":
            return None, False

        role = self._required_role(configuration)

        if variant == "self_approved":
            # A correct authority refuses to issue this at all. Model the refusal
            # as "no approval exists", which is what the executor would see.
            try:
                approval = authority.approve(
                    proposal, approver=proposal.requester, approver_role=role, now=NOW
                )
            except ExecutionDenied:
                return None, True
            return approval, True

        if variant == "authentic_expired":
            # Editing ``expires_at`` would break the signature and be caught one
            # check earlier, leaving the expiry check itself unexercised. A real
            # approval that simply sat too long is the case that matters.
            return authority.approve(
                proposal, approver="authorized-reviewer", approver_role=role,
                ttl_seconds=1, now=NOW - 10,
            ), False

        if variant == "authentic_wrong_audience":
            # A real approval service, signing correctly, for a different executor.
            other = ApprovalAuthority(audience="another-executor")
            return other.approve(
                proposal, approver="authorized-reviewer", approver_role=role, now=NOW
            ), False

        if variant == "authentic_wrong_role":
            return authority.approve(
                proposal, approver="authorized-reviewer",
                approver_role="role_not_permitted_for_this_transition", now=NOW,
            ), False

        if variant == "authentic_other_proposal":
            # The reviewer really did approve something. It was not this.
            other = replace(proposal, request_id="verify-other", case_id="resource-other")
            return authority.approve(
                other, approver="authorized-reviewer", approver_role=role, now=NOW
            ), False

        approval = authority.approve(
            proposal, approver="authorized-reviewer", approver_role=role, now=NOW
        )
        if variant == "valid":
            return approval, False
        if variant == "forged_signature":
            return replace(approval, approver="attacker"), False
        if variant == "untrusted_key":
            return replace(approval, key_id="key-the-executor-does-not-trust"), False
        if variant == "digest_mismatch":
            return replace(approval, proposal_digest="0" * 64), False
        raise ValueError(f"unknown approval variant {variant!r}")  # pragma: no cover

    def _required_role(self, configuration: Configuration) -> str:
        required = self.profile.required_approval_roles.get(
            (configuration.operation, configuration.from_status, configuration.to_status)
        )
        if required:
            return sorted(required)[0]
        return self.roles[0]

    # -- invariants --------------------------------------------------------
    def _authorized(self, configuration: Configuration) -> bool:
        """The reference predicate: when *should* a mutation be permitted?

        Written independently of the executor so the two can disagree. If they
        ever do, one of them is wrong and the checker says which configuration
        exposed it.
        """
        if configuration.approval_variant != "valid":
            return False
        if not configuration.resource_exists:
            return False
        if not configuration.version_is_current:
            return False
        if configuration.operation not in self.profile.allowed_operations:
            return False
        allowed = self.profile.transition_rules.get(configuration.operation, set())
        return (configuration.from_status, configuration.to_status) in allowed

    def check(self, progress: Callable[[int], None] | None = None) -> VerificationReport:
        violations: list[Violation] = []
        histogram: dict[str, int] = {}
        explored = 0
        mutations = 0

        for configuration in self.configurations():
            observation = self.observe(configuration)
            explored += 1
            histogram[observation.outcome] = histogram.get(observation.outcome, 0) + 1
            if progress is not None and explored % 500 == 0:
                progress(explored)

            expected = self._authorized(configuration)
            if observation.mutated and not expected:
                violations.append(Violation(
                    INVARIANTS[0], configuration.key(),
                    f"register mutated with outcome {observation.outcome} but the reference "
                    "predicate says this configuration is not authorized",
                ))
            if expected and not observation.mutated:
                violations.append(Violation(
                    INVARIANTS[0], configuration.key(),
                    f"an authorized configuration was denied with {observation.outcome}; "
                    "a false denial is a service failure, not a safe default",
                ))
            if observation.mutated:
                mutations += 1
                if observation.intent_records != 1 or observation.outcome_records != 1:
                    violations.append(Violation(
                        INVARIANTS[1], configuration.key(),
                        f"intent={observation.intent_records} outcome={observation.outcome_records}",
                    ))
                if observation.approver_equals_requester:
                    violations.append(Violation(
                        INVARIANTS[4], configuration.key(),
                        "the requester approved their own proposal and it executed",
                    ))
            if not observation.chain_valid:
                violations.append(Violation(
                    INVARIANTS[3], configuration.key(), "evidence chain failed verification"
                ))

        # INV-3 is a property of repeated execution, checked separately so that
        # every profile is exercised for idempotence, not only mutating ones.
        violations.extend(self._check_idempotence())

        return VerificationReport(
            profile_id=self.profile.profile_id,
            profile_version=self.profile.version,
            generated_at=datetime.now(timezone.utc).isoformat(),
            states_explored=explored,
            mutations_observed=mutations,
            invariants=INVARIANTS,
            violations=tuple(violations),
            bounds={
                "statuses": self.statuses,
                "operations": self.operations,
                "approval_variants": list(APPROVAL_VARIANTS),
                "versions_modelled": ["current", "stale"],
                "resource_presence": ["exists", "missing"],
                "concurrency": "single-threaded; interleavings are out of bounds",
                "identities": "one requester, one reviewer, one impostor",
                "note": (
                    "exhaustive within these bounds; not a proof for unbounded versions, "
                    "arbitrary identities, concurrent execution, or infrastructure behaviour"
                ),
            },
            outcome_histogram=dict(sorted(histogram.items())),
        )

    def _check_idempotence(self) -> list[Violation]:
        violations: list[Violation] = []
        for rule in self.profile.transitions:
            register = CaseRegister({"resource-1": {"status": rule.from_status, "version": 3}})
            evidence = EvidenceLedger(TOKEN)
            executor = self.profile.make_executor(register, evidence, TOKEN)
            proposal = ActionProposal(
                request_id="verify-idem", requester="bounded-agent", operation=rule.operation,
                case_id="resource-1", expected_version=3, from_status=rule.from_status,
                to_status=rule.to_status, evidence_version="verification-snapshot-1",
            )
            approval = ApprovalAuthority().approve(
                proposal, approver="authorized-reviewer", approver_role=rule.approval_role, now=NOW
            )
            first = executor.execute(proposal, approval, now=NOW + 1)
            for attempt in range(4):
                repeat = executor.execute(proposal, approval, now=NOW + 2 + attempt)
                if repeat.receipt_hash != first.receipt_hash or not repeat.replayed:
                    violations.append(Violation(
                        INVARIANTS[2], f"{rule.operation}:{rule.from_status}->{rule.to_status}",
                        f"retry {attempt + 1} did not return the stored receipt",
                    ))
            if register.mutation_count != 1:
                violations.append(Violation(
                    INVARIANTS[2], f"{rule.operation}:{rule.from_status}->{rule.to_status}",
                    f"{register.mutation_count} mutations for one request identifier",
                ))
            if len(evidence.find("action_outcome")) != 1:
                violations.append(Violation(
                    INVARIANTS[1], f"{rule.operation}:{rule.from_status}->{rule.to_status}",
                    "repeated execution duplicated outcome evidence",
                ))
        return violations


def verify_profile(profile: ApplicationProfile) -> VerificationReport:
    return ProfileVerifier(profile).check()


__all__ = [
    "APPROVAL_VARIANTS", "Configuration", "INVARIANTS", "Observation",
    "ProfileVerifier", "VerificationReport", "Violation", "verify_profile",
]
