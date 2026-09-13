"""Stateful, randomized testing of governed disclosure against a reference model.

The bounded model check in :mod:`fssaira.disclosure_eval` enumerates every
combination for *one* read and *one* release. It cannot see what happens across
a session: a grant revoked between a read and a release, consent withdrawn after
a summary was drafted, a second read that should tighten the label of an output
derived earlier, or time passing until a grant expires.

Those are the failures that occur in operation, so this module generates long
random sequences of grant, revoke, consent, time, read, derive, declassify, and
release operations, executes each against the real gate, and compares every
outcome with a reference model written independently of the gate. Any
disagreement is reported with the step that exposed it and the trace before it.

The reference model states the rules in their simplest form:

* a read is permitted only under a trusted, current grant held by the requester,
  for its purpose, covering every subject, field, and class, with consent for
  every subject, at an endpoint whose zone may process every class, in a session
  the requester owns;
* an output's label is the join of every read in its session before it was derived;
* a release is permitted only if the recipient dominates the output's label, and,
  checked again at the moment of release, every subject still consents to the
  release purpose and no grant that fed the output has been revoked or has expired.

That last clause is the one the first run of this harness found missing.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from .disclosure import (
    ALL_CHECKS,
    ConsentRegister,
    DataLabel,
    DeclassificationAuthority,
    DisclosureDenied,
    DisclosureGate,
    DisclosurePolicy,
    GrantAuthority,
)
from .evidence import EvidenceLedger

TOKEN = "stateful-disclosure-writer"
AGENTS = ("agent-a", "agent-b")
ISSUER = "data-owner"
REVIEWER = "independent-reviewer"
SUBJECTS = ("subject-1", "subject-2", "subject-3")
OPERATIONS = ("issue", "revoke", "withdraw", "restore", "tick", "read", "read",
              "read", "derive", "derive", "declassify", "release", "release")


@dataclass
class _Grant:
    grant: object
    revoked: bool = False


@dataclass
class _Session:
    holder: str
    label: DataLabel
    grants: set = field(default_factory=set)


@dataclass
class _Output:
    output: object
    label: DataLabel
    holder: str
    grants: frozenset


@dataclass
class Disagreement:
    sequence: int
    step: int
    operation: str
    expected: str
    actual: str
    trace: list

    def to_dict(self) -> dict:
        return {"sequence": self.sequence, "step": self.step, "operation": self.operation,
                "expected": self.expected, "actual": self.actual, "trace": self.trace[-8:]}


@dataclass
class StatefulReport:
    sequences: int
    steps: int
    operations: dict
    released: dict
    disagreements: list

    @property
    def holds(self) -> bool:
        return not self.disagreements

    def to_dict(self) -> dict:
        by_operation: dict = {}
        for item in self.disagreements:
            by_operation[item.operation] = by_operation.get(item.operation, 0) + 1
        return {
            "kind": "disclosure-stateful-random-testing",
            "summary": {
                "sequences": self.sequences,
                "steps": self.steps,
                "disagreements": len(self.disagreements),
                "disagreements_by_operation": by_operation,
                "holds": self.holds,
            },
            "operations": self.operations,
            "permitted": self.released,
            "first_disagreements": [d.to_dict() for d in self.disagreements[:5]],
            "limits": [
                "random sequences over synthetic records and one policy at a time; not "
                "exhaustive over sequence space",
                "single-threaded; concurrent revocation during a read is out of scope",
                "break-glass is covered by the bounded model check, not by these sequences",
            ],
        }


class _Reference:
    """The rules, stated without reference to the gate's implementation."""

    def __init__(self, policy: DisclosurePolicy) -> None:
        self.policy = policy
        self.grants: dict[str, _Grant] = {}
        self.withdrawn: set = set()
        self.sessions: dict[str, _Session] = {}
        self.outputs: dict[str, _Output] = {}

    def bottom(self) -> DataLabel:
        return DataLabel.bottom(self.policy)

    def current(self, grant_id: str, now: float) -> bool:
        entry = self.grants.get(grant_id)
        return bool(entry) and not entry.revoked and now < entry.grant.expires_at

    def read_allowed(self, agent, session_id, grant_id, purpose, subjects, fields,
                     endpoint, now) -> bool:
        policy = self.policy
        entry = self.grants.get(grant_id)
        if entry is None or not subjects or not fields:
            return False
        grant = entry.grant
        classes = {policy.field_classes[f] for f in fields}
        zone = policy.endpoints.get(endpoint)
        session = self.sessions.get(session_id)
        return (
            grant.holder == agent and grant.issued_by != agent
            and self.current(grant_id, now)
            and purpose in policy.purposes and purpose == grant.purpose
            and set(subjects) <= grant.subjects and set(fields) <= grant.fields
            and classes <= grant.classes
            and all((s, purpose) not in self.withdrawn for s in subjects)
            and zone is not None and all(zone in policy.class_zones[c] for c in classes)
            and (session is None or session.holder == agent)
        )

    def apply_read(self, agent, session_id, grant_id, purpose, subjects, fields) -> None:
        policy = self.policy
        label = self.bottom()
        for s in subjects:
            for f in fields:
                cls = policy.field_classes[f]
                label = label.join(DataLabel(frozenset({cls}), frozenset({s}),
                                             frozenset({purpose}), policy.class_zones[cls]))
        session = self.sessions.setdefault(session_id, _Session(agent, self.bottom()))
        session.label = session.label.join(label)
        session.grants.add(grant_id)

    def release_allowed(self, output_id, recipient, recipient_id, purpose, now) -> bool:
        entry = self.outputs.get(output_id)
        rule = self.policy.recipients.get(recipient)
        if entry is None or rule is None:
            return False
        label = entry.label
        return (
            label.classes <= rule.classes
            and purpose in rule.purposes and purpose in label.purposes
            and rule.zone in label.zones
            and (rule.subject_scope == "any" or label.subjects <= {recipient_id})
            and all((s, purpose) not in self.withdrawn for s in label.subjects)
            and all(self.current(g, now) for g in entry.grants)
        )


