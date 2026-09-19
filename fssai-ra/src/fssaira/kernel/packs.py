"""Domain packs: one declarative manifest per sector, held to the kernel floor.

A sector enters the architecture through a **pack manifest**
(``packs/<sector>.pack.yaml``). The manifest is what a policy leader reads: the
purposes, data classes and where each may be processed, recipients, transitions and
their approvers, declassification rules, emergency access, fallback, the tests that
falsify it, and honest limits. It does **not** carry enforcement configuration of its
own. It *references* the sources the runtime already enforces (``profiles/*.yaml``,
optionally a governed-learning pack) and the kernel's seven-field capability contracts.

Loading a manifest therefore proves three things, and fails closed on each:

1. **Schema.** Unknown keys and empty required fields are open governance decisions.
   Every test locator resolves to an exact pytest node; every capability id resolves
   to a loaded contract.
2. **No drift.** Every declaration in the manifest agrees exactly with what the
   referenced sources enforce, in both directions. A manifest can never claim a
   purpose, zone, recipient, approver or emergency bound the runtime does not enforce,
   and it can never omit one the runtime does.
3. **The floor.** Every source passes :func:`fssaira.pack_floor.check_pack` (rules that
   only make sense for the governed-learning format are recorded as exemptions for
   action profiles, never silently skipped), plus sector-neutral rules that apply to
   every pack: kernel capabilities are bound, only identity-removed declassified classes
   touch a public zone, declassification and emergency review are performed by an
   independent role that holds a consequential transition.

:func:`evaluate_pack` then runs the existing, unchanged evaluations for the pack and
returns per-profile denominators whose unit is named. Unlike units are never pooled.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ..evaluation import EvaluationRunner
from ..pack_floor import (
    EXTERNAL_ZONES,
    FloorCode,
    FloorFinding,
    GovernedPack,
    check_pack,
)
from ..profiles import ApplicationProfile, ProfileError
from ..verification import verify_profile
from .contract import (
    CapabilityContract,
    ContractError,
    load_capability_contracts,
    resolve_test_locator,
)

SCHEMA_VERSION = "1.0"
PLACEHOLDER_MARKER = "REPLACE_ME"

#: Capabilities every pack must bind: exact action, requester is never approver,
#: single-use approval, and tamper-evident evidence.
KERNEL_CAPABILITIES: tuple[str, ...] = ("CAP-ACT-1", "CAP-ACT-2", "CAP-ACT-3", "CAP-EVI-1")
#: Additionally required when any source declares a disclosure policy.
DISCLOSURE_CAPABILITIES: tuple[str, ...] = ("CAP-DIS-1", "CAP-DIS-2")

_TOP_LEVEL = frozenset({
    "schema_version", "sector", "title", "sources", "capabilities", "purposes",
    "data_classes", "recipients", "transitions", "declassification", "emergency_access",
    "fallback", "tests", "limits",
})
_REQUIRED = tuple(sorted(_TOP_LEVEL))
_SOURCE_KEYS = frozenset({"profiles", "governed_learning_pack"})
_RECIPIENT_KEYS = frozenset({"classes", "purposes", "zone", "subject_scope"})
_TRANSITION_KEYS = frozenset({"approver_roles", "consequential"})
_DECLASSIFICATION_KEYS = frozenset({"from_classes", "to_class", "purposes", "approval_role",
                                    "removes_subject_identity"})
_EMERGENCY_KEYS = frozenset({"purposes", "max_ttl_seconds", "max_unreviewed_per_holder", "review_role"})
#: pack_floor rules written for the governed-learning format that an action profile
#: cannot satisfy by construction, and what stands in for them in a manifest.
_PROFILE_EXEMPTIONS = {
    FloorCode.CONTRACT_MISSING: ("controls", "per-operation controls are not part of the action-profile "
                                 "format; the manifest binds kernel capability contracts instead"),
    FloorCode.REVIEW_FAILS_OPEN: ("review", "the action-profile format declares no review capacity; "
                                  "review load is not governed by this source"),
}


#: Keys only the governed-learning pack format carries; see ``_load_profile_source``.
_GOVERNED_ONLY_KEYS = frozenset({"controls", "review", "model_manifests", "delegation", "identity_fields"})


class PackCode:
    """Finding codes added by the manifest layer (the floor's own codes are in ``FloorCode``)."""

    SCHEMA = "PACK_MANIFEST_INVALID"
    PLACEHOLDER = "PACK_PLACEHOLDER_UNFILLED"
    DRIFT = "PACK_MANIFEST_DRIFT"
    SOURCE_INVALID = "PACK_SOURCE_INVALID"
    TEST_MISSING = "PACK_TEST_MISSING"
    CAPABILITY_UNKNOWN = "PACK_CAPABILITY_UNKNOWN"
    KERNEL_CAPABILITY_MISSING = "PACK_KERNEL_CAPABILITY_MISSING"
    PUBLIC_ZONE_UNDECLASSIFIED = "PACK_UNDECLASSIFIED_CLASS_IN_PUBLIC_ZONE"
    DECLASSIFIER_NOT_INDEPENDENT = "PACK_DECLASSIFIER_NOT_INDEPENDENT"
    DECLASSIFIER_NOT_ACCOUNTABLE = "PACK_DECLASSIFIER_HOLDS_NO_CONSEQUENTIAL_TRANSITION"
    EMERGENCY_REVIEW_NOT_ENFORCED = "PACK_EMERGENCY_REVIEW_NOT_ENFORCED"
    EMERGENCY_REVIEWER_NOT_INDEPENDENT = "PACK_EMERGENCY_REVIEWER_NOT_INDEPENDENT"


class PackError(ValueError):
    """The pack cannot be relied on. ``findings`` lists every reason at once."""

    def __init__(self, path: str | Path, findings: list[FloorFinding]) -> None:
        self.path = str(path)
        self.findings = list(findings)
        detail = "; ".join(f"{f.code} at {f.where}: {f.detail}" for f in self.findings)
        super().__init__(f"domain pack {self.path} is not loadable: {detail}")


# ---------------------------------------------------------------------------
# Declarations
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RecipientDeclaration:
    """Who may receive which classes, for which purposes, in which zone."""

    classes: frozenset[str]
    purposes: frozenset[str]
    zone: str
    subject_scope: str = "any"


@dataclass(frozen=True)
class TransitionDeclaration:
    """The approver roles and consequence of one operation (over all its from/to pairs)."""

    approver_roles: frozenset[str]
    consequential: bool


@dataclass(frozen=True)
class DeclassificationDeclaration:
    """One exact-output declassification rule and its independent approver."""

    from_classes: frozenset[str]
    to_class: str
    purposes: frozenset[str]
    approval_role: str
    removes_subject_identity: bool


@dataclass(frozen=True)
class EmergencyAccessDeclaration:
    """Bounded break-glass access: expiry, unreviewed limit, and the reviewing role."""

    purposes: frozenset[str]
    max_ttl_seconds: float
    max_unreviewed_per_holder: int
    review_role: str


@dataclass(frozen=True)
class PackManifest:
    """A loaded, drift-free, at-or-above-floor domain pack."""

    path: Path
    schema_version: str
    sector: str
    title: str
    profile_paths: tuple[Path, ...]
    profiles: tuple[ApplicationProfile, ...]
    governed_pack: GovernedPack | None
    capabilities: tuple[CapabilityContract, ...]
    purposes: frozenset[str]
    data_classes: dict[str, frozenset[str] | None]
    recipients: dict[str, RecipientDeclaration]
    transitions: dict[str, TransitionDeclaration]
    declassification: dict[str, DeclassificationDeclaration]
    emergency_access: frozenset[EmergencyAccessDeclaration]
    fallback: str
    tests: tuple[str, ...]
    limits: tuple[str, ...]
    #: pack_floor rules not applicable to a source, with the reason. Reported, never hidden.
    floor_exemptions: tuple[str, ...] = ()

    @property
    def enforcing_profiles(self) -> tuple[ApplicationProfile, ...]:
        """Every profile whose configuration the runtime enforces for this pack."""
        extra = (self.governed_pack.profile,) if self.governed_pack is not None else ()
        return (*self.profiles, *extra)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class _Schema(Exception):
    def __init__(self, where: str, detail: str) -> None:
        super().__init__(detail)
        self.where = where
        self.detail = detail


def _placeholders(value: Any, where: str = "") -> list[str]:
    if isinstance(value, str):
        return [where or "pack"] if PLACEHOLDER_MARKER in value else []
    if isinstance(value, dict):
        found: list[str] = []
        for key, child in value.items():
            child_where = f"{where}.{key}" if where else str(key)
            if PLACEHOLDER_MARKER in str(key):
                found.append(child_where)
            found.extend(_placeholders(child, child_where))
        return found
    if isinstance(value, list):
        return [hit for index, child in enumerate(value) for hit in _placeholders(child, f"{where}[{index}]")]
    return []


def _keys(raw: Any, allowed: frozenset[str], where: str, *, required: tuple[str, ...] = ()) -> dict:
    if not isinstance(raw, dict):
        raise _Schema(where, f"{where} must be a mapping")
    for key in raw:
        if key not in allowed:
            raise _Schema(f"{where}.{key}" if where != "pack" else str(key),
                          f"unknown key {key!r}; the kernel does not read it, so it cannot do what it says")
    for key in required:
        if key not in raw:
            raise _Schema(key, f"missing required key {key!r}; declare it explicitly, even when empty")
    return raw


def _text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _Schema(where, f"{where} is empty; this is an open governance decision, return it to its owner")
    return value.strip()


def _strings(value: Any, where: str, *, allow_empty: bool = True) -> tuple[str, ...]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise _Schema(where, f"{where} must be a {'non-empty ' if not allow_empty else ''}list")
    items = tuple(_text(item, where) for item in value)
    if len(set(items)) != len(items):
        raise _Schema(where, f"{where} contains duplicates")
    return items


def _mapping(value: Any, where: str, *, allow_empty: bool = True) -> dict:
    if not isinstance(value, dict) or (not value and not allow_empty):
        raise _Schema(where, f"{where} must be a {'non-empty ' if not allow_empty else ''}mapping")
    return value


def _parse(raw: Any) -> dict[str, Any]:
    body = _keys(raw, _TOP_LEVEL, "pack", required=_REQUIRED)
    if str(body["schema_version"]) != SCHEMA_VERSION:
        raise _Schema("schema_version", f"schema_version must be {SCHEMA_VERSION!r}")
    sources = _keys(body["sources"], _SOURCE_KEYS, "sources", required=("profiles",))
    governed = sources.get("governed_learning_pack")
    parsed: dict[str, Any] = {
        "sector": _text(body["sector"], "sector"),
        "title": _text(body["title"], "title"),
        "profiles": _strings(sources["profiles"], "sources.profiles", allow_empty=False),
        "governed_learning_pack": None if governed is None else _text(governed, "sources.governed_learning_pack"),
        "capabilities": _strings(body["capabilities"], "capabilities", allow_empty=False),
        "purposes": frozenset(_strings(body["purposes"], "purposes")),
        "fallback": _text(body["fallback"], "fallback"),
        "tests": _strings(body["tests"], "tests", allow_empty=False),
        "limits": _strings(body["limits"], "limits", allow_empty=False),
    }

    classes: dict[str, frozenset[str] | None] = {}
    for name, zones in _mapping(body["data_classes"], "data_classes", allow_empty=False).items():
        where = f"data_classes.{name}"
        classes[_text(name, "data_classes key")] = (
            None if zones is None else frozenset(_strings(zones, where)))
    parsed["data_classes"] = classes

    recipients: dict[str, RecipientDeclaration] = {}
    for name, spec in _mapping(body["recipients"], "recipients").items():
        where = f"recipients.{name}"
        spec = _keys(spec, _RECIPIENT_KEYS, where)
        scope = spec.get("subject_scope", "any")
        if scope not in {"any", "self"}:
            raise _Schema(f"{where}.subject_scope", "subject_scope must be any or self")
        recipients[_text(name, "recipient name")] = RecipientDeclaration(
            classes=frozenset(_strings(spec.get("classes"), f"{where}.classes")),
            purposes=frozenset(_strings(spec.get("purposes"), f"{where}.purposes")),
            zone=_text(spec.get("zone"), f"{where}.zone"),
            subject_scope=scope,
        )
    parsed["recipients"] = recipients

    transitions: dict[str, TransitionDeclaration] = {}
    for name, spec in _mapping(body["transitions"], "transitions", allow_empty=False).items():
        where = f"transitions.{name}"
        spec = _keys(spec, _TRANSITION_KEYS, where, required=())
        if not isinstance(spec.get("consequential"), bool):
            raise _Schema(f"{where}.consequential", f"{where}.consequential must be boolean")
        transitions[_text(name, "transition name")] = TransitionDeclaration(
            approver_roles=frozenset(_strings(spec.get("approver_roles"), f"{where}.approver_roles",
                                              allow_empty=False)),
            consequential=spec["consequential"],
        )
    parsed["transitions"] = transitions

    declassification: dict[str, DeclassificationDeclaration] = {}
    for name, spec in _mapping(body["declassification"], "declassification").items():
        where = f"declassification.{name}"
        spec = _keys(spec, _DECLASSIFICATION_KEYS, where)
        if not isinstance(spec.get("removes_subject_identity"), bool):
            raise _Schema(f"{where}.removes_subject_identity", "removes_subject_identity must be boolean")
        declassification[_text(name, "declassification name")] = DeclassificationDeclaration(
            from_classes=frozenset(_strings(spec.get("from_classes"), f"{where}.from_classes", allow_empty=False)),
            to_class=_text(spec.get("to_class"), f"{where}.to_class"),
            purposes=frozenset(_strings(spec.get("purposes"), f"{where}.purposes", allow_empty=False)),
            approval_role=_text(spec.get("approval_role"), f"{where}.approval_role"),
            removes_subject_identity=spec["removes_subject_identity"],
        )
    parsed["declassification"] = declassification

    emergency: set[EmergencyAccessDeclaration] = set()
    if not isinstance(body["emergency_access"], list):
        raise _Schema("emergency_access", "emergency_access must be a list")
    for index, spec in enumerate(body["emergency_access"]):
        where = f"emergency_access[{index}]"
        spec = _keys(spec, _EMERGENCY_KEYS, where)
        ttl, limit = spec.get("max_ttl_seconds"), spec.get("max_unreviewed_per_holder")
        if not isinstance(ttl, (int, float)) or isinstance(ttl, bool) or ttl <= 0:
            raise _Schema(f"{where}.max_ttl_seconds", "emergency access must expire: max_ttl_seconds > 0")
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            raise _Schema(f"{where}.max_unreviewed_per_holder", "max_unreviewed_per_holder must be >= 1")
        emergency.add(EmergencyAccessDeclaration(
            purposes=frozenset(_strings(spec.get("purposes"), f"{where}.purposes", allow_empty=False)),
            max_ttl_seconds=float(ttl),
            max_unreviewed_per_holder=limit,
            review_role=_text(spec.get("review_role"), f"{where}.review_role"),
        ))
    parsed["emergency_access"] = frozenset(emergency)
    return parsed


# ---------------------------------------------------------------------------
# What the sources actually enforce
# ---------------------------------------------------------------------------


@dataclass
class _Enforced:
    purposes: set[str] = field(default_factory=set)
    data_classes: dict[str, frozenset[str] | None] = field(default_factory=dict)
    recipients: dict[str, RecipientDeclaration] = field(default_factory=dict)
    transitions: dict[str, TransitionDeclaration] = field(default_factory=dict)
    declassification: dict[str, DeclassificationDeclaration] = field(default_factory=dict)
    emergency_access: set[EmergencyAccessDeclaration] = field(default_factory=set)
    conflicts: list[FloorFinding] = field(default_factory=list)


def _merge(target: dict, name: str, value: Any, where: str, conflicts: list[FloorFinding]) -> None:
    if name in target and target[name] != value:
        conflicts.append(FloorFinding(
            PackCode.DRIFT, where,
            f"sources disagree on {name!r} ({target[name]!r} vs {value!r}); one manifest entry cannot describe both"))
        return
    target[name] = value


def _enforced(profiles: tuple[ApplicationProfile, ...]) -> _Enforced:
    view = _Enforced()
    for profile in profiles:
        policy = profile.disclosure
        zones = policy.class_zones if policy is not None else {}
        for data_class in profile.governance.data_classes if profile.governance else ():
            _merge(view.data_classes, data_class, zones.get(data_class), f"data_classes.{data_class}",
                   view.conflicts)
        by_operation: dict[str, list] = {}
        for rule in profile.transitions:
            by_operation.setdefault(rule.operation, []).append(rule)
        for operation, rules in by_operation.items():
            consequence = {rule.consequential for rule in rules}
            if len(consequence) > 1:
                view.conflicts.append(FloorFinding(
                    PackCode.DRIFT, f"transitions.{operation}",
                    f"{profile.profile_id} marks some {operation} transitions consequential and others not"))
                continue
            _merge(view.transitions, operation, TransitionDeclaration(
                frozenset(rule.approval_role for rule in rules), consequence.pop()),
                f"transitions.{operation}", view.conflicts)
        if policy is None:
            continue
        view.purposes |= set(policy.purposes)
        for name, rule in policy.recipients.items():
            _merge(view.recipients, name, RecipientDeclaration(
                frozenset(rule.classes), frozenset(rule.purposes), rule.zone, rule.subject_scope),
                f"recipients.{name}", view.conflicts)
        for name, rule in policy.declassification.items():
            _merge(view.declassification, name, DeclassificationDeclaration(
                frozenset(rule.from_classes), rule.to_class, frozenset(rule.purposes), rule.approval_role,
                rule.removes_subject_identity), f"declassification.{name}", view.conflicts)
        if policy.break_glass is not None:
            glass = policy.break_glass
            view.emergency_access.add(EmergencyAccessDeclaration(
                frozenset(glass.purposes), float(glass.max_ttl_seconds), glass.max_unreviewed_per_holder,
                glass.review_role))
    return view


def _drift(manifest: dict[str, Any], view: _Enforced) -> list[FloorFinding]:
    findings = list(view.conflicts)

    def add(where: str, detail: str) -> None:
        findings.append(FloorFinding(PackCode.DRIFT, where, detail))

    claimed = manifest["purposes"] - view.purposes
    omitted = view.purposes - manifest["purposes"]
    if claimed:
        add("purposes", f"declared but not enforced by any source: {', '.join(sorted(claimed))}")
    if omitted:
        add("purposes", f"enforced but not declared: {', '.join(sorted(omitted))}")

    for section in ("data_classes", "recipients", "transitions", "declassification"):
        declared: dict = manifest[section]
        enforced: dict = getattr(view, section)
        for name in sorted(set(declared) - set(enforced)):
            add(f"{section}.{name}", f"declared but no source enforces {name!r}")
        for name in sorted(set(enforced) - set(declared)):
            add(f"{section}.{name}", "enforced by a source but not declared in the manifest")
        for name in sorted(set(declared) & set(enforced)):
            if declared[name] != enforced[name]:
                add(f"{section}.{name}", f"manifest declares {declared[name]!r}; sources enforce {enforced[name]!r}")

    if manifest["emergency_access"] != frozenset(view.emergency_access):
        add("emergency_access",
            f"manifest declares {sorted(map(repr, manifest['emergency_access']))}; "
            f"sources enforce {sorted(map(repr, view.emergency_access))}")
    return findings


# ---------------------------------------------------------------------------
# Floor
# ---------------------------------------------------------------------------


def _fallback_ok(text: str) -> bool:
    return len(text.split()) >= 4 and text.strip().lower() not in {"none", "none needed", "n/a"}


def _sector_neutral_floor(profile: ApplicationProfile) -> list[FloorFinding]:
    """Rules that hold in any sector, over what a profile actually enforces."""
    findings: list[FloorFinding] = []
    policy = profile.disclosure
    if policy is None:
        return findings
    pid = profile.profile_id
    consequential_roles = {rule.approval_role for rule in profile.transitions if rule.consequential}
    identity_removed = {rule.to_class for rule in policy.declassification.values() if rule.removes_subject_identity}

    for data_class, zones in sorted(policy.class_zones.items()):
        public = sorted(set(zones) & EXTERNAL_ZONES)
        if public and data_class not in identity_removed:
            findings.append(FloorFinding(
                PackCode.PUBLIC_ZONE_UNDECLASSIFIED, f"{pid}:disclosure.class_zones.{data_class}",
                f"{data_class} may be processed in {', '.join(public)} without passing an identity-removing "
                "declassification"))
    for name, rule in sorted(policy.recipients.items()):
        leaked = sorted(set(rule.classes) - identity_removed)
        if rule.zone in EXTERNAL_ZONES and leaked:
            findings.append(FloorFinding(
                PackCode.PUBLIC_ZONE_UNDECLASSIFIED, f"{pid}:disclosure.recipients.{name}",
                f"public-zone recipient receives undeclassified {', '.join(leaked)}"))

    for name, rule in sorted(policy.declassification.items()):
        receiver = policy.recipients.get(rule.approval_role)
        if receiver is not None and rule.to_class in receiver.classes:
            findings.append(FloorFinding(
                PackCode.DECLASSIFIER_NOT_INDEPENDENT, f"{pid}:disclosure.declassification.{name}",
                f"{rule.approval_role} approves lowering data to {rule.to_class} and also receives it"))
        if rule.approval_role not in consequential_roles:
            findings.append(FloorFinding(
                PackCode.DECLASSIFIER_NOT_ACCOUNTABLE, f"{pid}:disclosure.declassification.{name}",
                f"{rule.approval_role} holds no consequential transition, so no named human review binds it"))

    glass = policy.break_glass
    if glass is not None:
        if glass.review_role not in consequential_roles:
            findings.append(FloorFinding(
                PackCode.EMERGENCY_REVIEW_NOT_ENFORCED, f"{pid}:disclosure.break_glass.review_role",
                f"{glass.review_role} holds no consequential transition; the review obligation is not enforced"))
        holder = policy.recipients.get(glass.review_role)
        if holder is not None and set(holder.purposes) & set(glass.purposes):
            findings.append(FloorFinding(
                PackCode.EMERGENCY_REVIEWER_NOT_INDEPENDENT, f"{pid}:disclosure.break_glass.review_role",
                f"{glass.review_role} may itself use emergency access for "
                f"{', '.join(sorted(set(holder.purposes) & set(glass.purposes)))} and would review its own use"))
    return findings


def _read_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise _Schema(str(path), f"cannot read {path}: {exc}") from exc


def _source_path(reference: str, base: Path) -> Path:
    path = Path(reference)
    return path if path.is_absolute() else (base / path).resolve()


def _load_profile_source(path: Path, root: Path, findings: list[FloorFinding],
                         exemptions: list[str]) -> ApplicationProfile | None:
    try:
        raw = _read_yaml(path)
    except _Schema as exc:
        findings.append(FloorFinding(PackCode.SOURCE_INVALID, str(path), exc.detail))
        return None
    # Exemptions apply only to a genuine action profile. A source carrying any key
    # of the governed-learning format is held to that format's full floor, so a
    # governed pack cannot shed its controls by being listed under ``profiles``.
    governed_shape = isinstance(raw, dict) and any(key in raw for key in _GOVERNED_ONLY_KEYS)
    for finding in check_pack(raw, repo_root=root):
        exempt = _PROFILE_EXEMPTIONS.get(finding.code)
        if exempt and isinstance(raw, dict) and exempt[0] not in raw and not governed_shape:
            note = f"{path.name}: {finding.code} not applicable ({exempt[1]})"
            if note not in exemptions:
                exemptions.append(note)
            continue
        findings.append(FloorFinding(finding.code, f"{path.name}:{finding.where}", finding.detail))
    try:
        return ApplicationProfile.from_dict(raw)
    except ProfileError as exc:
        findings.append(FloorFinding(PackCode.SOURCE_INVALID, path.name, str(exc)))
        return None


def _load_governed_source(path: Path, root: Path, findings: list[FloorFinding]) -> GovernedPack | None:
    try:
        raw = _read_yaml(path)
    except _Schema as exc:
        findings.append(FloorFinding(PackCode.SOURCE_INVALID, str(path), exc.detail))
        return None
    floor = check_pack(raw, repo_root=root)
    findings.extend(FloorFinding(f.code, f"{path.name}:{f.where}", f.detail) for f in floor)
    if floor:
        return None
    try:
        return GovernedPack(raw, ApplicationProfile.from_dict(raw), str(path))
    except ProfileError as exc:
        findings.append(FloorFinding(PackCode.SOURCE_INVALID, path.name, str(exc)))
        return None


def load_pack(path: str | Path, *, root: str | Path, capability_dir: str | Path | None = None) -> PackManifest:
    """Load ``packs/<sector>.pack.yaml`` only if it is well formed, drift-free, and at the floor.

    ``root`` is the repository root: test locators and capability contracts resolve
    against it. Source paths resolve relative to the manifest file (absolute paths are
    accepted, so a pack can live outside the repository). Raises :class:`PackError`
    listing every finding.
    """
    path = Path(path)
    root = Path(root)
    raw = None
    try:
        raw = _read_yaml(path)
    except _Schema as exc:
        raise PackError(path, [FloorFinding(PackCode.SCHEMA, exc.where, exc.detail)]) from exc
    unfilled = _placeholders(raw)
    if unfilled:
        raise PackError(path, [FloorFinding(PackCode.PLACEHOLDER, where,
                                            f"{PLACEHOLDER_MARKER} placeholder not filled") for where in unfilled])
    try:
        manifest = _parse(raw)
    except _Schema as exc:
        raise PackError(path, [FloorFinding(PackCode.SCHEMA, exc.where, exc.detail)]) from exc

    findings: list[FloorFinding] = []
    exemptions: list[str] = []

    for locator in manifest["tests"]:
        try:
            resolve_test_locator(locator, root=root)
        except ContractError as exc:
            findings.append(FloorFinding(PackCode.TEST_MISSING, f"tests:{locator}", str(exc)))

    try:
        contracts = {c.id: c for c in load_capability_contracts(
            Path(capability_dir) if capability_dir else root / "contract" / "capabilities", root=root)}
    except ContractError as exc:
        raise PackError(path, [FloorFinding(PackCode.CAPABILITY_UNKNOWN, "capabilities", str(exc))]) from exc
    bound: list[CapabilityContract] = []
    for capability_id in manifest["capabilities"]:
        if capability_id in contracts:
            bound.append(contracts[capability_id])
        else:
            findings.append(FloorFinding(PackCode.CAPABILITY_UNKNOWN, f"capabilities:{capability_id}",
                                         f"no capability contract {capability_id!r} is loaded"))

    base = path.resolve().parent
    profile_paths = tuple(_source_path(ref, base) for ref in manifest["profiles"])
    profiles = [_load_profile_source(p, root, findings, exemptions) for p in profile_paths]
    governed = None
    if manifest["governed_learning_pack"] is not None:
        governed = _load_governed_source(_source_path(manifest["governed_learning_pack"], base), root, findings)
        if governed is None:
            profiles.append(None)

    if not _fallback_ok(manifest["fallback"]):
        findings.append(FloorFinding(FloorCode.FALLBACK_MISSING, "fallback",
                                     "failure must route to a staffed path"))

    loaded = tuple(p for p in profiles if p is not None)
    enforcing = (*loaded, *((governed.profile,) if governed is not None else ()))
    required = set(KERNEL_CAPABILITIES)
    if any(p.disclosure is not None for p in enforcing):
        required |= set(DISCLOSURE_CAPABILITIES)
    for capability_id in sorted(required - set(manifest["capabilities"])):
        findings.append(FloorFinding(PackCode.KERNEL_CAPABILITY_MISSING, f"capabilities:{capability_id}",
                                     "a pack may add capability contracts but never drop a kernel one"))
    for profile in enforcing:
        findings.extend(_sector_neutral_floor(profile))

    if None not in profiles:
        findings.extend(_drift(manifest, _enforced(enforcing)))

    if findings:
        raise PackError(path, findings)
    return PackManifest(
        path=path,
        schema_version=SCHEMA_VERSION,
        sector=manifest["sector"],
        title=manifest["title"],
        profile_paths=profile_paths,
        profiles=loaded,
        governed_pack=governed,
        capabilities=tuple(bound),
        purposes=manifest["purposes"],
        data_classes=manifest["data_classes"],
        recipients=manifest["recipients"],
        transitions=manifest["transitions"],
        declassification=manifest["declassification"],
        emergency_access=manifest["emergency_access"],
        fallback=manifest["fallback"],
        tests=manifest["tests"],
        limits=manifest["limits"],
        floor_exemptions=tuple(exemptions),
    )


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Ratio:
    """``numerator`` of ``denominator`` items, each item being one ``unit``."""

    numerator: int
    denominator: int
    unit: str

    def to_dict(self) -> dict:
        """Serialize with the unit beside the numbers."""
        return {"numerator": self.numerator, "denominator": self.denominator, "unit": self.unit}


@dataclass(frozen=True)
class Count:
    """A count whose unit is named."""

    value: int
    unit: str

    def to_dict(self) -> dict:
        """Serialize with the unit beside the number."""
        return {"value": self.value, "unit": self.unit}


@dataclass(frozen=True)
class ActionEvaluation:
    """Bounded verification and adversarial evaluation of one action profile."""

    profile_id: str
    states_explored: Count
    violations: Count
    scenarios: Ratio
    benign: Ratio
    unauthorized_mutations: Count
    invariants_hold: bool

    def to_dict(self) -> dict:
        """Serialize one profile's action denominators."""
        return {
            "profile_id": self.profile_id,
            "states_explored": self.states_explored.to_dict(),
            "violations": self.violations.to_dict(),
            "scenarios": self.scenarios.to_dict(),
            "benign": self.benign.to_dict(),
            "unauthorized_mutations": self.unauthorized_mutations.to_dict(),
            "invariants_hold": self.invariants_hold,
        }


@dataclass(frozen=True)
class DisclosureEvaluation:
    """The generated disclosure suite for one profile that declares a disclosure policy."""

    profile_id: str
    hostile: Ratio
    benign: Ratio
    checks: Ratio
    states_explored: Count
    violations: Count
    holds: bool

    def to_dict(self) -> dict:
        """Serialize one profile's disclosure denominators."""
        return {
            "profile_id": self.profile_id,
            "hostile": self.hostile.to_dict(),
            "benign": self.benign.to_dict(),
            "checks": self.checks.to_dict(),
            "states_explored": self.states_explored.to_dict(),
            "violations": self.violations.to_dict(),
            "holds": self.holds,
        }


@dataclass(frozen=True)
class PackEvaluation:
    """Per-profile results for one pack. There is deliberately no pooled total."""

    sector: str
    action: tuple[ActionEvaluation, ...]
    disclosure: tuple[DisclosureEvaluation, ...]
    not_evaluated: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        """Serialize; each entry keeps its own denominators and units."""
        return {
            "sector": self.sector,
            "action": [entry.to_dict() for entry in self.action],
            "disclosure": [entry.to_dict() for entry in self.disclosure],
            "not_evaluated": list(self.not_evaluated),
        }


def _evaluate_action(profile: ApplicationProfile) -> ActionEvaluation:
    verification = verify_profile(profile)
    evaluation = EvaluationRunner(profile).run()
    return ActionEvaluation(
        profile_id=profile.profile_id,
        states_explored=Count(verification.states_explored, "bounded authority configurations enumerated"),
        violations=Count(len(verification.violations), "invariant violations across enumerated configurations"),
        scenarios=Ratio(evaluation.passed, evaluation.total, "hostile action scenarios contained"),
        benign=Ratio(evaluation.benign_completed, len(evaluation.utility), "benign declared transitions completed"),
        unauthorized_mutations=Count(evaluation.unauthorized_mutations,
                                     "unauthorized mutations across hostile action scenarios"),
        invariants_hold=verification.holds,
    )


def _evaluate_disclosure(profile: ApplicationProfile) -> DisclosureEvaluation:
    from ..disclosure_eval import run_disclosure_suite

    report = run_disclosure_suite(profile.disclosure, profile_id=profile.profile_id).to_dict()
    summary = report["summary"]
    verification = report["verification"]["summary"]
    return DisclosureEvaluation(
        profile_id=profile.profile_id,
        hostile=Ratio(summary["contained_by_arm"]["this_architecture"], summary["hostile_scenarios"],
                      "hostile disclosure scenarios contained"),
        benign=Ratio(summary["benign_completed"], summary["benign_total"], "benign disclosure tasks completed"),
        checks=Ratio(summary["checks_load_bearing"], summary["checks_ablated"],
                     "disclosure checks load-bearing under ablation"),
        states_explored=Count(verification["states_explored"], "bounded disclosure read and release states"),
        violations=Count(verification["violations"], "disclosure invariant violations"),
        holds=bool(summary["holds"]),
    )


def evaluate_pack(pack: PackManifest) -> PackEvaluation:
    """Run the existing evaluations for every enforced profile the pack references.

    Action profiles get :func:`fssaira.verification.verify_profile` and the
    :class:`fssaira.evaluation.EvaluationRunner` suite, exactly as the published domain
    matrix does. Profiles that declare a disclosure policy additionally get
    :func:`fssaira.disclosure_eval.run_disclosure_suite`. A governed-learning pack is
    held to the floor at load time but not evaluated here; it is named in
    ``not_evaluated`` so its absence from the denominators is explicit.
    """
    action = tuple(_evaluate_action(profile) for profile in pack.profiles)
    disclosure = tuple(_evaluate_disclosure(profile) for profile in pack.profiles
                       if profile.disclosure is not None)
    not_evaluated = ()
    if pack.governed_pack is not None:
        not_evaluated = (f"{pack.governed_pack.profile.profile_id}: floor-checked at load; evaluated by its "
                         "named tests, not by the domain-pack matrix",)
    return PackEvaluation(pack.sector, action, disclosure, not_evaluated)


__all__ = [
    "DISCLOSURE_CAPABILITIES", "KERNEL_CAPABILITIES", "ActionEvaluation", "Count",
    "DeclassificationDeclaration", "DisclosureEvaluation", "EmergencyAccessDeclaration", "PackCode",
    "PackError", "PackEvaluation", "PackManifest", "Ratio", "RecipientDeclaration",
    "TransitionDeclaration", "evaluate_pack", "load_pack",
]
