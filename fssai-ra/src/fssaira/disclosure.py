"""Governed disclosure: the data half of the constitution.

Everything else in this architecture governs what an AI system may *do*. The
rule it enforces is

    **A model may propose an action. It cannot manufacture the authority to
    execute it.**

That rule is necessary and, for the systems institutions are now building, it
is not sufficient. A clinical-record assistant, a corporate copilot over
confidential data, or a research agent over a cohort causes most of its harm
without executing anything. It *reads*. What it read is placed in a prompt,
sent to a model endpoint, summarised, and handed to whoever asked. None of that
is a state transition, so none of it reaches the executor, the approval check,
or the resource-version check. An exact-action kernel alone governs the write
path of a system whose dominant risk is the read path.

This module supplies the second rule, and it is written to mirror the first:

    **A model may request information. It cannot manufacture the entitlement to
    see it, and it cannot launder what it saw.**

The two halves of that sentence are different controls.

*Entitlement* is checked before anything enters a model context. A signed,
holder-bound, expiring grant names a purpose, subjects, fields, and data classes.
The gate, not the model, holds the record-store credential, and it releases only
the intersection of what was granted, what was asked, what consent currently
permits, and what may be processed at the model endpoint's location.

*Laundering* is the failure every retrieval-augmented system is exposed to and
almost none governs. Protected values go into a context; a summary comes out;
the summary carries no label, so it flows wherever plain text flows. The model
is asked, in effect, to classify its own output, which is the data-path twin of
a model declaring its own action low risk. Here the gate labels every output as
the join of everything released into the session that produced it. The model's
claimed label is recorded and ignored. The only way to lower a label is an
exact-output declassification, bound to the output's digest and approved by an
independent role named in the domain pack.

The lattice
-----------
A :class:`DataLabel` has four components and a join that only ever tightens:

=============  ==========================  =================================
component      meaning                     join (combining two inputs)
=============  ==========================  =================================
``classes``    sensitivity classes present union: more classes, more care
``subjects``   people or entities in it    union: more people affected
``purposes``   uses still permitted        intersection: fewer uses
``zones``      where it may be processed   intersection: fewer places
=============  ==========================  =================================

This is the data-flow counterpart of delegation's attenuation rule. Authority
only narrows as it travels through agents. Restriction only accumulates as data
travels through models. Both properties are checkable in one pass without
trusting any component's account of itself, which is what makes them controls.

What is enforced
----------------
Thirteen checks, each with stable denial codes and each independently ablatable
(``ALL_CHECKS``). The disclosure suite in :mod:`fssaira.disclosure_eval` shows
that removing any one of them lets a specific harm through.

What this does not establish
----------------------------
Redacting released values from an output is not de-identification, and nothing
here measures re-identification risk. Session taint is conservative and will
over-label outputs that ignored most of their context; that is a utility cost,
reported rather than hidden. Values the model encodes, paraphrases, or infers
are labelled only because the whole session is labelled, not because anything
detects them. Consent and purpose semantics are declared by the institution and
not validated against any law. These are fixture observations of an in-process
gate, with the same limits as the rest of ``docs/ASSURANCE.md``.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
from typing import Any

from .evidence import EvidenceError, EvidenceLedger

# ---------------------------------------------------------------------------
# Checks and codes
# ---------------------------------------------------------------------------

#: Every ablatable check the gate performs. Structural refusals (an undeclared
#: field, an unknown subject, an output the gate never issued) are not listed:
#: they are not safeguards that can be switched off, they are the absence of
#: anything to release.
ALL_CHECKS = (
    "grant_signature",               # the grant was issued by a trusted authority, unmodified
    "holder_binding",                # the grant names this requester and was not self-issued
    "grant_currency",                # the grant is unexpired and unrevoked
    "purpose_binding",               # the request's purpose is the grant's purpose
    "subject_scope",                 # every requested subject is inside the grant
    "minimum_necessary",             # every requested field is inside the grant
    "consent",                       # the subject currently permits this purpose
    "class_clearance",               # every released class is inside the grant
    "residency",                     # the model endpoint's zone may process every class
    "break_glass",                   # emergency access is bounded and its review is not overdue
    "session_taint",                 # outputs carry the join of their session, not a claim
    "recipient_clearance",           # the recipient dominates the output's label
    "exact_output_declassification", # lowering a label needs an independent, exact approval
)


class DisclosureCode:
    """Stable denial codes, one family per check."""

    GRANT_NOT_SUPPLIED = "GRANT_NOT_SUPPLIED"
    GRANT_SIGNATURE_INVALID = "GRANT_SIGNATURE_INVALID"
    GRANT_KEY_UNTRUSTED = "GRANT_KEY_UNTRUSTED"
    GRANT_HOLDER_MISMATCH = "GRANT_HOLDER_MISMATCH"
    GRANT_SELF_ISSUED = "GRANT_SELF_ISSUED"
    SESSION_HOLDER_MISMATCH = "SESSION_HOLDER_MISMATCH"
    GRANT_EXPIRED = "GRANT_EXPIRED"
    GRANT_REVOKED = "GRANT_REVOKED"
    PURPOSE_UNDECLARED = "PURPOSE_UNDECLARED"
    PURPOSE_MISMATCH = "PURPOSE_MISMATCH"
    SUBJECT_OUT_OF_SCOPE = "SUBJECT_OUT_OF_SCOPE"
    SUBJECT_NOT_FOUND = "SUBJECT_NOT_FOUND"
    FIELD_UNDECLARED = "FIELD_UNDECLARED"
    FIELD_NOT_MINIMUM_NECESSARY = "FIELD_NOT_MINIMUM_NECESSARY"
    CONSENT_WITHDRAWN = "CONSENT_WITHDRAWN"
    CLASS_NOT_CLEARED = "CLASS_NOT_CLEARED"
    ENDPOINT_UNDECLARED = "ENDPOINT_UNDECLARED"
    RESIDENCY_VIOLATION = "RESIDENCY_VIOLATION"
    BREAK_GLASS_NOT_PERMITTED = "BREAK_GLASS_NOT_PERMITTED"
    BREAK_GLASS_PURPOSE = "BREAK_GLASS_PURPOSE"
    BREAK_GLASS_TOO_LONG = "BREAK_GLASS_TOO_LONG"
    BREAK_GLASS_UNJUSTIFIED = "BREAK_GLASS_UNJUSTIFIED"
    BREAK_GLASS_REVIEW_OVERDUE = "BREAK_GLASS_REVIEW_OVERDUE"
    OUTPUT_UNKNOWN = "OUTPUT_UNKNOWN"
    RECIPIENT_UNDECLARED = "RECIPIENT_UNDECLARED"
    RECIPIENT_CLASS_NOT_CLEARED = "RECIPIENT_CLASS_NOT_CLEARED"
    RECIPIENT_PURPOSE_NOT_PERMITTED = "RECIPIENT_PURPOSE_NOT_PERMITTED"
    RECIPIENT_ZONE_NOT_PERMITTED = "RECIPIENT_ZONE_NOT_PERMITTED"
    RECIPIENT_SUBJECT_NOT_PERMITTED = "RECIPIENT_SUBJECT_NOT_PERMITTED"
    DECLASSIFICATION_RULE_UNKNOWN = "DECLASSIFICATION_RULE_UNKNOWN"
    DECLASSIFICATION_NOT_APPROVED = "DECLASSIFICATION_NOT_APPROVED"
    DECLASSIFICATION_SIGNATURE_INVALID = "DECLASSIFICATION_SIGNATURE_INVALID"
    DECLASSIFICATION_WRONG_ROLE = "DECLASSIFICATION_WRONG_ROLE"
    DECLASSIFICATION_SELF_APPROVED = "DECLASSIFICATION_SELF_APPROVED"
    DECLASSIFICATION_WRONG_OUTPUT = "DECLASSIFICATION_WRONG_OUTPUT"
    DECLASSIFICATION_EXPIRED = "DECLASSIFICATION_EXPIRED"
    DECLASSIFICATION_OUT_OF_RULE = "DECLASSIFICATION_OUT_OF_RULE"
    REVIEW_NOT_PERMITTED = "REVIEW_NOT_PERMITTED"
    EVIDENCE_UNAVAILABLE = "EVIDENCE_UNAVAILABLE"


class DisclosurePolicyError(ValueError):
    """A domain pack's disclosure section is incomplete or inconsistent."""