def run_stateful(policy: DisclosurePolicy, *, sequences: int = 200, steps: int = 40,
                 seed: int = 20260913, enforce=ALL_CHECKS) -> StatefulReport:
    rng = random.Random(seed)
    fields = sorted(policy.field_classes)
    endpoints = sorted(policy.endpoints)
    recipients = sorted(policy.recipients)
    rules = sorted(policy.declassification)
    purposes = list(policy.purposes)
    operations: dict = {}
    released: dict = {"read": 0, "release": 0, "declassify": 0}
    disagreements: list = []
    total = 0

    for sequence in range(sequences):
        authority = GrantAuthority()
        declassifier = DeclassificationAuthority()
        records = {s: {f: f"SYNTH::{s}::{f}::{sequence}" for f in fields} for s in SUBJECTS}
        gate = DisclosureGate(policy, records, EvidenceLedger(TOKEN), TOKEN,
                              grant_keys=authority.trusted_keys,
                              declassification_keys=declassifier.trusted_keys,
                              consent=ConsentRegister(), enforce=enforce)
        ref = _Reference(policy)
        now = 1_000.0
        trace: list = []
        counter = 0

        for step in range(steps):
            total += 1
            op = rng.choice(OPERATIONS)
            operations[op] = operations.get(op, 0) + 1
            expected = actual = "n/a"

            if op == "issue" or not ref.grants:
                op = "issue"
                counter += 1
                chosen = rng.sample(fields, rng.randint(1, min(3, len(fields))))
                # Sometimes the clearance omits a class the fields need.
                classes = {policy.field_classes[f] for f in chosen}
                if rng.random() < 0.15 and len(classes) > 1:
                    classes.discard(sorted(classes)[0])
                grant = authority.issue(
                    grant_id=f"g{counter}", holder=rng.choice(AGENTS),
                    purpose=rng.choice(purposes),
                    subjects=rng.sample(SUBJECTS, rng.randint(1, 2)), fields=chosen,
                    classes=classes, issued_by=ISSUER, now=now,
                    ttl_seconds=rng.choice((30.0, 120.0, 600.0)),
                )
                ref.grants[grant.grant_id] = _Grant(grant)
                trace.append(f"issue {grant.grant_id} holder={grant.holder} "
                             f"purpose={grant.purpose} subjects={sorted(grant.subjects)} "
                             f"fields={sorted(grant.fields)}")
                continue

            if op == "revoke":
                gid = rng.choice(sorted(ref.grants))
                gate.revoke_grant(gid, by=ISSUER, reason="random")
                ref.grants[gid].revoked = True
                trace.append(f"revoke {gid}")
                continue
            if op == "withdraw":
                pair = (rng.choice(SUBJECTS), rng.choice(purposes))
                gate.withdraw_consent(*pair, recorded_by="privacy")
                ref.withdrawn.add(pair)
                trace.append(f"withdraw {pair}")
                continue
            if op == "restore":
                if ref.withdrawn:
                    pair = rng.choice(sorted(ref.withdrawn))
                    gate.consent.restore(*pair)
                    ref.withdrawn.discard(pair)
                    trace.append(f"restore {pair}")
                continue
            if op == "tick":
                now += rng.choice((10.0, 60.0, 200.0))
                trace.append(f"tick now={now}")
                continue

            if op == "read":
                agent = rng.choice(AGENTS)
                gid = rng.choice(sorted(ref.grants))
                grant = ref.grants[gid].grant
                honest = rng.random() < 0.6
                purpose = grant.purpose if honest else rng.choice(purposes)
                subjects = sorted(grant.subjects) if honest else rng.sample(SUBJECTS, rng.randint(1, 2))
                req_fields = sorted(grant.fields) if honest else rng.sample(
                    fields, rng.randint(1, min(3, len(fields))))
                endpoint = rng.choice(endpoints)
                session_id = f"s{rng.randint(1, 3)}"
                expected_ok = ref.read_allowed(agent, session_id, gid, purpose, subjects,
                                               req_fields, endpoint, now)
                try:
                    gate.assemble_context(requester=agent, session_id=session_id,
                                          grant=grant, purpose=purpose, subjects=subjects,
                                          fields=req_fields, model_endpoint=endpoint, now=now)
                    actual_ok = True
                except DisclosureDenied as denied:
                    actual_ok, actual = False, denied.code
                if expected_ok:
                    ref.apply_read(agent, session_id, gid, purpose, subjects, req_fields)
                    released["read"] += actual_ok
                expected = "allow" if expected_ok else "deny"
                actual = "allow" if actual_ok else f"deny:{actual}"
                trace.append(f"read {agent} {session_id} {gid} purpose={purpose} "
                             f"subjects={subjects} fields={req_fields} at {endpoint}: {actual}")

            elif op == "derive":
                live = [(sid, s) for sid, s in ref.sessions.items()]
                if not live:
                    continue
                session_id, session = rng.choice(sorted(live, key=lambda item: item[0]))
                output = gate.derive_output(requester=session.holder, session_id=session_id,
                                            content=f"summary of {session_id}",
                                            claimed_label=DataLabel.bottom(policy))
                ref.outputs[output.output_id] = _Output(output, session.label, session.holder,
                                                        frozenset(session.grants))
                expected = "label=session"
                actual = "label=session" if output.label == session.label else "label differs"
                trace.append(f"derive {output.output_id} from {session_id}: {actual}")

            elif op == "declassify":
                candidates = sorted(ref.outputs)
                if not candidates or not rules:
                    continue
                oid = rng.choice(candidates)
                entry = ref.outputs[oid]
                rule = policy.declassification[rng.choice(rules)]
                approval = declassifier.approve(entry.output, rule=rule.name, approver=REVIEWER,
                                                approver_role=rule.approval_role, now=now)
                expected_ok = (entry.label.classes <= (rule.from_classes | {rule.to_class})
                               and bool(entry.label.purposes & rule.purposes))
                try:
                    lowered = gate.declassify(entry.output, rule=rule.name, approval=approval,
                                              now=now)
                    actual_ok = True
                except DisclosureDenied as denied:
                    actual_ok, actual = False, denied.code
                    lowered = None
                if expected_ok and lowered is not None:
                    released["declassify"] += 1
                    label = DataLabel(
                        frozenset({rule.to_class}),
                        frozenset() if rule.removes_subject_identity else entry.label.subjects,
                        entry.label.purposes & rule.purposes,
                        policy.class_zones[rule.to_class],
                    )
                    grants = frozenset() if rule.removes_subject_identity else entry.grants
                    ref.outputs[lowered.output_id] = _Output(lowered, label, entry.holder, grants)
                    if lowered.label != label:
                        disagreements.append(Disagreement(sequence, step, op, "declassified label",
                                                          "label differs", list(trace)))
                expected = "allow" if expected_ok else "deny"
                actual = "allow" if actual_ok else f"deny:{actual}"
                trace.append(f"declassify {oid} by {rule.name}: {actual}")

            elif op == "release":
                candidates = sorted(ref.outputs)
                if not candidates:
                    continue
                oid = rng.choice(candidates)
                entry = ref.outputs[oid]
                recipient = rng.choice(recipients)
                purpose = rng.choice(purposes)
                recipient_id = rng.choice(SUBJECTS)
                expected_ok = ref.release_allowed(oid, recipient, recipient_id, purpose, now)
                try:
                    gate.release(entry.output, recipient=recipient, recipient_id=recipient_id,
                                 purpose=purpose, now=now)
                    actual_ok = True
                except DisclosureDenied as denied:
                    actual_ok, actual = False, denied.code
                released["release"] += expected_ok and actual_ok
                expected = "allow" if expected_ok else "deny"
                actual = "allow" if actual_ok else f"deny:{actual}"
                trace.append(f"release {oid} to {recipient} for {purpose} at now={now}: {actual}")

            if expected.split(":")[0] != actual.split(":")[0] and expected != "n/a":
                disagreements.append(Disagreement(sequence, step, op, expected, actual, list(trace)))

    return StatefulReport(sequences, total, operations, released, disagreements)


__all__ = ["Disagreement", "StatefulReport", "run_stateful"]
