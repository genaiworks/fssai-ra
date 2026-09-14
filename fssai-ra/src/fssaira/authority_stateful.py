"""Stateful testing: random sequences of grants, delegations, reads, revocations, and actions.

Single-step attacks miss failures that need history: a summary drafted before consent was
withdrawn, a delegation made before its root was revoked, an approval reused after the
record moved on. This harness generates seeded sequences such as

    grant → delegate → read → revoke → read → delegate → expire → execute → retry

and after **every** transition compares the real world with an independent reference
model that knows nothing about the mediators' code. It checks eight properties:

  P1  no unauthorized write           P5  expired authority cannot be used
  P2  no unauthorized protected read  P6  output restrictions never decrease without approval
  P3  child authority ⊆ parent        P7  every consequential action produces evidence
  P4  revoked authority cannot be used P8  replay causes no additional mutation

The reference model also reports **false denials** (the world refused what the model says
was allowed), so a world that refuses everything cannot pass silently.
"""
from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import dataclass, field

from .custody_errors import DENIALS, denial_code
from .disclosure import DataLabel
from .education_world import ALL_CONTROLS, STUDENTS, EducationWorld

PROPERTIES = {
    "P1": "no unauthorized write",
    "P2": "no unauthorized protected read",
    "P3": "child authority never exceeds parent authority",
    "P4": "revoked authority cannot be used",
    "P5": "expired authority cannot be used",
    "P6": "output restrictions cannot decrease without explicit authorization",
    "P7": "every consequential action produces evidence",
    "P8": "replay cannot cause an additional mutation",
}
OPERATIONS = ("grant", "delegate", "read", "revoke", "expire", "withdraw_consent", "execute", "retry",
              "replay", "derive")
FIELDS = ("attendance_rate", "current_grades", "academic_history", "support_plan")
SUBJECTS = tuple(sorted(STUDENTS))
PURPOSES = ("academic-support", "institutional-research")


@dataclass
class _GrantModel:
    grant: object
    holder: str
    purpose: str
    subjects: frozenset
    fields: frozenset
    expires_at: float
    ancestry: tuple
    parent_fields: frozenset | None = None
    parent_subjects: frozenset | None = None


@dataclass
class StatefulReport:
    sequences: int
    steps: int
    controls_removed: tuple[str, ...]
    violations: dict = field(default_factory=lambda: dict.fromkeys(PROPERTIES, 0))
    false_denials: int = 0
    operations: dict = field(default_factory=dict)
    first_counterexample: list = field(default_factory=list)

    @property
    def holds(self) -> bool:
        return not any(self.violations.values())

    def to_dict(self) -> dict:
        return {"sequences": self.sequences, "steps": self.steps,
                "controls_removed": list(self.controls_removed),
                "properties": {k: {"property": PROPERTIES[k], "violations": v}
                               for k, v in self.violations.items()},
                "total_violations": sum(self.violations.values()), "false_denials": self.false_denials,
                "operations": dict(sorted(self.operations.items())), "holds": self.holds,
                "first_counterexample": self.first_counterexample}


