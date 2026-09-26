"""Education policy pack: FERPA release rules and a stricter mandate for minors.

The sealed-release gate answers "is this recipient cleared for every label the
output was built from?". For US education records the clearance table is not a
matter of taste: the Family Educational Rights and Privacy Act (20 U.S.C.
1232g) and its regulations (34 CFR Part 99) say who holds the rights, which
disclosures need written consent, which do not, which must be recorded, and how
long an institution has to answer. This module encodes those provisions as a
decision function whose every answer names its basis, so a registrar and
counsel can review the table line by line and the refusal suite can test it.

It separates two sources of rule, and every decision says which applied:

* ``law`` -- a provision of 34 CFR Part 99, cited by section;
* ``institution`` -- a stricter local mandate this pack adds for minors
  (dual approval, shorter grants, named recipients only). FERPA sets a floor;
  an institution may do more, and a child's record is where it should.

The pack covers the disclosure paths an AI workflow actually meets. Paths it
does not model (subpoenas, audits under 99.35, studies under 99.31(a)(6), and
so on) are refused with ``FERPA_PATH_NOT_MODELLED`` and routed to a person,
never silently allowed. A registrar and counsel validate the table before use.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

DIRECTORY = "directory"
NON_DIRECTORY = "non_directory"
RECORD_CLASSES = (DIRECTORY, NON_DIRECTORY)

REQUESTERS = ("parent", "student", "school_official", "other_school", "emergency",
              "third_party", "other")

#: 34 CFR 99.10(b): access within a reasonable time, not more than 45 days.
ACCESS_DEADLINE_DAYS = 45
#: Institutional service levels. FERPA says "reasonable time" (99.20(b), 99.22);
#: these defaults are the pack's, and an institution sets its own.
AMENDMENT_DECISION_DAYS = 30
HEARING_DAYS = 45
#: Institutional mandate for minors.
MINOR_MAX_GRANT_DAYS = 7
ADULT_MAX_GRANT_DAYS = 30


@dataclass(frozen=True)
class Student:
    id: str
    age: int
    postsecondary: bool = False
    directory_opt_out: bool = False
    #: Claimed as a dependant for tax purposes (26 U.S.C. 152) by the parent asking.
    tax_dependent_of_requester: bool = False
    #: Portions under an amendment dispute with a statement on file (99.21(b)(2)).
    contested_portions: frozenset[str] = frozenset()

    @property
    def eligible(self) -> bool:
        """99.3 / 99.5: rights transfer at 18 or on attending postsecondary."""
        return self.age >= 18 or self.postsecondary

    @property
    def minor(self) -> bool:
        return self.age < 18


@dataclass(frozen=True)
class Consent:
    """99.30: signed and dated, naming the records, the purpose and the recipient."""
    signed_by: str                # "parent" or "student"
    records: frozenset[str]
    purpose: str
    recipient: str
    signed_on: date
    revoked: bool = False


@dataclass(frozen=True)
class Request:
    requester: str
    recipient: str
    record_class: str
    records: frozenset[str]
    purpose: str
    legitimate_educational_interest: bool = False
    #: 99.31(a)(2): the student seeks or intends to enrol at the other school.
    student_enrolling: bool = False
    #: 99.36: an articulable and significant threat to health or safety.
    articulable_threat: str = ""
    consent: Consent | None = None
    approvers: tuple[str, ...] = ()
    grant_days: int = 1
    #: The release carries the student's statement for contested portions.
    includes_statements: bool = False


@dataclass(frozen=True)
class Decision:
    allowed: bool
    code: str
    basis: str
    source: str                       # "law" or "institution"
    rights_holder: str
    record_required: bool = False     # 99.32 record of disclosure is mandatory
    obligations: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {"allowed": self.allowed, "code": self.code, "basis": self.basis,
                "source": self.source, "rights_holder": self.rights_holder,
                "record_required": self.record_required,
                "obligations": list(self.obligations)}


def rights_holder(student: Student) -> str:
    return "student" if student.eligible else "parent"


def _refuse(code: str, basis: str, holder: str, source: str = "law") -> Decision:
    return Decision(False, code, basis, source, holder)


def _minor_mandate(student: Student, request: Request, holder: str) -> Decision | None:
    """The stricter institutional rules for a child's non-directory record."""
    if not student.minor or request.record_class != NON_DIRECTORY:
        return None
    if request.requester in ("parent", "student"):
        return None                   # a family reading its own record needs no second key
    if request.recipient in ("*", "any", ""):
        return _refuse("MINOR_RECIPIENT_NOT_NAMED",
                       "a child's record goes only to a named recipient", holder, "institution")
    if request.grant_days > MINOR_MAX_GRANT_DAYS:
        return _refuse("MINOR_GRANT_TOO_LONG",
                       f"grants on a child's record last at most {MINOR_MAX_GRANT_DAYS} days",
                       holder, "institution")
    if len(set(request.approvers)) < 2 and request.requester != "emergency":
        return _refuse("MINOR_DUAL_APPROVAL_REQUIRED",
                       "two distinct approvers release a child's record", holder, "institution")
    return None


