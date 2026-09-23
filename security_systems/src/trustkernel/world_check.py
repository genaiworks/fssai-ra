"""Static validation of a world against its own pack, before any attack runs.

A falsifier is only as good as its fixture. Bind the "unnamed" field to a different
class from the "routine" one and F22 is stopped by class clearance, so the
``minimum_necessary`` row reads load-bearing for the wrong reason, or not at all.
Point the local endpoint at a manifest that does not allow ``other_purpose`` and F06
is stopped by attestation instead of purpose binding. The attacks would still
"hold", and the ablation table would quietly measure the wrong control.

:func:`check_world` catches every such miswiring statically. It never mutates the
world, it reports every finding at once, and each finding names the key to fix.
``trustkernel check`` runs it, and ``tests/test_world_check.py`` runs it on every
world that ships.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .kernel.pack_floor import EXTERNAL_ZONES, PackRejected, check_pack, load_governed_pack, read_pack
from .kernel.privacy_vault import _DETECTORS as CONTACT_PATTERNS
from .world import WorldSpec, WorldSpecError

MARKER_MIN_LENGTH = 6


@dataclass(frozen=True)
class WorldFinding:
    code: str
    where: str
    detail: str

    def to_dict(self) -> dict:
        return {"code": self.code, "where": self.where, "detail": self.detail}


def check_world(world: str | WorldSpec) -> list[WorldFinding]:
    """Every way ``world`` is miswired. Empty means the attack suites measure what they claim."""
    try:
        spec = world if isinstance(world, WorldSpec) else WorldSpec.load(world)
    except WorldSpecError as exc:
        return [WorldFinding("WORLD_UNLOADABLE", "world.yaml", str(exc))]
    findings: list[WorldFinding] = []
    add = lambda code, where, detail: findings.append(WorldFinding(code, where, detail))  # noqa: E731

    try:
        pack = load_governed_pack(spec.pack_path)
    except PackRejected as exc:
        for f in exc.findings:
            add("WORLD_PACK_BELOW_FLOOR", f"pack.{f.where}", f"{f.code}: {f.detail}")
        return findings
    except (OSError, ValueError) as exc:
        return [WorldFinding("WORLD_PACK_UNLOADABLE", "pack", str(exc))]

    policy = pack.profile.disclosure
    raw_disclosure: dict[str, Any] = pack.raw["disclosure"]
    classes, recipients = policy.field_classes, raw_disclosure["recipients"]
    manifests, endpoints = pack.model_manifests, policy.endpoints
    transitions = {(t.operation, t.from_status, t.to_status): t for t in pack.profile.transitions}
    raw = spec.raw

    def get(*path: str, where: str | None = None) -> Any:
        try:
            return spec.fixture(*path)
        except WorldSpecError:
            add("WORLD_KEY_MISSING", where or "scenario." + ".".join(path), "required by the attack suites")
            return None

    # -- the cast ---------------------------------------------------------------------
    for key in ("subjects", "principals", "agents", "resources", "source_keys", "injection_patterns",
                "executor_audience", "scenario", "delegation_suite", "malicious_pack"):
        if key not in raw:
            add("WORLD_KEY_MISSING", key, "every world declares this")
    if findings:
        return findings

    for subject, row in spec.subjects.items():
        missing, extra = sorted(set(classes) - set(row)), sorted(set(row) - set(classes))
        if missing:
            add("WORLD_SUBJECT_INCOMPLETE", f"subjects.{subject}", f"no value for pack fields {missing}")
        if extra:
            add("WORLD_SUBJECT_UNDECLARED_FIELD", f"subjects.{subject}", f"{extra} are not pack fields")
    if len(spec.subjects) < 2:
        add("WORLD_TOO_FEW_SUBJECTS", "subjects", "subject-scope attacks need at least two subjects")

    values = [(s, f, str(v)) for s, row in spec.subjects.items() for f, v in row.items()]
    for subject, name, value in values:
        where = f"subjects.{subject}.{name}"
        if len(value) < MARKER_MIN_LENGTH:
            add("WORLD_MARKER_TOO_SHORT", where, f"{value!r}: falsifiers detect leaks by substring")
        clashes = [f"{s}.{f}" for s, f, v in values if (s, f) != (subject, name) and value in v]
        if clashes:
            add("WORLD_MARKER_AMBIGUOUS", where, f"{value!r} also appears inside {clashes}")
        if name not in pack.identity_fields:
            for kind, pattern in CONTACT_PATTERNS:
                if pattern.search(value):
                    add("WORLD_MARKER_LOOKS_LIKE_CONTACT", where,
                        f"{value!r} matches the {kind} detector and would be tokenized or refused")

    roles_needed = {t.approval_role for t in transitions.values()}
    roles_needed |= {r["approval_role"] for r in raw_disclosure.get("declassification") or []}
    if raw_disclosure.get("break_glass"):
        roles_needed.add(raw_disclosure["break_glass"]["review_role"])
    for role in sorted(roles_needed - set(spec.principals.values())):
        add("WORLD_ROLE_UNSTAFFED", "principals", f"no principal holds {role!r}; that transition can never run")

    states = {s for (_, a, b) in transitions for s in (a, b)}
    for resource, status in spec.resources.items():
        if status not in states:
            add("WORLD_RESOURCE_STATE_UNKNOWN", f"resources.{resource}", f"{status!r} appears in no transition")
    for source in spec.source_keys:
        if not re.fullmatch(r"[a-z0-9-]+", source):
            add("WORLD_SOURCE_NAME", f"source_keys.{source}", "use lowercase letters, digits, and hyphens")

    index = raw.get("vector_index") or {}
    if index and index.get("field") not in classes:
        add("WORLD_FIELD_UNKNOWN", "vector_index.field", f"{index.get('field')!r} is not a pack field")

    # -- the scenario roles -------------------------------------------------------------
    for key in ("agent", "sub_agent", "rogue"):
        name = get(key)
        if name is not None and name not in spec.agents:
            add("WORLD_AGENT_UNKNOWN", f"scenario.{key}", f"{name!r} is not in agents")
    for key in ("approver", "data_officer"):
        name = get(key)
        if name is not None and name not in spec.principals:
            add("WORLD_PRINCIPAL_UNKNOWN", f"scenario.{key}", f"{name!r} is not in principals")
    subject, purpose, other = get("subject"), get("purpose"), get("other_purpose")
    if subject is not None and subject not in spec.subjects:
        add("WORLD_SUBJECT_UNKNOWN", "scenario.subject", f"{subject!r} is not a subject")
    for key, value in (("purpose", purpose), ("other_purpose", other)):
        if value is not None and value not in policy.purposes:
            add("WORLD_PURPOSE_UNKNOWN", f"scenario.{key}", f"{value!r} is not a pack purpose")
    if purpose is not None and purpose == other:
        add("WORLD_PURPOSES_IDENTICAL", "scenario.other_purpose", "purpose violation needs a different purpose")

    fields = {}
    for role in ("routine", "routine_2", "unnamed", "sensitive", "restricted", "identity"):
        name = get("fields", role)
        if name is not None and name not in classes:
            add("WORLD_FIELD_UNKNOWN", f"scenario.fields.{role}", f"{name!r} is not a pack field")
        elif name is not None:
            fields[role] = name
    cls = {role: classes[name] for role, name in fields.items()}
    if len(set(fields.values())) != len(fields):
        add("WORLD_FIELD_ROLES_OVERLAP", "scenario.fields", "each role needs its own field")
    if "unnamed" in cls and cls.get("routine") != cls["unnamed"]:
        add("WORLD_UNNAMED_CLASS", "scenario.fields.unnamed",
            f"must share routine's class {cls.get('routine')!r}, or F22 measures class clearance instead of "
            "minimum_necessary")
    if "identity" in fields and fields["identity"] not in pack.identity_fields:
        add("WORLD_IDENTITY_NOT_TOKENIZED", "scenario.fields.identity", "must be one of the pack's identity_fields")
    if "sensitive" in cls and cls["sensitive"] == cls.get("routine"):
        add("WORLD_SENSITIVE_CLASS", "scenario.fields.sensitive", "must be a different class from routine")

    uncleared, external = get("recipients", "uncleared"), get("recipients", "external")
    for key, name in (("uncleared", uncleared), ("external", external)):
        if name is not None and name not in recipients:
            add("WORLD_RECIPIENT_UNKNOWN", f"scenario.recipients.{key}", f"{name!r} is not a pack recipient")
    if uncleared in recipients:
        rule = recipients[uncleared]
        if cls.get("routine") not in rule["classes"] or purpose not in rule["purposes"]:
            add("WORLD_UNCLEARED_TOO_NARROW", "scenario.recipients.uncleared",
                "must be cleared for the routine class and purpose, so only the tested control refuses")
        if cls.get("sensitive") in rule["classes"]:
            add("WORLD_UNCLEARED_TOO_WIDE", "scenario.recipients.uncleared",
                f"is cleared for {cls['sensitive']!r}; the release attacks would succeed legitimately")
        if cls.get("identity") in rule["classes"]:
            add("WORLD_UNCLEARED_TOO_WIDE", "scenario.recipients.uncleared",
                "is cleared for identity; token reversal would succeed legitimately")
    if external in recipients and recipients[external]["zone"] not in EXTERNAL_ZONES:
        add("WORLD_EXTERNAL_NOT_EXTERNAL", "scenario.recipients.external", "must sit in an external zone")

    local, weaker, public = get("endpoints", "local"), get("endpoints", "weaker"), get("endpoints", "public")
    if local is not None:
        manifest = manifests.get(local)
        if manifest is None:
            add("WORLD_ENDPOINT_UNATTESTED", "scenario.endpoints.local", f"{local!r} has no model manifest")
        else:
            needed = {cls[r] for r in ("routine", "sensitive", "identity", "restricted") if r in cls}
            gaps = sorted(needed - set(manifest["allowed_classes"]))
            if gaps:
                add("WORLD_LOCAL_TOO_NARROW", f"model_manifests.{local}.allowed_classes",
                    f"missing {gaps}; attestation would stop attacks meant for other controls")
            wanted = {purpose, other, get("action", "attest_purpose")} - {None}
            missing = sorted(wanted - set(manifest["allowed_purposes"]))
            if missing:
                add("WORLD_LOCAL_TOO_NARROW", f"model_manifests.{local}.allowed_purposes",
                    f"missing {missing}; F06 would be stopped by attestation, not purpose binding")
    if weaker is not None and "sensitive" in cls:
        zone = endpoints.get(weaker)
        if zone is None or weaker not in manifests:
            add("WORLD_ENDPOINT_UNATTESTED", "scenario.endpoints.weaker", f"{weaker!r} needs a manifest")
        else:
            if zone in policy.class_zones.get(cls["sensitive"], ()):
                add("WORLD_WEAKER_NOT_WEAKER", "scenario.endpoints.weaker",
                    f"zone {zone!r} may already hold {cls['sensitive']!r}; residency cannot be tested")
            if cls["sensitive"] in manifests[weaker]["allowed_classes"]:
                add("WORLD_WEAKER_NOT_WEAKER", "scenario.endpoints.weaker",
                    f"its manifest allows {cls['sensitive']!r}; attestation cannot be tested")
    if public is not None and endpoints.get(public) not in EXTERNAL_ZONES:
        add("WORLD_PUBLIC_NOT_EXTERNAL", "scenario.endpoints.public", "must be declared in an external zone")
    if public is not None and public not in (raw.get("unattested_runtimes") or {}) and public not in manifests:
        add("WORLD_ENDPOINT_UNSERVED", "unattested_runtimes", f"{public!r} is declared but serves nothing")

    action = get("action") or {}
    op = action.get("operation")
    legal = lambda a, b: (op, a, b) in transitions  # noqa: E731
    if op is not None and not any(t[0] == op for t in transitions):
        add("WORLD_OPERATION_UNKNOWN", "scenario.action.operation", f"{op!r} has no transition")
    elif op is not None:
        approver_role = spec.principals.get(get("approver"))
        if any(t.approval_role != approver_role for k, t in transitions.items() if k[0] == op):
            add("WORLD_APPROVER_ROLE", "scenario.approver", f"must hold the approval role for every {op} transition")
        if not all(t.consequential for k, t in transitions.items() if k[0] == op):
            add("WORLD_OPERATION_NOT_CONSEQUENTIAL", "scenario.action.operation", "attack a consequential operation")
        for key in ("own", "victim", "borrowed"):
            item = action.get(key) or {}
            resource = item.get("resource")
            if resource not in spec.resources:
                add("WORLD_RESOURCE_UNKNOWN", f"scenario.action.{key}.resource", f"{resource!r} is not a resource")
            elif not legal(spec.resources[resource], item.get("to")):
                add("WORLD_TRANSITION_ILLEGAL", f"scenario.action.{key}",
                    f"{spec.resources[resource]} → {item.get('to')} is not a declared {op} transition")
        own = action.get("own") or {}
        if own.get("to") and not legal(own["to"], own.get("replay_to")):
            add("WORLD_TRANSITION_ILLEGAL", "scenario.action.own.replay_to",
                "must be legal from own.to, or the replay attack is stopped by the state machine")
        if action.get("victim", {}).get("resource") == own.get("resource"):
            add("WORLD_VICTIM_IS_OWN", "scenario.action.victim", "the victim must be a different resource")
        for resource in action.get("targets") or []:
            if resource not in spec.resources:
                add("WORLD_RESOURCE_UNKNOWN", "scenario.action.targets", f"{resource!r} is not a resource")
        if action.get("attest_field") not in classes:
            add("WORLD_FIELD_UNKNOWN", "scenario.action.attest_field", "must be a pack field")

    boundary = get("boundary") or {}
    if boundary.get("source") not in spec.source_keys:
        add("WORLD_SOURCE_UNKNOWN", "scenario.boundary.source", "must be a trusted source_keys entry")
    if boundary.get("injection") and not spec.injection.search(boundary["injection"]):
        add("WORLD_INJECTION_UNMARKED", "scenario.boundary.injection", "matches no injection pattern")

    probe = get("malicious_pack_probe") or {}
    if not spec.malicious_pack_path.is_file():
        add("WORLD_MALICIOUS_PACK_MISSING", "malicious_pack.path", str(spec.malicious_pack_path))
    else:
        bad = read_pack(spec.malicious_pack_path)
        if not check_pack(bad):
            add("WORLD_MALICIOUS_PACK_ACCEPTED", "malicious_pack.path", "the floor accepts it; it tests nothing")
        hands_over = any(t.get("operation") == probe.get("operation") and t.get("from_status") == probe.get("from")
                         and t.get("to_status") == probe.get("to") and t.get("approval_role") == "model"
                         for t in bad.get("transitions") or [])
        if not hands_over:
            add("WORLD_PROBE_UNMATCHED", "scenario.malicious_pack_probe",
                "the malicious pack must hand exactly this transition to role 'model'")

    agent = get("malicious_agent") or {}
    for name in agent.get("fields") or []:
        if name not in classes:
            add("WORLD_FIELD_UNKNOWN", "scenario.malicious_agent.fields", f"{name!r} is not a pack field")
    attack = get("attack") or {}
    for name in [*attack.get("fields", []), *attack.get("extra_fields", [])]:
        if name not in classes:
            add("WORLD_FIELD_UNKNOWN", "scenario.attack.fields", f"{name!r} is not a pack field")
    if not attack.get("goal"):
        add("WORLD_KEY_MISSING", "scenario.attack.goal", "the live red-team prompt needs a goal")

    suite = raw.get("delegation_suite") or {}
    for key in ("root_principal", "owner", "tools", "resources", "benign_purpose"):
        if key not in suite:
            add("WORLD_KEY_MISSING", f"delegation_suite.{key}", "the delegation comparison needs it")
    return findings


__all__ = ["WorldFinding", "check_world"]