class DisclosureDenied(Exception):
    """Raised when the gate refuses to release; nothing was disclosed."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------------------
# The label lattice
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DataLabel:
    """What a piece of data is, who it concerns, and where and why it may go."""

    classes: frozenset[str]
    subjects: frozenset[str]
    purposes: frozenset[str]
    zones: frozenset[str]

    @classmethod
    def bottom(cls, policy: DisclosurePolicy) -> DataLabel:
        """The label of no data at all: every purpose and zone still open."""
        return cls(frozenset(), frozenset(), frozenset(policy.purposes),
                   frozenset(policy.all_zones))

    def join(self, other: DataLabel) -> DataLabel:
        return DataLabel(
            classes=self.classes | other.classes,
            subjects=self.subjects | other.subjects,
            purposes=self.purposes & other.purposes,
            zones=self.zones & other.zones,
        )

    def dominates(self, other: DataLabel) -> bool:
        """True when this label is at least as restrictive as ``other``."""
        return (
            self.classes >= other.classes
            and self.subjects >= other.subjects
            and self.purposes <= other.purposes
            and self.zones <= other.zones
        )

    def to_dict(self) -> dict:
        return {key: sorted(getattr(self, key))
                for key in ("classes", "subjects", "purposes", "zones")}


# ---------------------------------------------------------------------------
# Policy, compiled from a domain pack's ``disclosure`` section
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RecipientRule:
    name: str
    classes: frozenset[str]
    purposes: frozenset[str]
    zone: str
    subject_scope: str = "any"          # "any" or "self"


@dataclass(frozen=True)
class DeclassificationRule:
    name: str
    from_classes: frozenset[str]
    to_class: str
    purposes: frozenset[str]
    approval_role: str
    removes_subject_identity: bool


@dataclass(frozen=True)
class BreakGlassRule:
    purposes: frozenset[str]
    max_ttl_seconds: float
    max_unreviewed_per_holder: int
    review_role: str


@dataclass(frozen=True)
class DisclosurePolicy:
    """The declared information-flow policy of one domain pack."""

    subject_kind: str
    purposes: tuple[str, ...]
    field_classes: dict[str, str]
    endpoints: dict[str, str]                 # model endpoint -> zone
    class_zones: dict[str, frozenset[str]]
    recipients: dict[str, RecipientRule]
    declassification: dict[str, DeclassificationRule]
    break_glass: BreakGlassRule | None = None

    @property
    def all_zones(self) -> frozenset[str]:
        zones: set[str] = set(self.endpoints.values())
        for allowed in self.class_zones.values():
            zones |= allowed
        zones |= {rule.zone for rule in self.recipients.values()}
        return frozenset(zones)

    def summary(self) -> dict:
        return {
            "subject_kind": self.subject_kind,
            "purposes": list(self.purposes),
            "fields": len(self.field_classes),
            "classes": sorted(set(self.field_classes.values())),
            "model_endpoints": dict(sorted(self.endpoints.items())),
            "recipients": sorted(self.recipients),
            "declassification_rules": sorted(self.declassification),
            "break_glass": (
                {
                    "purposes": sorted(self.break_glass.purposes),
                    "max_ttl_seconds": self.break_glass.max_ttl_seconds,
                    "max_unreviewed_per_holder": self.break_glass.max_unreviewed_per_holder,
                    "review_role": self.break_glass.review_role,
                }
                if self.break_glass else None
            ),
        }

    @classmethod
    def from_dict(
        cls,
        raw: Any,
        *,
        data_classes: Iterable[str],
        approval_roles: Iterable[str],
    ) -> DisclosurePolicy:
        """Validate a ``disclosure`` section against the rest of its pack.

        The cross-checks are the point. A field whose class the governance block
        never declared, a declassification approved by a role no transition
        names, or a class with no declared processing zone are each a policy that
        reads well and cannot be enforced as written. They fail at load time.
        """
        if not isinstance(raw, dict):
            raise DisclosurePolicyError("disclosure must be a mapping")
        declared_classes = set(data_classes)
        declared_roles = set(approval_roles)

        def text(value: Any, where: str) -> str:
            if not isinstance(value, str) or not value.strip():
                raise DisclosurePolicyError(f"disclosure {where} must be a non-empty string")
            return value.strip()

        def strings(value: Any, where: str, *, allow_empty: bool = False) -> tuple[str, ...]:
            if not isinstance(value, list) or (not value and not allow_empty):
                raise DisclosurePolicyError(f"disclosure {where} must be a non-empty list")
            items = tuple(text(item, where) for item in value)
            if len(set(items)) != len(items):
                raise DisclosurePolicyError(f"disclosure {where} contains duplicates")
            return items

        def mapping(value: Any, where: str) -> dict:
            if not isinstance(value, dict) or not value:
                raise DisclosurePolicyError(f"disclosure {where} must be a non-empty mapping")
            return value

        subject_kind = text(raw.get("subject_kind"), "subject_kind")
        purposes = strings(raw.get("purposes"), "purposes")
        purpose_set = set(purposes)

        def known_purposes(items: tuple[str, ...], where: str) -> frozenset[str]:
            unknown = sorted(set(items) - purpose_set)
            if unknown:
                raise DisclosurePolicyError(
                    f"disclosure {where} names undeclared purposes: {', '.join(unknown)}"
                )
            return frozenset(items)

        def known_class(name: str, where: str) -> str:
            if name not in declared_classes:
                raise DisclosurePolicyError(
                    f"disclosure {where} uses class {name!r}, which governance.data_classes "
                    "does not declare"
                )
            return name

        field_classes: dict[str, str] = {}
        for name, spec in mapping(raw.get("fields"), "fields").items():
            if not isinstance(spec, dict):
                raise DisclosurePolicyError(f"disclosure field {name} must be a mapping")
            field_classes[text(name, "field name")] = known_class(
                text(spec.get("class"), f"field {name} class"), f"field {name}"
            )

        endpoints = {
            text(name, "endpoint name"): text(zone, f"endpoint {name} zone")
            for name, zone in mapping(raw.get("model_endpoints"), "model_endpoints").items()
        }

        class_zones: dict[str, frozenset[str]] = {}
        for name, zones in mapping(raw.get("class_zones"), "class_zones").items():
            class_zones[known_class(text(name, "class_zones key"), "class_zones")] = frozenset(
                strings(zones, f"class_zones.{name}", allow_empty=True)
            )

        recipients: dict[str, RecipientRule] = {}
        for name, spec in mapping(raw.get("recipients"), "recipients").items():
            if not isinstance(spec, dict):
                raise DisclosurePolicyError(f"disclosure recipient {name} must be a mapping")
            scope = spec.get("subject_scope", "any")
            if scope not in {"any", "self"}:
                raise DisclosurePolicyError(
                    f"disclosure recipient {name} subject_scope must be any or self"
                )
            recipients[text(name, "recipient name")] = RecipientRule(
                name=name,
                classes=frozenset(
                    known_class(item, f"recipient {name}")
                    for item in strings(spec.get("classes", []), f"recipient {name} classes",
                                        allow_empty=True)
                ),
                purposes=known_purposes(
                    strings(spec.get("purposes", []), f"recipient {name} purposes",
                            allow_empty=True),
                    f"recipient {name}",
                ),
                zone=text(spec.get("zone"), f"recipient {name} zone"),
                subject_scope=scope,
            )

        declassification: dict[str, DeclassificationRule] = {}
        for index, spec in enumerate(raw.get("declassification", []) or []):
            if not isinstance(spec, dict):
                raise DisclosurePolicyError(f"declassification {index} must be a mapping")
            name = text(spec.get("name"), f"declassification {index} name")
            role = text(spec.get("approval_role"), f"declassification {name} approval_role")
            if role not in declared_roles:
                raise DisclosurePolicyError(
                    f"declassification {name} is approved by {role!r}, which no transition "
                    "declares; a role nobody enforces cannot be the only barrier to disclosure"
                )
            if not isinstance(spec.get("removes_subject_identity"), bool):
                raise DisclosurePolicyError(
                    f"declassification {name} removes_subject_identity must be boolean"
                )
            declassification[name] = DeclassificationRule(
                name=name,
                from_classes=frozenset(
                    known_class(item, f"declassification {name}")
                    for item in strings(spec.get("from_classes"), f"declassification {name} from_classes")
                ),
                to_class=known_class(
                    text(spec.get("to_class"), f"declassification {name} to_class"),
                    f"declassification {name}",
                ),
                purposes=known_purposes(
                    strings(spec.get("purposes"), f"declassification {name} purposes"),
                    f"declassification {name}",
                ),
                approval_role=role,
                removes_subject_identity=spec["removes_subject_identity"],
            )

        break_glass = None
        if raw.get("break_glass") is not None:
            spec = raw["break_glass"]
            if not isinstance(spec, dict):
                raise DisclosurePolicyError("disclosure break_glass must be a mapping")
            role = text(spec.get("review_role"), "break_glass review_role")
            if role not in declared_roles:
                raise DisclosurePolicyError(
                    f"break_glass review_role {role!r} is not declared by any transition; "
                    "an emergency-access review nobody is required to perform is concealment"
                )
            ttl = spec.get("max_ttl_seconds")
            limit = spec.get("max_unreviewed_per_holder")
            if not isinstance(ttl, (int, float)) or isinstance(ttl, bool) or ttl <= 0:
                raise DisclosurePolicyError("break_glass max_ttl_seconds must be positive")
            if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
                raise DisclosurePolicyError(
                    "break_glass max_unreviewed_per_holder must be a positive integer"
                )
            break_glass = BreakGlassRule(
                purposes=known_purposes(strings(spec.get("purposes"), "break_glass purposes"),
                                        "break_glass"),
                max_ttl_seconds=float(ttl),
                max_unreviewed_per_holder=limit,
                review_role=role,
            )

        used_classes = set(field_classes.values()) | {
            rule.to_class for rule in declassification.values()
        }
        missing_zones = sorted(used_classes - set(class_zones))
        if missing_zones:
            raise DisclosurePolicyError(
                "disclosure class_zones must declare where each used class may be processed; "
                f"missing: {', '.join(missing_zones)}"
            )

        return cls(
            subject_kind=subject_kind,
            purposes=purposes,
            field_classes=field_classes,
            endpoints=endpoints,
            class_zones=class_zones,
            recipients=recipients,
            declassification=declassification,
            break_glass=break_glass,
        )


# ---------------------------------------------------------------------------
# Signed grants and declassification approvals
# ---------------------------------------------------------------------------


def _sign(secret: str, payload: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=sorted).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class DisclosureGrant:
    """Purpose-, subject-, field-, class-, holder-, and time-bound entitlement."""

    grant_id: str
    holder: str
    purpose: str
    subjects: frozenset[str]
    fields: frozenset[str]
    classes: frozenset[str]
    issued_by: str
    issued_at: float
    expires_at: float
    basis: str
    break_glass: bool = False
    justification: str = ""
    key_id: str = ""
    signature: str = ""

    def signing_payload(self) -> str:
        return json.dumps({
            "grant_id": self.grant_id, "holder": self.holder, "purpose": self.purpose,
            "subjects": sorted(self.subjects), "fields": sorted(self.fields),
            "classes": sorted(self.classes), "issued_by": self.issued_by,
            "issued_at": self.issued_at, "expires_at": self.expires_at,
            "basis": self.basis, "break_glass": self.break_glass,
            "justification": self.justification, "key_id": self.key_id,
        }, sort_keys=True)

    def to_dict(self) -> dict:
        return {
            "grant_id": self.grant_id, "holder": self.holder, "purpose": self.purpose,
            "subjects": sorted(self.subjects), "fields": sorted(self.fields),
            "classes": sorted(self.classes), "issued_by": self.issued_by,
            "expires_at": self.expires_at, "break_glass": self.break_glass,
            "key_id": self.key_id,
        }


class GrantAuthority:
    """Issues grants under an institution-held key.

    Deliberately permissive about content: it signs what an accountable issuer
    asks it to sign. Whether a signed grant is *sufficient* for a request is
    decided by the gate at the moment of use, against live consent, revocation,
    and endpoint location, which is where that decision has to be made.
    """

    def __init__(self, *, key_id: str = "disclosure-authority-1",
                 secret: str = "teaching-disclosure-key-not-secret") -> None:
        self.key_id = key_id
        self._secret = secret

    @property
    def trusted_keys(self) -> dict[str, str]:
        return {self.key_id: self._secret}

    def issue(
        self, *, grant_id: str, holder: str, purpose: str, subjects: Iterable[str],
        fields: Iterable[str], classes: Iterable[str], issued_by: str, now: float,
        ttl_seconds: float = 3600.0, basis: str = "declared basis",
        break_glass: bool = False, justification: str = "",
    ) -> DisclosureGrant:
        grant = DisclosureGrant(
            grant_id=grant_id, holder=holder, purpose=purpose,
            subjects=frozenset(subjects), fields=frozenset(fields),
            classes=frozenset(classes), issued_by=issued_by, issued_at=now,
            expires_at=now + ttl_seconds, basis=basis, break_glass=break_glass,
            justification=justification, key_id=self.key_id,
        )
        return replace(grant, signature=_sign(self._secret, grant.signing_payload()))


@dataclass(frozen=True)
class DeclassificationApproval:
    """A named person's approval to lower the label of one exact output."""

    output_id: str
    output_digest: str
    rule: str
    approver: str
    approver_role: str
    expires_at: float
    key_id: str = ""
    signature: str = ""

    def signing_payload(self) -> str:
        return json.dumps({
            "output_id": self.output_id, "output_digest": self.output_digest,
            "rule": self.rule, "approver": self.approver,
            "approver_role": self.approver_role, "expires_at": self.expires_at,
            "key_id": self.key_id,
        }, sort_keys=True)


