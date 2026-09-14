"""One governed request in ten steps, traced so an audience can follow it.

    1 ADMIT      boundary        who is asking, and is the input authentic?
    2 PROTECT    data            what is this data, and is it encrypted and tokenized?
    3 ROUTE      intelligence    which model is suggested? (advisory only)
    4 ENTITLE    context gate    is this model attested, and may this holder see these fields?
    5 REASON     intelligence    what did the model propose? (untrusted)
    6 AUTHORIZE  authority       did a named human with the right role approve this exact proposal?
    7 EXECUTE    execution       did the executor recheck everything and make one write?
    8 RELEASE    release gate    may this recipient see the result, and see who it concerns?
    9 RECORD     evidence        is the history intact and signed?
   10 RECOVER    resilience      what happens now if something is revoked or fails?

:func:`run_governed_request` drives a real request through the education world with a
chosen model, and stops at the first refusal. Steps after a refusal still run RECORD and
RECOVER, because failure must be evidenced and routed, never silently turned into success.
:func:`explain` then turns the trace into the system-literacy questions a student, an
educator, or a policymaker should be able to answer about any AI decision.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .custody_errors import DENIALS, denial_code
from .education_models import HonestAssistant
from .education_world import PEOPLE, EducationWorld
from .evidence_notary import verify_receipt

STEPS = (
    (1, "ADMIT", "boundary", "Is the caller known and the input authentic?"),
    (2, "PROTECT", "data", "Is the data classified, encrypted at rest, and tokenized for the model?"),
    (3, "ROUTE", "intelligence", "Which model does the router suggest? (a suggestion, not a decision)"),
    (4, "ENTITLE", "context gate", "Is the model attested and the holder entitled to these fields?"),
    (5, "REASON", "intelligence", "What does the model propose? (untrusted output)"),
    (6, "AUTHORIZE", "authority", "Did a named human with the right role approve this exact proposal?"),
    (7, "EXECUTE", "execution mediator", "Did the executor recheck and make exactly one write?"),
    (8, "RELEASE", "release gate", "May this recipient see the result, and see who it concerns?"),
    (9, "RECORD", "evidence", "Is the history intact, signed, and free of protected values?"),
    (10, "RECOVER", "resilience", "If authority is withdrawn now, does the system fail closed?"),
)


@dataclass
class TraceStep:
    number: int
    name: str
    plane: str
    question: str
    status: str = "SKIPPED"          # ALLOWED, DENIED, SKIPPED, INFO
    decided_by: str = ""
    code: str = ""
    detail: str = ""
    evidence: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"step": self.number, "name": self.name, "plane": self.plane, "question": self.question,
                "status": self.status, "decided_by": self.decided_by, "code": self.code,
                "detail": self.detail, "evidence": self.evidence}


@dataclass
class RequestTrace:
    scenario: str
    model: str
    steps: list[TraceStep]
    outcome: str = ""
    facts: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"scenario": self.scenario, "model": self.model, "outcome": self.outcome,
                "steps": [s.to_dict() for s in self.steps], "facts": self.facts}

    def render(self) -> str:
        lines = [f"GOVERNED REQUEST · {self.scenario} · model: {self.model}"]
        for step in self.steps:
            mark = {"ALLOWED": "✓", "DENIED": "✕", "INFO": "•", "SKIPPED": "·"}[step.status]
            lines.append(f"  {step.number:>2} {mark} {step.name:<9} [{step.plane}] {step.code or step.status}"
                         + (f" — {step.detail}" if step.detail else ""))
            if step.number < len(self.steps):
                lines.append("       ↓")
        lines.append(f"  OUTCOME: {self.outcome}")
        return "\n".join(lines)


def run_governed_request(world: EducationWorld | None = None, *, model: Any = None,
                         scenario: str = "support-and-correction",
                         requester: str = "support-agent", reviewer: str = "dr-lin",
                         student: str = "stu-a1f3", target_grade: str = "grade:B",
                         fields: tuple[str, ...] = ("student_name", "attendance_rate", "current_grades"),
                         recipient: str = "academic_advisor", document: str | None = None,
                         document_source: str = "registrar-feed", sign_document: bool = True) -> RequestTrace:
    world = world or EducationWorld()
    model = model or HonestAssistant()
    steps = [TraceStep(n, name, plane, question) for n, name, plane, question in STEPS]
    trace = RequestTrace(scenario, getattr(model, "name", type(model).__name__), steps)
    facts: dict = {"who": requester, "student": student, "reviewer": reviewer, "recipient": recipient}
    by = {s.name: s for s in steps}
    purpose = "academic-support"
    halted = False

    def deny(step: TraceStep, exc: BaseException) -> None:
        nonlocal halted
        step.status, step.code, step.detail = "DENIED", denial_code(exc), str(exc).split(": ", 1)[-1][:160]
        halted = True

    # 1 ADMIT
    step = by["ADMIT"]
    documents: tuple[str, ...] = ()
    known = requester in {"support-agent", "sub-agent-b"} or requester in PEOPLE
    if not known:
        step.status, step.code, step.decided_by = "DENIED", "CALLER_NOT_AUTHENTICATED", "boundary"
        halted = True
    else:
        try:
            if document is not None:
                signature = world.sign_document(document_source, document) if sign_document else "0" * 64
                admitted = world.admit_document(document_source, document, signature)
                documents = (admitted["text"],)
                step.evidence = {"injection_markers": admitted["injection_markers"]}
            step.status, step.code, step.decided_by = "ALLOWED", "ADMITTED", "boundary"
            step.detail = f"caller {requester} authenticated" + (
                f"; document carried as data with {len(step.evidence.get('injection_markers', []))} "
                "instruction-like marker(s)" if document else "")
        except DENIALS as exc:
            deny(step, exc)

    # 2 PROTECT
    step = by["PROTECT"]
    if not halted:
        classes = sorted({world.policy.field_classes[f] for f in fields})
        step.status, step.code, step.decided_by = "ALLOWED", "CLASSIFIED_AND_ENCRYPTED", "key custody"
        step.detail = f"classes {', '.join(classes)}; records stored as per-student AES-GCM ciphertext"
        step.evidence = {"classes": classes, "plaintext_in_store": b"Mei Ling Chan" in world.records.raw_bytes(),
                         "tokenization": world.on("tokenization")}
        facts["classes"] = classes

    # 3 ROUTE
    step = by["ROUTE"]
    endpoint = world.model_endpoint
    if not halted:
        try:
            choice = world.router.route(purpose=purpose, fields=fields)
            endpoint = choice.endpoint
            step.status, step.code, step.decided_by = "INFO", "ROUTE_SUGGESTED", "router (advisory)"
            step.detail = f"suggested {endpoint}; the gate and registry still decide"
        except LookupError as exc:
            step.status, step.code, step.detail = "DENIED", "ROUTE_NO_PERMITTED_ENDPOINT", str(exc)
            halted = True
        facts["where"] = endpoint

    # 4 ENTITLE
    step = by["ENTITLE"]
    context = None
    grant = None
    session = f"trace-{scenario}"
    if not halted:
        grant = world.grant(holder=requester, purpose=purpose, subjects=[student], fields=fields)
        facts["grant"] = {"grant_id": grant.grant_id, "purpose": grant.purpose, "fields": sorted(grant.fields),
                          "subjects": sorted(grant.subjects), "expires_at": grant.expires_at,
                          "issued_by": grant.issued_by}
        try:
            context = world.read(requester=requester, grant=grant, purpose=purpose, subjects=[student],
                                 fields=fields, endpoint=endpoint, session_id=session)
            step.status, step.code, step.decided_by = "ALLOWED", "CONTEXT_RELEASED", "context gate"
            step.detail = f"{len(context.values)} value(s) released as {len(context.tokens)} token(s) to {endpoint}"
            step.evidence = {"receipt_id": context.receipt_id, "model_sees": context.values}
            facts["data"] = context.values
        except DENIALS as exc:
            deny(step, exc)

    # 5 REASON
    step = by["REASON"]
    proposal = None
    if not halted:
        turn = world.ask_model(model, {"kind": "grade_correction",
                                       "resource": f"transcript:{student}:MATH101",
                                       "from_status": world.register.get(f"transcript:{student}:MATH101")["status"],
                                       "to_status": target_grade}, context, documents)
        facts["proposed"] = turn.to_dict()
        step.status, step.decided_by = "INFO", "model (untrusted)"
        spec = next((p for p in turn.proposals if p.get("operation") == "correct_transcript_grade"), None)
        if spec is None:
            step.code, step.detail = "NO_ACTION_PROPOSED", turn.text[:120]
            halted = True
        else:
            proposal = world.propose(requester=requester, operation=spec["operation"], resource=spec["resource"],
                                     to_status=spec["to_status"], from_status=spec.get("from_status"))
            step.code = "PROPOSAL_RECEIVED"
            step.detail = f"{spec['operation']} {spec['resource']} → {spec['to_status']}; claims ignored: {sorted(turn.claims)}"
            step.evidence = {"proposal_digest": proposal.digest}

    # 6 AUTHORIZE
    step = by["AUTHORIZE"]
    approval = None
    if not halted and proposal is not None:
        try:
            approval = world.review_and_approve(proposal, reviewer=reviewer)
            step.status, step.code, step.decided_by = "ALLOWED", "HUMAN_APPROVED", f"{reviewer} ({PEOPLE.get(reviewer)})"
            step.detail = "Ed25519 approval bound to the exact proposal digest"
            step.evidence = {"approval_id": approval.approval_id, "approver_role": approval.approver_role,
                             "expires_at": approval.expires_at}
            facts["authority"] = {"approver": reviewer, "role": PEOPLE.get(reviewer)}
        except DENIALS as exc:
            deny(step, exc)

    # 7 EXECUTE
    step = by["EXECUTE"]
    receipt = None
    if not halted and proposal is not None:
        try:
            executed = world.execute(proposal, approval, model_endpoint=endpoint)
            receipt = executed["receipt"]
            step.status, step.code, step.decided_by = "ALLOWED", "EXECUTED", "execution mediator"
            step.detail = f"{proposal.case_id} now {executed['result'].status} (version {executed['result'].version})"
            step.evidence = {"receipt_digest": receipt.digest,
                             "receipt_valid": verify_receipt(receipt, world.notary.public_keys).valid}
            facts["result"] = step.detail
        except DENIALS as exc:
            deny(step, exc)

    # 8 RELEASE
    step = by["RELEASE"]
    if not halted and context is not None:
        name_token = next((v for k, v in context.values.items() if k.endswith(".student_name")), "the student")
        try:
            output = world.derive(requester=requester, session_id=session,
                                  content=f"{name_token}: MATH101 corrected to {target_grade[-1]}; attendance follow-up advised")
            released = world.release(output, recipient=recipient, purpose=purpose, restore_identity=True)
            step.status, step.code, step.decided_by = "ALLOWED", released.code, "release gate"
            step.detail = f"released to {recipient}; identity restored: {released.identity_restored}"
            step.evidence = {"label": sorted(output.label.classes), "receipt_id": released.receipt.receipt_id}
            facts["released"] = released.content
        except DENIALS as exc:
            deny(step, exc)

    # 9 RECORD — always
    step = by["RECORD"]
    checkpoint = world.checkpoint()
    intact, code = world.evidence_intact()
    values_in_evidence = any(value in str([r.payload for r in world.ledger])
                             for value in world.identity_values())
    step.status = "ALLOWED" if intact and not values_in_evidence else "DENIED"
    step.code, step.decided_by = code, "evidence notary"
    step.detail = f"{checkpoint.count} records, signed head {checkpoint.head_hash[:12]}…; identity values in evidence: {values_in_evidence}"
    step.evidence = {"checkpoint": checkpoint.to_dict(), "receipt": receipt.to_dict() if receipt else None}
    facts["evidence"] = {"records": checkpoint.count, "head": checkpoint.head_hash,
                         "receipt_digest": receipt.digest if receipt else None}

    # 10 RECOVER — always
    step = by["RECOVER"]
    step.decided_by = "resilience"
    if halted:
        step.status, step.code = "ALLOWED", "FAILED_CLOSED_TO_MANUAL_FALLBACK"
        step.detail = world.profile.manual_fallback.strip()
    else:
        grant_id = facts["grant"]["grant_id"]
        world.data_delegation.revoke(grant_id, by="privacy-officer-ng", reason="post-decision revocation drill")
        try:
            world.read(requester=requester, grant=grant, purpose=purpose, subjects=[student], fields=fields,
                       endpoint=endpoint, session_id=session + "-after")
            step.status, step.code = "DENIED", "REVOCATION_NOT_ENFORCED"
        except DENIALS as exc:
            step.status, step.code = "ALLOWED", "REVOKED_AUTHORITY_REFUSED"
            step.detail = f"revocation drill: next read refused with {denial_code(exc)}; pending outcomes {world.executor.pending_outcome_count}"
    trace.outcome = next((f"DENIED at step {s.number} {s.name} by {s.decided_by or s.plane}: {s.code}"
                          for s in steps if s.status == "DENIED" and s.number <= 8), "COMPLETED with evidence")
    facts["redress"] = ("file_challenge → academic_appeals_officer may uphold (reverse) or dismiss; "
                        "the student sees the receipt digest, the policy, and who approved")
    trace.facts = facts
    return trace


def explain(trace: RequestTrace) -> dict:
    """The system-literacy view: ten questions anyone should be able to answer about an AI decision."""
    facts = trace.facts
    by = {s.name: s for s in trace.steps}
    return {
        "WHO": f"{facts.get('who')} asked, about student {facts.get('student')} (shown to the model only as a token)",
        "WHAT": (facts.get("proposed") or {}).get("proposals") or "nothing was proposed",
        "AUTHORITY": facts.get("authority") or f"none: {by['AUTHORIZE'].code or 'not reached'}",
        "DATA": facts.get("data") or f"none released: {by['ENTITLE'].code or 'not reached'}",
        "WHY": (facts.get("grant") or {}).get("purpose", "no purpose was entitled"),
        "WHERE": facts.get("where"),
        "DECISION": trace.outcome,
        "RESULT": facts.get("result") or "no state changed",
        "EVIDENCE": facts.get("evidence"),
        "REDRESS": facts.get("redress"),
    }


__all__ = ["RequestTrace", "STEPS", "TraceStep", "explain", "run_governed_request"]