def decide(student: Student, request: Request) -> Decision:
    """May ``request`` receive these records of ``student``, and on what basis?"""
    if request.record_class not in RECORD_CLASSES:
        raise ValueError(f"unknown record class {request.record_class!r}")
    if request.requester not in REQUESTERS:
        raise ValueError(f"unknown requester {request.requester!r}")
    holder = rights_holder(student)
    if request.grant_days > ADULT_MAX_GRANT_DAYS:
        return _refuse("GRANT_TOO_LONG", f"grants last at most {ADULT_MAX_GRANT_DAYS} days",
                       holder, "institution")
    contested = request.records & student.contested_portions
    if contested and not request.includes_statements:
        return _refuse("FERPA_STATEMENT_MISSING",
                       "34 CFR 99.21(c): a contested portion is disclosed with the "
                       "student's statement", holder)
    mandate = _minor_mandate(student, request, holder)
    if mandate:
        return mandate

    # The rights holder reading their own (or their child's) record.
    if request.requester == holder:
        return Decision(True, "FERPA_ACCESS_RIGHT", "34 CFR 99.10: right to inspect and review",
                        "law", holder,
                        obligations=(f"respond within {ACCESS_DEADLINE_DAYS} days (99.10(b))",))
    if request.requester == "parent":         # the student is eligible
        if student.tax_dependent_of_requester:
            return Decision(True, "FERPA_DEPENDENT_PARENT",
                            "34 CFR 99.31(a)(8): parent of a tax-dependent eligible student",
                            "law", holder, record_required=True)
        return _refuse("FERPA_RIGHTS_TRANSFERRED",
                       "34 CFR 99.5: rights passed to the eligible student", holder)
    if request.requester == "student":         # a minor who is not yet the holder
        return _refuse("FERPA_NOT_RIGHTS_HOLDER",
                       "34 CFR 99.3: the parent holds the rights until eligibility", holder)
    if request.record_class == DIRECTORY and not student.directory_opt_out:
        return Decision(True, "FERPA_DIRECTORY", "34 CFR 99.31(a)(11), 99.37: directory "
                        "information, no opt-out on file", "law", holder)
    if request.requester == "school_official":
        if request.legitimate_educational_interest:
            return Decision(True, "FERPA_SCHOOL_OFFICIAL",
                            "34 CFR 99.31(a)(1): school official, legitimate educational "
                            "interest", "law", holder)
        return _refuse("FERPA_NO_LEGITIMATE_INTEREST",
                       "34 CFR 99.31(a)(1) requires a legitimate educational interest", holder)
    if request.requester == "other_school" and request.student_enrolling:
        return Decision(True, "FERPA_TRANSFER",
                        "34 CFR 99.31(a)(2), 99.34: school where the student seeks to enrol",
                        "law", holder, record_required=True,
                        obligations=("make a reasonable attempt to notify, unless the annual "
                                     "notice covers transfers (99.34(a)(1))",))
    if request.requester == "emergency":
        if request.articulable_threat.strip():
            return Decision(True, "FERPA_HEALTH_SAFETY",
                            "34 CFR 99.36: articulable and significant threat", "law", holder,
                            record_required=True,
                            obligations=("record the threat and the parties told (99.32(a)(5))",))
        return _refuse("FERPA_THREAT_NOT_ARTICULATED",
                       "34 CFR 99.36 needs an articulable and significant threat", holder)
    consent = request.consent
    if consent is not None:
        problems = []
        if consent.revoked:
            problems.append("revoked")
        if consent.signed_by != holder:
            problems.append(f"signed by {consent.signed_by}, rights holder is {holder}")
        if not request.records <= consent.records:
            problems.append("records exceed the consent")
        if consent.recipient != request.recipient:
            problems.append("recipient differs from the consent")
        if consent.purpose != request.purpose:
            problems.append("purpose differs from the consent")
        if problems:
            return _refuse("FERPA_CONSENT_INVALID", "34 CFR 99.30: " + "; ".join(problems),
                           holder)
        return Decision(True, "FERPA_CONSENT", "34 CFR 99.30: written consent", "law", holder,
                        obligations=("give the holder a copy on request (99.30(c))",))
    if request.requester == "third_party":
        return _refuse("FERPA_CONSENT_REQUIRED",
                       "34 CFR 99.30: written consent is required", holder)
    return _refuse("FERPA_PATH_NOT_MODELLED",
                   "this disclosure path is not in the pack; route to the registrar", holder)