class DeclassificationAuthority:
    """Signs exact-output declassification approvals for authenticated reviewers."""

    def __init__(self, *, key_id: str = "declassification-authority-1",
                 secret: str = "teaching-declassification-key-not-secret") -> None:
        self.key_id = key_id
        self._secret = secret

    @property
    def trusted_keys(self) -> dict[str, str]:
        return {self.key_id: self._secret}

    def approve(self, output: GovernedOutput, *, rule: str, approver: str,
                approver_role: str, now: float, ttl_seconds: float = 900.0,
                ) -> DeclassificationApproval:
        approval = DeclassificationApproval(
            output_id=output.output_id, output_digest=output.digest, rule=rule,
            approver=approver, approver_role=approver_role,
            expires_at=now + ttl_seconds, key_id=self.key_id,
        )
        return replace(approval, signature=_sign(self._secret, approval.signing_payload()))


# ---------------------------------------------------------------------------
# Records, consent, and the objects the gate hands out
# ---------------------------------------------------------------------------


class ConsentRegister:
    """Live consent state. Checked at every release, never cached into a grant."""

    def __init__(self) -> None:
        self._withdrawn: set[tuple[str, str]] = set()
        self._lock = threading.Lock()

    def withdraw(self, subject: str, purpose: str) -> None:
        with self._lock:
            self._withdrawn.add((subject, purpose))

    def restore(self, subject: str, purpose: str) -> None:
        with self._lock:
            self._withdrawn.discard((subject, purpose))

    def permits(self, subject: str, purpose: str) -> bool:
        with self._lock:
            return (subject, purpose) not in self._withdrawn