def _run_sequence(rng: random.Random, controls: Iterable[str], length: int, report: StatefulReport,
                  trace: list) -> None:
    world = EducationWorld(controls)
    grants: dict[str, _GrantModel] = {}
    revoked: set[str] = set()
    withdrawn: set[tuple[str, str]] = set()
    sessions: dict[str, tuple[str, set]] = {}
    approvals: list = []           # (proposal, approval)
    used_approvals: set[str] = set()
    expected_mutations = 0

    def violate(key: str, detail: str) -> None:
        report.violations[key] += 1
        if not report.first_counterexample:
            report.first_counterexample = [*trace, f"VIOLATION {key}: {detail}"]

    for _ in range(length):
        op = rng.choice(OPERATIONS)
        report.operations[op] = report.operations.get(op, 0) + 1
        report.steps += 1
        if op == "grant":
            fields = frozenset(rng.sample(FIELDS, rng.randint(1, 3)))
            subjects = frozenset(rng.sample(SUBJECTS, rng.randint(1, 2)))
            purpose = rng.choice(PURPOSES)
            ttl = rng.choice((120.0, 900.0, 3600.0))
            grant = world.grant(holder="support-agent", purpose=purpose, subjects=subjects, fields=fields,
                                ttl_seconds=ttl)
            grants[grant.grant_id] = _GrantModel(grant, "support-agent", purpose, subjects, fields,
                                                 world.now + ttl, (grant.grant_id,))
            trace.append(f"grant {grant.grant_id} {purpose} {sorted(fields)}")
        elif op == "delegate" and grants:
            parent = grants[rng.choice(sorted(grants))]
            if parent.grant.grant_id.count("/") >= 2:
                continue
            escalate = rng.random() < 0.4
            fields = set(rng.sample(sorted(parent.fields), rng.randint(1, len(parent.fields))))
            if escalate:
                fields.add(rng.choice(FIELDS))
            subjects = set(rng.sample(sorted(parent.subjects), 1))
            classes = {world.policy.field_classes[f] for f in fields}
            ttl = rng.choice((60.0, 600.0, 7200.0))
            root = grants[parent.ancestry[0]].grant
            hop_parent = parent.ancestry[-1] if len(parent.ancestry) > 1 else root.grant_id
            hop = world.data_delegation.delegate(
                parent_id=hop_parent, delegator="support-agent", delegate="support-agent-delegate",
                purpose=parent.purpose, subjects=subjects, fields=fields, classes=classes,
                issued_at=world.now, expires_at=world.now + ttl)
            if len(parent.ancestry) > 1:
                continue    # keep chains one hop deep from a root; depth is exercised elsewhere
            code, effective = _attempt(world.data_delegation.exchange, root, [hop],
                                       requester="support-agent-delegate", now=world.now)
            trace.append(f"delegate from {parent.grant.grant_id} fields={sorted(fields)} -> {code or 'ok'}")
            if effective is not None:
                g = effective.grant
                if not (g.fields <= parent.fields and g.subjects <= parent.subjects
                        and g.expires_at <= parent.expires_at + 1e-6 and g.purpose == parent.purpose):
                    violate("P3", f"effective grant {g.grant_id} exceeds its parent")
                grants[g.grant_id] = _GrantModel(g, "support-agent-delegate", g.purpose, g.subjects, g.fields,
                                                 g.expires_at, (root.grant_id, hop.hop_id))
        elif op == "read" and grants:
            model = grants[rng.choice(sorted(grants))]
            subjects = frozenset(rng.sample(SUBJECTS, rng.randint(1, 2)))
            fields = frozenset(rng.sample(FIELDS, rng.randint(1, 2)))
            purpose = model.purpose if rng.random() < 0.8 else rng.choice(PURPOSES)
            session = f"session-{rng.randint(1, 3)}-{model.holder}"
            before = len(world.observed.model_inputs)
            code, context = _attempt(world.read, requester=model.holder, grant=model.grant,
                                     purpose=purpose, subjects=subjects, fields=fields, session_id=session)
            is_revoked = any(a in revoked for a in model.ancestry)
            is_expired = world.now >= model.expires_at
            allowed = (not is_revoked and not is_expired and purpose == model.purpose
                       and subjects <= model.subjects and fields <= model.fields
                       and not any((s, purpose) in withdrawn for s in subjects))
            trace.append(f"read {model.grant.grant_id} {sorted(subjects)} {sorted(fields)} {purpose} -> {code or 'released'}")
            leaked = context is not None and len(world.observed.model_inputs) > before
            if leaked and not allowed:
                key = "P4" if is_revoked else "P5" if is_expired else "P2"
                violate(key, f"released {sorted(fields)} of {sorted(subjects)} under {model.grant.grant_id}")
            elif allowed and context is None:
                report.false_denials += 1
            if context is not None:
                label = world.gate.session_label(session)
                sessions[session] = (model.holder, set(label.classes) if label else set())
        elif op == "revoke" and grants:
            target = rng.choice(sorted(grants))
            world.data_delegation.revoke(target, by="privacy-officer-ng", reason="stateful")
            revoked.add(target)
            trace.append(f"revoke {target}")
        elif op == "expire":
            step = rng.choice((30.0, 300.0, 1800.0))
            world.tick(step)
            trace.append(f"advance clock {step}s")
        elif op == "withdraw_consent":
            subject, purpose = rng.choice(SUBJECTS), rng.choice(PURPOSES)
            world.gate.withdraw_consent(subject, purpose, recorded_by=subject)
            withdrawn.add((subject, purpose))
            trace.append(f"withdraw consent {subject} {purpose}")
        elif op == "execute":
            student = rng.choice(SUBJECTS)
            resource = f"transcript:{student}:MATH101"
            current = world.register.get(resource)["status"]
            target = rng.choice([g for g in ("grade:A", "grade:B", "grade:C", "grade:D") if g != current])
            proposal = world.propose(requester="support-agent", operation="correct_transcript_grade",
                                     resource=resource, to_status=target)
            approved = rng.random() < 0.7
            approval = None
            if approved:
                code, approval = _attempt(world.review_and_approve, proposal, reviewer="dr-lin")
            before = world.register.mutation_count
            code, _ = _attempt(world.execute, proposal, approval)
            legitimate = approval is not None and approval.approval_id not in used_approvals
            if world.register.mutation_count > before:
                if not legitimate:
                    violate("P1", f"{proposal.request_id} mutated without a fresh human approval")
                expected_mutations += 1
                used_approvals.add(approval.approval_id)
                approvals.append((proposal, approval))
                intents = world.ledger.find("action_intent", request_id=proposal.request_id)
                outcomes = world.ledger.find("action_outcome", request_id=proposal.request_id)
                if len(intents) != 1 or len(outcomes) != 1:
                    violate("P7", f"{proposal.request_id} has {len(intents)} intent and {len(outcomes)} outcome")
            trace.append(f"execute {proposal.request_id} {resource} -> {code or 'executed'}")
        elif op == "retry" and approvals:
            proposal, approval = rng.choice(approvals)
            before = world.register.mutation_count
            _attempt(world.execute, proposal, approval)
            if world.register.mutation_count > before:
                violate("P8", f"retry of {proposal.request_id} mutated again")
            trace.append(f"retry {proposal.request_id}")
        elif op == "replay" and approvals:
            proposal, approval = rng.choice(approvals)
            resource = proposal.case_id
            current = world.register.get(resource)
            fresh = world.propose(requester="support-agent", operation=proposal.operation, resource=resource,
                                  to_status=proposal.to_status if current["status"] != proposal.to_status else "grade:D")
            before = world.register.mutation_count
            _attempt(world.execute, fresh, approval)
            if world.register.mutation_count > before:
                violate("P8", f"approval {approval.approval_id} replayed onto {fresh.request_id}")
            trace.append(f"replay approval onto {fresh.request_id}")
        elif op == "derive" and sessions:
            session = rng.choice(sorted(sessions))
            holder, classes = sessions[session]
            code, output = _attempt(world.derive, requester=holder, session_id=session, content="summary",
                                    claimed_label=DataLabel.bottom(world.policy))
            if output is not None and hasattr(output, "label") and not classes <= set(output.label.classes):
                violate("P6", f"output {output.output_id} lost classes {sorted(classes - set(output.label.classes))}")
            trace.append(f"derive in {session} -> {code or 'labelled'}")
        if world.register.mutation_count != expected_mutations:
            violate("P1", f"register shows {world.register.mutation_count} mutations; {expected_mutations} were authorized")
            expected_mutations = world.register.mutation_count
        del trace[:-12]


def _attempt(action, *args, **kwargs):
    try:
        return "", action(*args, **kwargs)
    except DENIALS as exc:
        return denial_code(exc), None


def run_stateful(*, sequences: int = 120, length: int = 25, seed: int = 20261125,
                 remove: Iterable[str] = ()) -> StatefulReport:
    removed = tuple(sorted(remove))
    controls = [c for c in ALL_CONTROLS if c not in removed]
    rng = random.Random(seed)
    report = StatefulReport(sequences, 0, removed)
    for _ in range(sequences):
        _run_sequence(rng, controls, length, report, [])
    return report


__all__ = ["OPERATIONS", "PROPERTIES", "StatefulReport", "run_stateful"]