@dataclass(frozen=True)
class AmendmentCase:
    """34 CFR 99.20-99.22: request, decision, hearing, statement."""
    received: date

    def decision_due(self) -> date:
        return self.received + timedelta(days=AMENDMENT_DECISION_DAYS)

    def hearing_due(self, requested: date) -> date:
        return requested + timedelta(days=HEARING_DAYS)

    @staticmethod
    def after_refusal() -> tuple[str, ...]:
        return ("tell the holder of the decision and of the right to a hearing (99.20(c))",
                "if the hearing upholds the record, tell the holder they may place a "
                "statement in it (99.21(b)(2))",
                "keep the statement with the contested portion and disclose it whenever "
                "that portion is disclosed (99.21(c))")


# The table a registrar reviews: one row per disclosure path, and its source.
POLICY_TABLE = (
    ("rights holder inspects own record", "99.10", "law", "allowed; 45-day deadline"),
    ("parent of eligible student", "99.5, 99.31(a)(8)", "law",
     "refused unless tax dependant"),
    ("minor student requests own record", "99.3", "law", "refused; parent holds rights"),
    ("directory information, no opt-out", "99.31(a)(11), 99.37", "law", "allowed"),
    ("directory information, opted out", "99.37", "law", "consent required"),
    ("school official with legitimate interest", "99.31(a)(1)", "law", "allowed"),
    ("school official without legitimate interest", "99.31(a)(1)", "law", "refused"),
    ("school where the student enrols", "99.31(a)(2), 99.34", "law", "allowed; recorded"),
    ("health or safety emergency", "99.36", "law", "allowed only with articulated threat"),
    ("third party with valid written consent", "99.30", "law", "allowed"),
    ("third party without consent", "99.30", "law", "refused"),
    ("contested portion without statement", "99.21(c)", "law", "refused"),
    ("child's record: second approver", "-", "institution", "two distinct approvers"),
    ("child's record: grant length", "-", "institution",
     f"at most {MINOR_MAX_GRANT_DAYS} days"),
    ("child's record: recipient", "-", "institution", "named recipient only"),
    ("any other path", "-", "institution", "refused; routed to the registrar"),
)


__all__ = ["ACCESS_DEADLINE_DAYS", "AmendmentCase", "Consent", "DIRECTORY", "Decision",
           "NON_DIRECTORY", "POLICY_TABLE", "Request", "Student", "decide", "rights_holder"]