@dataclass(frozen=True)
class GovernedContext:
    """What the model is allowed to see, with the label it carries."""

    receipt_id: str
    session_id: str
    holder: str
    values: dict[str, str]
    label: DataLabel


@dataclass(frozen=True)
class GovernedOutput:
    """A model output as the gate labelled it. Content is opaque to the gate."""

    output_id: str
    session_id: str
    holder: str
    content: str
    label: DataLabel
    declassified_by: str = ""

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ReleaseReceipt:
    receipt_id: str
    output_id: str
    recipient: str
    purpose: str
    label: DataLabel


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------


@dataclass
class _Session:
    holder: str
    label: DataLabel
    released_values: set[str] = field(default_factory=set)


class DisclosureGate:
    """The policy enforcement point for every read and every release.

    The gate holds the record store. A model runtime holds none of it and can
    obtain protected values only through :meth:`assemble_context`. Every attempt,
    released or refused, writes an intent record before any check and an outcome
    record after; if the intent cannot be written, nothing is released. Evidence
    records carry field names, subjects, codes, and digests, never the protected
    values themselves: a disclosure log that reproduces the disclosure is a
    second copy of the data under weaker control.
    """

    def __init__(
        self,
        policy: DisclosurePolicy,
        records: dict[str, dict[str, str]],
        evidence: EvidenceLedger,
        evidence_token: str,
        *,
        grant_keys: dict[str, str],
        declassification_keys: dict[str, str] | None = None,
        consent: ConsentRegister | None = None,
        enforce: Iterable[str] = ALL_CHECKS,
    ) -> None:
        self.policy = policy
        self._records = {subject: dict(fields) for subject, fields in records.items()}
        self._evidence = evidence
        self._token = evidence_token
        self._grant_keys = dict(grant_keys)
        self._declassification_keys = dict(declassification_keys or {})
        self.consent = consent or ConsentRegister()
        self.enforce = frozenset(enforce)
        unknown = sorted(self.enforce - set(ALL_CHECKS))
        if unknown:
            raise ValueError(f"unknown disclosure checks: {', '.join(unknown)}")
        self._revoked: set[str] = set()
        self._sessions: dict[str, _Session] = {}
        self._outputs: dict[str, GovernedOutput] = {}
        self._open_break_glass: dict[str, str] = {}     # grant_id -> holder
        self._seen_break_glass: set[str] = set()
        self._sequence = 0
        self._lock = threading.RLock()

    # -- helpers -------------------------------------------------------------
    def _on(self, check: str) -> bool:
        return check in self.enforce

    def _next(self, prefix: str) -> str:
        self._sequence += 1
        return f"{prefix}-{self._sequence}"

    def _record(self, kind: str, payload: dict) -> None:
        self._evidence.append(kind, payload, token=self._token)

    def _guarded(self, kind: str, intent: dict, body: Callable[[], Any],
                 describe: Callable[[Any], dict]) -> Any:
        """Intent, then the decision, then the outcome. No intent, no release."""
        attempt = self._next("attempt")
        try:
            self._record(f"{kind}_intent", {"attempt": attempt, **intent})
        except EvidenceError as exc:
            raise DisclosureDenied(
                DisclosureCode.EVIDENCE_UNAVAILABLE,
                f"intent evidence could not be written; nothing released ({exc})",
            ) from exc
        try:
            result = body()
        except DisclosureDenied as denied:
            self._record(f"{kind}_outcome", {
                "attempt": attempt, "released": False, "code": denied.code,
            })
            raise
        self._record(f"{kind}_outcome", {"attempt": attempt, "released": True,
                                         **describe(result)})
        return result

    # -- records and outputs ---------------------------------------------------
    def load_records(self, subject: str, fields: dict[str, str], *, loaded_by: str) -> list[str]:
        """Place synthetic or adapter-supplied values behind the gate.

        Only declared fields are accepted. The evidence record names the subject
        and field names and never the values.
        """
        if not isinstance(subject, str) or not subject.strip():
            raise DisclosureDenied(DisclosureCode.SUBJECT_NOT_FOUND, "a subject is required")
        undeclared = sorted(set(fields) - set(self.policy.field_classes))
        if undeclared:
            raise DisclosureDenied(DisclosureCode.FIELD_UNDECLARED,
                                   f"undeclared fields: {', '.join(undeclared)}")
        with self._lock:
            self._records.setdefault(subject, {}).update(
                {name: str(value) for name, value in fields.items()})
            names = sorted(fields)
            self._record("disclosure_records_loaded",
                         {"subject": subject, "fields": names, "loaded_by": loaded_by})
            return names

    def output(self, output_id: str) -> GovernedOutput:
        with self._lock:
            known = self._outputs.get(output_id)
        if known is None:
            raise DisclosureDenied(DisclosureCode.OUTPUT_UNKNOWN, f"no output {output_id!r}")
        return known

    # -- grant lifecycle -----------------------------------------------------
    def revoke_grant(self, grant_id: str, *, by: str, reason: str) -> None:
        with self._lock:
            self._revoked.add(grant_id)
            self._record("disclosure_grant_revoked",
                         {"grant_id": grant_id, "by": by, "reason": reason})

    def withdraw_consent(self, subject: str, purpose: str, *, recorded_by: str) -> None:
        with self._lock:
            self.consent.withdraw(subject, purpose)
            self._record("consent_withdrawn", {"subject": subject, "purpose": purpose,
                                               "recorded_by": recorded_by})

    @property
    def open_break_glass(self) -> dict[str, str]:
        return dict(self._open_break_glass)

    def record_break_glass_review(self, grant_id: str, *, reviewer: str,
                                  reviewer_role: str, finding: str) -> None:
        with self._lock:
            holder = self._open_break_glass.get(grant_id)
            rule = self.policy.break_glass
            if holder is None or rule is None:
                raise DisclosureDenied(DisclosureCode.REVIEW_NOT_PERMITTED,
                                       "no open break-glass obligation for this grant")
            if reviewer_role != rule.review_role:
                raise DisclosureDenied(DisclosureCode.REVIEW_NOT_PERMITTED,
                                       f"break-glass review requires {rule.review_role}")
            if reviewer == holder:
                raise DisclosureDenied(DisclosureCode.REVIEW_NOT_PERMITTED,
                                       "the holder cannot review their own emergency access")
            del self._open_break_glass[grant_id]
            self._record("break_glass_reviewed", {
                "grant_id": grant_id, "holder": holder, "reviewer": reviewer,
                "reviewer_role": reviewer_role, "finding": finding,
            })

    # -- read path -----------------------------------------------------------
    def assemble_context(
        self, *, requester: str, session_id: str, grant: DisclosureGrant | None,
        purpose: str, subjects: Iterable[str], fields: Iterable[str],
        model_endpoint: str, now: float,
    ) -> GovernedContext:
        subjects = tuple(sorted(set(subjects)))
        fields = tuple(sorted(set(fields)))
        intent = {
            "requester": requester, "session_id": session_id,
            "grant_id": grant.grant_id if grant else None, "purpose": purpose,
            "subjects": list(subjects), "fields": list(fields),
            "model_endpoint": model_endpoint,
        }
        with self._lock:
            return self._guarded(
                "disclosure", intent,
                lambda: self._assemble(requester, session_id, grant, purpose,
                                       subjects, fields, model_endpoint, now),
                lambda ctx: {
                    "receipt_id": ctx.receipt_id, "label": ctx.label.to_dict(),
                    "values_digest": _digest(sorted(ctx.values.items())),
                    "value_count": len(ctx.values),
                },
            )

    def _deny(self, code: str, detail: str) -> DisclosureDenied:
        return DisclosureDenied(code, detail)

    def _assemble(self, requester, session_id, grant, purpose, subjects, fields,
                  model_endpoint, now) -> GovernedContext:
        policy = self.policy
        if grant is None:
            raise self._deny(DisclosureCode.GRANT_NOT_SUPPLIED, "no grant presented")

        # Structural: nothing undeclared can be released by any configuration.
        for name in fields:
            if name not in policy.field_classes:
                raise self._deny(DisclosureCode.FIELD_UNDECLARED, f"field {name} is undeclared")
        for subject in subjects:
            if subject not in self._records:
                raise self._deny(DisclosureCode.SUBJECT_NOT_FOUND, f"no record for {subject}")
        if not subjects or not fields:
            raise self._deny(DisclosureCode.FIELD_NOT_MINIMUM_NECESSARY,
                             "a request must name its subjects and fields; there is no 'all'")

        if self._on("grant_signature"):
            secret = self._grant_keys.get(grant.key_id)
            if secret is None:
                raise self._deny(DisclosureCode.GRANT_KEY_UNTRUSTED,
                                 f"grant key {grant.key_id!r} is not trusted")
            if not hmac.compare_digest(_sign(secret, grant.signing_payload()), grant.signature):
                raise self._deny(DisclosureCode.GRANT_SIGNATURE_INVALID,
                                 "grant fields do not match their signature")

        if self._on("holder_binding"):
            if grant.holder != requester:
                raise self._deny(DisclosureCode.GRANT_HOLDER_MISMATCH,
                                 "the grant names a different holder; grants are not bearer tokens")
            if grant.issued_by == grant.holder and not grant.break_glass:
                raise self._deny(DisclosureCode.GRANT_SELF_ISSUED,
                                 "a holder cannot issue their own non-emergency grant")
            existing = self._sessions.get(session_id)
            if existing is not None and existing.holder != requester:
                raise self._deny(DisclosureCode.SESSION_HOLDER_MISMATCH,
                                 "the session belongs to another principal")

        if self._on("grant_currency"):
            if grant.grant_id in self._revoked:
                raise self._deny(DisclosureCode.GRANT_REVOKED, "grant has been revoked")
            if now >= grant.expires_at:
                raise self._deny(DisclosureCode.GRANT_EXPIRED, "grant has expired")

        if self._on("purpose_binding"):
            if purpose not in policy.purposes:
                raise self._deny(DisclosureCode.PURPOSE_UNDECLARED,
                                 f"purpose {purpose!r} is not declared by the domain pack")
            if purpose != grant.purpose:
                raise self._deny(DisclosureCode.PURPOSE_MISMATCH,
                                 f"grant is for {grant.purpose!r}, request is for {purpose!r}")

        if self._on("subject_scope"):
            outside = sorted(set(subjects) - grant.subjects)
            if outside:
                raise self._deny(DisclosureCode.SUBJECT_OUT_OF_SCOPE,
                                 f"subjects outside the grant: {', '.join(outside)}")

        if self._on("minimum_necessary"):
            outside = sorted(set(fields) - grant.fields)
            if outside:
                raise self._deny(DisclosureCode.FIELD_NOT_MINIMUM_NECESSARY,
                                 f"fields outside the grant: {', '.join(outside)}")

        if self._on("consent"):
            for subject in subjects:
                if not self.consent.permits(subject, purpose):
                    raise self._deny(DisclosureCode.CONSENT_WITHDRAWN,
                                     f"{subject} does not currently permit {purpose}")

        classes = {policy.field_classes[name] for name in fields}
        if self._on("class_clearance"):
            outside = sorted(classes - grant.classes)
            if outside:
                raise self._deny(DisclosureCode.CLASS_NOT_CLEARED,
                                 f"classes outside the grant: {', '.join(outside)}")

        if self._on("residency"):
            zone = policy.endpoints.get(model_endpoint)
            if zone is None:
                raise self._deny(DisclosureCode.ENDPOINT_UNDECLARED,
                                 f"model endpoint {model_endpoint!r} has no declared zone")
            blocked = sorted(c for c in classes if zone not in policy.class_zones.get(c, ()))
            if blocked:
                raise self._deny(DisclosureCode.RESIDENCY_VIOLATION,
                                 f"zone {zone!r} may not process: {', '.join(blocked)}")

        if grant.break_glass and self._on("break_glass"):
            rule = policy.break_glass
            if rule is None:
                raise self._deny(DisclosureCode.BREAK_GLASS_NOT_PERMITTED,
                                 "this domain pack declares no emergency access")
            if grant.purpose not in rule.purposes:
                raise self._deny(DisclosureCode.BREAK_GLASS_PURPOSE,
                                 f"break-glass is not permitted for {grant.purpose!r}")
            if grant.expires_at - grant.issued_at > rule.max_ttl_seconds:
                raise self._deny(DisclosureCode.BREAK_GLASS_TOO_LONG,
                                 "emergency access longer than the declared maximum")
            if not grant.justification.strip():
                raise self._deny(DisclosureCode.BREAK_GLASS_UNJUSTIFIED,
                                 "emergency access requires a recorded justification")
            unreviewed = sum(
                1 for gid, holder in self._open_break_glass.items()
                if holder == grant.holder and gid != grant.grant_id
            )
            if unreviewed >= rule.max_unreviewed_per_holder:
                raise self._deny(DisclosureCode.BREAK_GLASS_REVIEW_OVERDUE,
                                 f"{unreviewed} earlier emergency access(es) still unreviewed")

        # Release: the label is computed here, from policy, never supplied.
        values: dict[str, str] = {}
        label = DataLabel.bottom(policy)
        for subject in subjects:
            for name in fields:
                cls = policy.field_classes[name]
                values[f"{subject}.{name}"] = self._records[subject].get(name, "")
                label = label.join(DataLabel(
                    classes=frozenset({cls}), subjects=frozenset({subject}),
                    purposes=frozenset({purpose}),
                    zones=frozenset(policy.class_zones.get(cls, frozenset())),
                ))

        session = self._sessions.get(session_id)
        if session is None:
            session = self._sessions[session_id] = _Session(requester, DataLabel.bottom(policy))
        session.label = session.label.join(label)
        session.released_values.update(v for v in values.values() if v)

        if grant.break_glass and grant.grant_id not in self._seen_break_glass:
            self._seen_break_glass.add(grant.grant_id)
            self._open_break_glass[grant.grant_id] = grant.holder
            self._record("break_glass_review_due", {
                "grant_id": grant.grant_id, "holder": grant.holder,
                "purpose": grant.purpose, "justification_digest": _digest(grant.justification),
                "review_role": policy.break_glass.review_role if policy.break_glass else None,
            })

        return GovernedContext(self._next("context"), session_id, requester, values, label)

    # -- derivation ----------------------------------------------------------
    def derive_output(self, *, requester: str, session_id: str, content: str,
                      claimed_label: DataLabel | None = None) -> GovernedOutput:
        """Label a model output. The session's label wins over any claim."""
        with self._lock:
            session = self._sessions.get(session_id)
            bottom = DataLabel.bottom(self.policy)
            if self._on("session_taint"):
                if session is not None and session.holder != requester:
                    raise DisclosureDenied(DisclosureCode.SESSION_HOLDER_MISMATCH,
                                           "the session belongs to another principal")
                label = session.label if session else bottom
            else:
                label = claimed_label if claimed_label is not None else bottom
            output = GovernedOutput(self._next("output"), session_id, requester, content, label)
            self._outputs[output.output_id] = output
            downgrade = claimed_label is not None and not claimed_label.dominates(label)
            self._record("output_labelled", {
                "output_id": output.output_id, "session_id": session_id,
                "holder": requester, "content_digest": output.digest,
                "label": label.to_dict(),
                "claimed_label": claimed_label.to_dict() if claimed_label else None,
                "claimed_downgrade_attempt": downgrade,
            })
            return output

    def _issued(self, output: GovernedOutput) -> GovernedOutput:
        known = self._outputs.get(output.output_id)
        if known is None or known.digest != output.digest or known.label != output.label:
            raise DisclosureDenied(DisclosureCode.OUTPUT_UNKNOWN,
                                   "output was not issued by this gate or was altered")
        return known

    # -- declassification ----------------------------------------------------
    def declassify(self, output: GovernedOutput, *, rule: str,
                   approval: DeclassificationApproval | None, now: float) -> GovernedOutput:
        intent = {"output_id": output.output_id, "rule": rule,
                  "approver": approval.approver if approval else None}
        with self._lock:
            return self._guarded(
                "declassification", intent,
                lambda: self._declassify(output, rule, approval, now),
                lambda out: {"new_output_id": out.output_id, "label": out.label.to_dict(),
                             "approved_by": out.declassified_by},
            )

    def _declassify(self, output, rule_name, approval, now) -> GovernedOutput:
        known = self._issued(output)
        rule = self.policy.declassification.get(rule_name)
        if rule is None:
            raise DisclosureDenied(DisclosureCode.DECLASSIFICATION_RULE_UNKNOWN,
                                   f"no declassification rule {rule_name!r}")
        approved_by = approval.approver if approval else ""
        if self._on("exact_output_declassification"):
            if approval is None:
                raise DisclosureDenied(DisclosureCode.DECLASSIFICATION_NOT_APPROVED,
                                       "lowering a label requires an exact-output approval")
            secret = self._declassification_keys.get(approval.key_id)
            if secret is None or not hmac.compare_digest(
                _sign(secret, approval.signing_payload()), approval.signature
            ):
                raise DisclosureDenied(DisclosureCode.DECLASSIFICATION_SIGNATURE_INVALID,
                                       "approval signature is invalid or its key untrusted")
            if approval.output_id != known.output_id or approval.output_digest != known.digest \
                    or approval.rule != rule.name:
                raise DisclosureDenied(DisclosureCode.DECLASSIFICATION_WRONG_OUTPUT,
                                       "approval is for a different output or rule")
            if approval.approver_role != rule.approval_role:
                raise DisclosureDenied(DisclosureCode.DECLASSIFICATION_WRONG_ROLE,
                                       f"rule {rule.name} requires {rule.approval_role}")
            if approval.approver == known.holder:
                raise DisclosureDenied(DisclosureCode.DECLASSIFICATION_SELF_APPROVED,
                                       "the output's holder cannot declassify it")
            if now >= approval.expires_at:
                raise DisclosureDenied(DisclosureCode.DECLASSIFICATION_EXPIRED,
                                       "declassification approval has expired")
            if not known.label.classes <= (rule.from_classes | {rule.to_class}):
                raise DisclosureDenied(DisclosureCode.DECLASSIFICATION_OUT_OF_RULE,
                                       "output carries classes this rule may not lower")
            if not (known.label.purposes & rule.purposes):
                raise DisclosureDenied(DisclosureCode.DECLASSIFICATION_OUT_OF_RULE,
                                       "output purposes do not include this rule's purposes")

        # The gate applies the transform. Redaction of released values and
        # subject identifiers is a floor, not de-identification.
        session = self._sessions.get(known.session_id)
        content = known.content
        for value in sorted(session.released_values if session else (), key=len, reverse=True):
            content = content.replace(value, "[withheld]")
        subjects = known.label.subjects
        if rule.removes_subject_identity:
            # The pseudonym must not be able to reproduce an identifier: an earlier
            # form, "[patient-1]", re-created the subject id "patient-1" verbatim.
            for index, subject in enumerate(sorted(subjects, key=len, reverse=True), start=1):
                content = content.replace(subject, f"[{self.policy.subject_kind} withheld #{index}]")
            if any(subject in content for subject in subjects):
                raise DisclosureDenied(DisclosureCode.DECLASSIFICATION_OUT_OF_RULE,
                                       "a subject identifier survived redaction")
            subjects = frozenset()
        label = DataLabel(
            classes=frozenset({rule.to_class}), subjects=subjects,
            purposes=known.label.purposes & rule.purposes,
            zones=frozenset(self.policy.class_zones.get(rule.to_class, frozenset())),
        )
        new = GovernedOutput(self._next("output"), f"{known.session_id}/declassified",
                             known.holder, content, label, declassified_by=approved_by)
        self._outputs[new.output_id] = new
        return new

    # -- release path --------------------------------------------------------
    def release(self, output: GovernedOutput, *, recipient: str, recipient_id: str = "",
                purpose: str, now: float) -> ReleaseReceipt:
        intent = {"output_id": output.output_id, "recipient": recipient, "purpose": purpose}
        with self._lock:
            return self._guarded(
                "release", intent,
                lambda: self._release(output, recipient, recipient_id, purpose),
                lambda receipt: {"receipt_id": receipt.receipt_id,
                                 "label": receipt.label.to_dict()},
            )

    def _release(self, output, recipient, recipient_id, purpose) -> ReleaseReceipt:
        known = self._issued(output)
        rule = self.policy.recipients.get(recipient)
        if rule is None:
            raise DisclosureDenied(DisclosureCode.RECIPIENT_UNDECLARED,
                                   f"recipient {recipient!r} is not declared")
        label = known.label
        if self._on("recipient_clearance"):
            outside = sorted(label.classes - rule.classes)
            if outside:
                raise DisclosureDenied(DisclosureCode.RECIPIENT_CLASS_NOT_CLEARED,
                                       f"{recipient} is not cleared for: {', '.join(outside)}")
            if purpose not in rule.purposes or purpose not in label.purposes:
                raise DisclosureDenied(DisclosureCode.RECIPIENT_PURPOSE_NOT_PERMITTED,
                                       f"{purpose!r} is not permitted for this output and recipient")
            if rule.zone not in label.zones:
                raise DisclosureDenied(DisclosureCode.RECIPIENT_ZONE_NOT_PERMITTED,
                                       f"zone {rule.zone!r} may not receive this output")
            if rule.subject_scope == "self" and not label.subjects <= {recipient_id}:
                raise DisclosureDenied(DisclosureCode.RECIPIENT_SUBJECT_NOT_PERMITTED,
                                       "recipient may receive only their own records")
        return ReleaseReceipt(self._next("release"), known.output_id, recipient, purpose, label)


__all__ = [
    "ALL_CHECKS", "BreakGlassRule", "ConsentRegister", "DataLabel",
    "DeclassificationApproval", "DeclassificationAuthority", "DeclassificationRule",
    "DisclosureCode", "DisclosureDenied", "DisclosureGate", "DisclosureGrant",
    "DisclosurePolicy", "DisclosurePolicyError", "GovernedContext", "GovernedOutput",
    "GrantAuthority", "RecipientRule", "ReleaseReceipt",
]
