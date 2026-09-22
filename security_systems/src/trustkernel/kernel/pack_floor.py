"""The kernel floor: what no domain pack may weaken.

Domain packs are how the architecture transfers to a new sector, and that makes
them an attack surface. A pack is configuration written by people with commit
access, reviewed by people who read YAML quickly. Every weakening below looks like
ordinary configuration: a production deploy marked non-consequential, a role named
``model``, an external zone added to a class list, a review policy of
``auto_approve``, a key called ``skip_evidence`` that the loader silently ignores.

The profile loader checks that a pack is *well formed*. This module checks that it
is *not weaker than the kernel*, and it reports every violation at once rather than
the first, so a reviewer sees the whole attempt. :func:`check_pack` never mutates
anything; :func:`load_governed_pack` refuses to return a pack with any finding.

The floor is deliberately small. It does not judge whether a pack's policy is
wise, only whether it removes a guarantee the architecture's safety case relies on:

* consequential authority is reviewed by a declared human role, never a model;
* every consequential capability has a complete seven-field control contract whose
  failure test exists and whose failure response does not fail open;
* identity, health, support, financial, credential, secret, and PII classes never reach
  an external zone;
* emergency access, delegation, and review load are bounded, and review overload
  never becomes approval;
* no pack key can switch a kernel check off, and no unknown key is silently ignored.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .profiles import ApplicationProfile, ProfileError

ALLOWED_TOP_LEVEL = frozenset({
    "profile_id", "version", "title", "resource_name", "owner", "manual_fallback",
    "governance", "disclosure", "transitions", "identity_fields", "controls",
    "model_manifests", "review", "delegation",
})
CONTROL_FIELDS = ("protected_asset", "permitted_operation", "enforcement_point", "owner",
                  "failure_test", "evidence_artifact", "failure_response")
MEDIATORS = frozenset({"execution_mediator", "context_gate", "release_gate",
                       "delegation_verifier", "model_registry", "review_queue",
                       "evidence_notary", "key_custody"})
#: Keys whose only plausible purpose is to switch a kernel guarantee off.
WEAKENING_KEYS = frozenset({
    "auto_approve", "skip_evidence", "disable_checks", "enforce", "bypass_executor",
    "unrestricted_writes", "allow_model_execution", "disable_review", "consent",
    "skip_consent", "trust_model", "allow_self_approval", "disable_tokenization",
})
NON_HUMAN_ROLES = frozenset({"model", "agent", "ai", "assistant", "system", "automation",
                             "*", "any", "llm", "bot"})
EXTERNAL_ZONES = frozenset({"external", "public", "internet", "public-cloud"})
#: A data class whose name carries any of these markers may never reach an external zone.
#: Adding a marker only ever protects more classes, so no existing pack is weakened by it.
PROTECTED_CLASS_MARKERS = ("identity", "health", "support", "financial", "restricted",
                           "credential", "secret", "pii")
#: The repository whose ``tests/`` a pack's ``failure_test`` references must resolve in.
REPO_ROOT = Path(__file__).resolve().parents[3]
FAIL_OPEN_WORDS = re.compile(r"\b(allow|approve|continue|proceed|ignore)\b", re.IGNORECASE)
FAIL_SAFE_WORDS = re.compile(r"\b(deny|refuse|reject|defer|freeze|escalate|keep|report|release tokens only)\b",
                             re.IGNORECASE)
REVIEW_OVERLOAD_POLICIES = frozenset({"defer_to_manual", "escalate", "queue"})
DATA_CAPABILITIES = ("read_protected_context", "release_labelled_output", "restore_identity",
                     "delegate_authority", "erase_subject")
KERNEL_MAX_DELEGATION_DEPTH = 4
KERNEL_MAX_BREAK_GLASS_SECONDS = 86_400
KERNEL_MAX_MODEL_APPROVAL_DAYS = 366


class FloorCode:
    UNKNOWN_KEY = "PACK_UNKNOWN_KEY"
    WEAKENING_KEY = "PACK_ATTEMPTS_TO_DISABLE_KERNEL"
    STRUCTURE = "PACK_STRUCTURALLY_INVALID"
    NON_HUMAN_APPROVER = "PACK_NON_HUMAN_APPROVER"
    CONSEQUENCE_DOWNGRADED = "PACK_CONSEQUENCE_DOWNGRADED"
    CONTRACT_MISSING = "PACK_CONTROL_CONTRACT_MISSING"
    CONTRACT_INCOMPLETE = "PACK_CONTROL_CONTRACT_INCOMPLETE"
    ENFORCEMENT_UNKNOWN = "PACK_ENFORCEMENT_POINT_UNKNOWN"
    FAILURE_TEST_MISSING = "PACK_FAILURE_TEST_MISSING"
    FAILS_OPEN = "PACK_FAILURE_RESPONSE_FAILS_OPEN"
    PROTECTED_CLASS_EXTERNAL = "PACK_PROTECTED_CLASS_IN_EXTERNAL_ZONE"
    EXTERNAL_RECIPIENT = "PACK_EXTERNAL_RECIPIENT_RECEIVES_PROTECTED_DATA"
    BREAK_GLASS_UNBOUNDED = "PACK_BREAK_GLASS_UNBOUNDED"
    REVIEW_FAILS_OPEN = "PACK_REVIEW_OVERLOAD_FAILS_OPEN"
    DELEGATION_UNBOUNDED = "PACK_DELEGATION_UNBOUNDED"
    MODEL_APPROVAL_UNBOUNDED = "PACK_MODEL_APPROVAL_UNBOUNDED"
    FALLBACK_MISSING = "PACK_MANUAL_FALLBACK_MISSING"


@dataclass(frozen=True)
class FloorFinding:
    code: str
    where: str
    detail: str

    def to_dict(self) -> dict:
        return {"code": self.code, "where": self.where, "detail": self.detail}


class PackRejected(ValueError):
    def __init__(self, findings: list[FloorFinding]) -> None:
        super().__init__("domain pack weakens the kernel: " +
                         "; ".join(f"{f.code} at {f.where}" for f in findings))
        self.findings = findings


def _protected(data_class: str) -> bool:
    return any(marker in data_class for marker in PROTECTED_CLASS_MARKERS)


def _walk_keys(value: Any, path: str = "") -> Iterable[tuple[str, str]]:
    if isinstance(value, dict):
        for key, child in value.items():
            where = f"{path}.{key}" if path else str(key)
            yield str(key), where
            yield from _walk_keys(child, where)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_keys(child, f"{path}[{index}]")


def _test_exists(reference: str, root: Path) -> bool:
    path, _, name = str(reference).partition("::")
    target = root / path
    if not name or not target.is_file():
        return False
    return re.search(rf"^def {re.escape(name)}\(", target.read_text(encoding="utf-8"),
                     re.MULTILINE) is not None


def check_pack(raw: Any, *, repo_root: Path | None = None) -> list[FloorFinding]:
    """Every way ``raw`` weakens the kernel. Empty means the pack is at or above the floor."""
    root = repo_root or REPO_ROOT
    findings: list[FloorFinding] = []
    add = lambda code, where, detail: findings.append(FloorFinding(code, where, detail))  # noqa: E731

    if not isinstance(raw, dict):
        return [FloorFinding(FloorCode.STRUCTURE, "pack", "a pack must be a mapping")]

    for key in sorted(set(raw) - ALLOWED_TOP_LEVEL):
        add(FloorCode.UNKNOWN_KEY, key,
            "the kernel does not read this key; a pack author may believe it does something")
    for key, where in _walk_keys(raw):
        if key in WEAKENING_KEYS:
            add(FloorCode.WEAKENING_KEY, where, f"{key!r} would switch a kernel guarantee off")

    try:
        ApplicationProfile.from_dict(raw)
    except ProfileError as exc:
        add(FloorCode.STRUCTURE, "profile", str(exc))

    fallback = raw.get("manual_fallback")
    if not isinstance(fallback, str) or len(fallback.split()) < 4 or fallback.strip().lower() in {"none", "none needed", "n/a"}:
        add(FloorCode.FALLBACK_MISSING, "manual_fallback",
            "failure must route to a staffed path; a missing fallback turns refusal into outage or override")

    transitions = raw.get("transitions") or []
    controls = raw.get("controls") or {}
    consequential_ops: set[str] = set()
    for index, item in enumerate(transitions if isinstance(transitions, list) else []):
        if not isinstance(item, dict):
            continue
        role = str(item.get("approval_role", "")).strip().lower()
        where = f"transitions[{index}]"
        if role in NON_HUMAN_ROLES:
            add(FloorCode.NON_HUMAN_APPROVER, where,
                f"{item.get('operation')} is approved by {role!r}; authority must come from a declared human role")
        operation = str(item.get("operation", ""))
        if item.get("consequential") is True:
            consequential_ops.add(operation)
        elif operation in controls:
            add(FloorCode.CONSEQUENCE_DOWNGRADED, where,
                f"{operation} has a control contract but is marked non-consequential, which removes review")
        if str(item.get("from_status")) in {"any", "*"} or str(item.get("to_status")) in {"any", "*"}:
            add(FloorCode.STRUCTURE, where, "wildcard states grant unrestricted writes")

    required = set(consequential_ops)
    if raw.get("disclosure") is not None:
        required |= set(DATA_CAPABILITIES)
    declared = set(controls) if isinstance(controls, dict) else set()
    for operation in sorted(required | declared):
        contract = controls.get(operation) if isinstance(controls, dict) else None
        where = f"controls.{operation}"
        if not isinstance(contract, dict):
            add(FloorCode.CONTRACT_MISSING, where,
                "a consequential capability without a seven-field contract is an unresolved governance decision")
            continue
        for name in CONTROL_FIELDS:
            if not isinstance(contract.get(name), str) or not contract[name].strip():
                add(FloorCode.CONTRACT_INCOMPLETE, f"{where}.{name}", f"{name} is empty")
        point = contract.get("enforcement_point")
        if isinstance(point, str) and point.strip() and point not in MEDIATORS:
            add(FloorCode.ENFORCEMENT_UNKNOWN, f"{where}.enforcement_point",
                f"{point!r} is not an independent mediator the kernel provides")
        test = contract.get("failure_test")
        if isinstance(test, str) and test.strip() and not _test_exists(test, root):
            add(FloorCode.FAILURE_TEST_MISSING, f"{where}.failure_test",
                f"{test} does not exist, so the failure test never runs")
        response = contract.get("failure_response")
        if isinstance(response, str) and response.strip() and \
                (FAIL_OPEN_WORDS.search(response) and not FAIL_SAFE_WORDS.search(response)):
            add(FloorCode.FAILS_OPEN, f"{where}.failure_response",
                f"{response!r} continues on failure")

    disclosure = raw.get("disclosure") if isinstance(raw.get("disclosure"), dict) else {}
    for cls, zones in (disclosure.get("class_zones") or {}).items():
        external = sorted(set(zones or ()) & EXTERNAL_ZONES)
        if _protected(str(cls)) and external:
            add(FloorCode.PROTECTED_CLASS_EXTERNAL, f"disclosure.class_zones.{cls}",
                f"{cls} may be processed in {', '.join(external)}")
    for name, rule in (disclosure.get("recipients") or {}).items():
        if isinstance(rule, dict) and rule.get("zone") in EXTERNAL_ZONES:
            leaked = sorted(c for c in rule.get("classes") or () if _protected(str(c)))
            if leaked:
                add(FloorCode.EXTERNAL_RECIPIENT, f"disclosure.recipients.{name}",
                    f"external recipient receives {', '.join(leaked)}")
    glass = disclosure.get("break_glass")
    if isinstance(glass, dict):
        if not isinstance(glass.get("max_ttl_seconds"), (int, float)) or \
                glass["max_ttl_seconds"] > KERNEL_MAX_BREAK_GLASS_SECONDS:
            add(FloorCode.BREAK_GLASS_UNBOUNDED, "disclosure.break_glass.max_ttl_seconds",
                f"emergency access may not exceed {KERNEL_MAX_BREAK_GLASS_SECONDS} seconds")
        if not isinstance(glass.get("max_unreviewed_per_holder"), int) or \
                glass["max_unreviewed_per_holder"] > 3:
            add(FloorCode.BREAK_GLASS_UNBOUNDED, "disclosure.break_glass.max_unreviewed_per_holder",
                "more than three unreviewed emergency accesses is not emergency access")
        if str(glass.get("review_role", "")).lower() in NON_HUMAN_ROLES:
            add(FloorCode.NON_HUMAN_APPROVER, "disclosure.break_glass.review_role",
                "emergency access must be reviewed by a human role")

    review = raw.get("review")
    if not isinstance(review, dict):
        if consequential_ops:
            add(FloorCode.REVIEW_FAILS_OPEN, "review",
                "consequential capabilities require declared review capacity and an overload policy")
    else:
        if review.get("overload_policy") not in REVIEW_OVERLOAD_POLICIES:
            add(FloorCode.REVIEW_FAILS_OPEN, "review.overload_policy",
                f"{review.get('overload_policy')!r}: overload must defer, escalate, or queue, never approve")
        for key in ("capacity_per_window", "queue_limit", "timeout_seconds", "window_seconds"):
            if not isinstance(review.get(key), int) or review[key] <= 0:
                add(FloorCode.REVIEW_FAILS_OPEN, f"review.{key}", f"{key} must be a positive integer")
        if not str(review.get("escalation_role", "")).strip() or \
                str(review.get("escalation_role")).lower() in NON_HUMAN_ROLES:
            add(FloorCode.REVIEW_FAILS_OPEN, "review.escalation_role", "escalation needs a human role")

    delegation = raw.get("delegation")
    if isinstance(delegation, dict):
        depth = delegation.get("max_depth")
        if not isinstance(depth, int) or depth < 1 or depth > KERNEL_MAX_DELEGATION_DEPTH:
            add(FloorCode.DELEGATION_UNBOUNDED, "delegation.max_depth",
                f"depth must be between 1 and {KERNEL_MAX_DELEGATION_DEPTH}")
        if delegation.get("allow_machine_delegated_consequence") is not False:
            add(FloorCode.DELEGATION_UNBOUNDED, "delegation.allow_machine_delegated_consequence",
                "a machine may not pass consequential authority onward")

    zones = disclosure.get("model_endpoints") or {}
    for endpoint, manifest in (raw.get("model_manifests") or {}).items():
        where = f"model_manifests.{endpoint}"
        if not isinstance(manifest, dict):
            add(FloorCode.STRUCTURE, where, "manifest must be a mapping")
            continue
        days = manifest.get("approval_days")
        if not isinstance(days, int) or days <= 0 or days > KERNEL_MAX_MODEL_APPROVAL_DAYS:
            add(FloorCode.MODEL_APPROVAL_UNBOUNDED, f"{where}.approval_days",
                f"model approval must expire within {KERNEL_MAX_MODEL_APPROVAL_DAYS} days")
        if zones.get(endpoint) in EXTERNAL_ZONES:
            leaked = sorted(c for c in manifest.get("allowed_classes") or () if _protected(str(c)))
            if leaked:
                add(FloorCode.PROTECTED_CLASS_EXTERNAL, f"{where}.allowed_classes",
                    f"external model approved for {', '.join(leaked)}")
        if "execute_actions" in (manifest.get("capabilities") or ()):
            add(FloorCode.WEAKENING_KEY, f"{where}.capabilities",
                "no model may hold an execution capability; models propose")
    return findings


@dataclass(frozen=True)
class GovernedPack:
    raw: dict
    profile: ApplicationProfile
    path: str = ""

    @property
    def identity_fields(self) -> dict[str, str]:
        return dict(self.raw.get("identity_fields") or {})

    @property
    def controls(self) -> dict[str, dict]:
        return dict(self.raw.get("controls") or {})

    @property
    def model_manifests(self) -> dict[str, dict]:
        return dict(self.raw.get("model_manifests") or {})

    @property
    def review(self) -> dict:
        return dict(self.raw.get("review") or {})

    @property
    def delegation(self) -> dict:
        return dict(self.raw.get("delegation") or {})


def read_pack(path: str | Path) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def load_governed_pack(path: str | Path, *, floor: bool = True,
                       repo_root: Path | None = None) -> GovernedPack:
    """Load a pack only if it is at or above the kernel floor.

    ``floor=False`` exists for one purpose: the ablation that shows what a
    malicious pack does when nothing checks it. It is never used by a deployment path.
    """
    raw = read_pack(path)
    if floor:
        findings = check_pack(raw, repo_root=repo_root)
        if findings:
            raise PackRejected(findings)
    return GovernedPack(raw, ApplicationProfile.from_dict(raw), str(path))


__all__ = [
    "CONTROL_FIELDS", "FloorCode", "FloorFinding", "GovernedPack", "MEDIATORS", "PackRejected",
    "REPO_ROOT",
    "check_pack", "load_governed_pack", "read_pack",
]
