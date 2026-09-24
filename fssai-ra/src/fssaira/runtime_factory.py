"""Environment-driven assembly, and an honest account of what got assembled.

One function builds the control plane for every deployment profile, and one
function reports what is wrong with the resulting configuration. The second
matters as much as the first. A reference architecture that boots happily with
public test keys, in-memory state, and spoofable headers is a reference
architecture that will be deployed that way.

So: teaching defaults are reported on ``/health``, in the CLI's ``doctor``
command, and on the console's landing page, with a severity. Structurally
inconsistent review-assistance declarations are the exception: they fail during
assembly because the assistant-independence claim cannot be enforced later at
runtime. The paper's claim is about testable boundaries; a boundary nobody can
see the state of is not testable.

Configuration
-------------
====================================  ==================================================
``FSSAI_PROFILE``                     path to the application profile YAML
``FSSAI_DATABASE_URL``                ``postgresql://…`` or ``sqlite:///…`` (enables
                                      single-transaction durability)
``FSSAI_REDIS_URL``                   Redis state, when no database is configured
``FSSAI_KAFKA_BOOTSTRAP``             Kafka event publication
``FSSAI_MODEL``                       model backend name (default ``ollama``)
``FSSAI_MODEL_FALLBACK``              ``allow`` (default) or ``deny``
``FSSAI_AUTH_MODE``                   ``token`` (default), ``header``, or ``oidc``
``FSSAI_EVIDENCE_TOKEN``              evidence write credential
``FSSAI_APPROVAL_SIGNING_KEY``        approval signing key
====================================  ==================================================
"""
from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .assisted_review import AssistanceMode, AssistedReviewPolicy, ReviewAssistance
from .control_plane import ControlPlane
from .exact_action import ApprovalAuthority
from .metrics import Metrics
from .oversight import OversightMonitor, ReviewLoadPolicy

TEACHING_KEY_PREFIX = "non-secret"
#: The only accepted values of FSSAI_DEPLOYMENT_PROFILE. Anything else refuses to start.
DEPLOYMENT_PROFILES = frozenset({"teaching", "pilot", "production"})


@dataclass(frozen=True)
class Warning_:
    severity: str        # blocking | high | medium | info
    code: str
    message: str
    remedy: str = ""

    def to_dict(self) -> dict:
        return {"severity": self.severity, "code": self.code,
                "message": self.message, "remedy": self.remedy}


def build_control_plane(*, profile_path: str | Path | None = None) -> ControlPlane:
    """Assemble the control plane described by the environment."""
    # Fail secure, not fail loud. A deployment that declares itself a pilot or
    # production system does not start while a blocking teaching default is
    # active: a warning on /health is read after the forgeable key was used.
    declared = os.getenv("FSSAI_DEPLOYMENT_PROFILE", "teaching").strip().lower()
    # An unrecognised value (a typo such as "prod", or "staging") must not fall
    # through to teaching behaviour and skip every consequential refusal below.
    if declared not in DEPLOYMENT_PROFILES:
        raise RuntimeError(
            f"refusing to start: FSSAI_DEPLOYMENT_PROFILE={declared!r} is not one of "
            f"{', '.join(sorted(DEPLOYMENT_PROFILES))}"
        )
    if declared in {"pilot", "production"}:
        blocking = [item for item in configuration_warnings() if item.severity == "blocking"]
        if blocking:
            raise RuntimeError(
                f"refusing to start a {declared} deployment with teaching defaults active: "
                + "; ".join(item.code for item in blocking)
            )
<<<<<<< HEAD
    # The kernel floor is enforced where the deployment starts, not only in tests:
    # a pack that weakens a guarantee (a model approver, a fail-open review, a
    # missing control contract) raises PackRejected and the server does not start.
    from .pack_floor import load_governed_pack

    pack = load_governed_pack(
=======
    # A backend inherits no assurance until the conformance suite has passed on
    # exactly its code. Enforced for pilot/production; recorded for teaching.
    assurance = _backend_assurance(declared)
    profile = ApplicationProfile.load(
>>>>>>> 1423e13 (M4: GenAI integration contract, backend assurance, and two fail-open fixes)
        Path(profile_path or os.getenv("FSSAI_PROFILE", "profiles/student_support.yaml"))
    )
    profile = pack.profile
    evidence_token = os.getenv("FSSAI_EVIDENCE_TOKEN", "teaching-evidence-writer")
    key_id = os.getenv("FSSAI_APPROVAL_KEY_ID", "teaching-approval-key-1")
    signing_key = os.getenv(
        "FSSAI_APPROVAL_SIGNING_KEY", "non-secret-demo-key-replace-in-production"
    )
    # The oversight control is attached to the authority the *deployment* uses,
    # not only to the one the CLI trial builds. Until this existed, an
    # institution could run the whole platform with review capacity enforced
    # nowhere, which is precisely the failure the contract exists to eliminate:
    # a control that held in the evaluation and not at runtime.
    #
    # `from_env` returns None when nothing was declared, and that stays None.
    # Inheriting our shipped quota would publish a capacity figure nobody at the
    # institution agreed to; `configuration_warnings` reports the absence.
    oversight = None
    # An explicit FSSAI_REVIEW_* declaration wins; otherwise the pack's own review
    # block is enforced, so capacity that passed the kernel floor is also the
    # capacity the approval path applies.
    review_policy = ReviewLoadPolicy.from_env() or ReviewLoadPolicy.from_pack(pack.review)
    from .control_plane import ReviewQueuePolicy

    review_queue = ReviewQueuePolicy.from_pack(pack.review)
    assistance = ReviewAssistance.from_env()
    if assistance.mode is not AssistanceMode.UNAIDED:
        # This failure is visible only in the declaration. At approval time an
        # independent and a dependent assistant produce the same reviewer
        # identity, interval, and signature, so waiting until runtime would make
        # the advertised gate impossible. When no capacity has been declared,
        # the unaided baseline validates ownership without inventing a floor.
        declared_floor = (
            review_policy.min_deliberation_seconds
            if review_policy is not None
            else AssistedReviewPolicy().unaided_floor_seconds
        )
        AssistedReviewPolicy().check(assistance, declared_floor)
    if review_policy is not None:
        oversight = OversightMonitor(review_policy)
    authority = ApprovalAuthority(
        key_id=key_id, signing_key=signing_key, oversight=oversight
    )
    approval_keys = {key_id: signing_key}
    metrics = Metrics()

    events = None
    kafka_bootstrap = os.getenv("FSSAI_KAFKA_BOOTSTRAP")
    if kafka_bootstrap:
        from .envelope_mac import key_from_env
        from .kafka_backend import KafkaEventPublisher

        events = KafkaEventPublisher(
            kafka_bootstrap, os.getenv("FSSAI_KAFKA_TOPIC", "fssaira.events"),
            mac_key=key_from_env("FSSAI_EVENT_ENVELOPE_KEY"),
        )

    model = _build_model()
    from .checkpoint_notary import CheckpointNotary

    notary = CheckpointNotary.from_env()

    # 1. SQL profile: the only one with single-transaction durability.
    database_url = os.getenv("FSSAI_DATABASE_URL")
    if database_url:
        from .atomic_execution import AtomicExecutor, sql_evidence, sql_object_store, sql_register
        from .event_outbox import SqlEventOutbox
        from .postgres_backend import database_from_env

        database = database_from_env(database_url, evidence_token=evidence_token)
<<<<<<< HEAD
        # Events are written to the SQL outbox first and relayed to Kafka when it
        # is configured, so a broker outage never loses or fails a committed change.
        return ControlPlane(
=======
        plane = ControlPlane(
>>>>>>> 1423e13 (M4: GenAI integration contract, backend assurance, and two fail-open fixes)
            profile,
            register=sql_register(database),
            evidence=sql_evidence(database),
            evidence_token=evidence_token,
            authority=authority,
            objects=sql_object_store(database),
            events=SqlEventOutbox(database, publisher=events),
            approval_keys=approval_keys,
            metrics=metrics,
            model=model,
            notary=notary,
            review_queue=review_queue,
            durability="single-transaction",
            executor=AtomicExecutor(
                database,
                evidence_token,
                approval_keys=approval_keys,
                allowed_operations=profile.allowed_operations,
                transition_rules=profile.transition_rules,
                required_approval_roles=profile.required_approval_roles,
            ),
        )
        return _attach_assurance(plane, assurance)

    # 2. Redis profile: durable across restarts, two stores, reconciliation needed.
    redis_url = os.getenv("FSSAI_REDIS_URL")
    if redis_url:
        from .event_outbox import EventOutbox, RedisOutboxStore
        from .redis_backend import (
            RedisApprovalUseStore,
            RedisCaseRegister,
            RedisEvidenceLedger,
            RedisObjectStore,
            RedisPendingOutcomeStore,
            connect_redis,
        )

        client = connect_redis(redis_url)
        prefix = os.getenv("FSSAI_REDIS_PREFIX", "fssaira")
<<<<<<< HEAD
        outbox = RedisOutboxStore(client, prefix)
        return ControlPlane(
=======
        plane = ControlPlane(
>>>>>>> 1423e13 (M4: GenAI integration contract, backend assurance, and two fail-open fixes)
            profile,
            register=RedisCaseRegister(client, prefix, outbox=outbox),
            evidence=RedisEvidenceLedger(client, evidence_token, prefix),
            evidence_token=evidence_token,
            authority=authority,
            objects=RedisObjectStore(client, prefix),
            events=EventOutbox(outbox, publisher=events),
            outcome_store=RedisPendingOutcomeStore(client, prefix),
            approval_use_store=RedisApprovalUseStore(client, prefix),
            approval_keys=approval_keys,
            metrics=metrics,
            model=model,
            notary=notary,
            review_queue=review_queue,
            durability="best-effort",
        )
        return _attach_assurance(plane, assurance)

    # 3. Teaching profile: everything in memory, nothing survives a restart.
<<<<<<< HEAD
    if events is not None:
        from .event_outbox import EventOutbox, MemoryOutboxStore

        # A broker outage must not fail a change that has already happened.
        events = EventOutbox(MemoryOutboxStore(), publisher=events)
    return ControlPlane(
=======
    plane = ControlPlane(
>>>>>>> 1423e13 (M4: GenAI integration contract, backend assurance, and two fail-open fixes)
        profile,
        evidence_token=evidence_token,
        authority=authority,
        approval_keys=approval_keys,
        events=events,
        metrics=metrics,
        model=model,
        notary=notary,
        review_queue=review_queue,
        durability="volatile",
    )
    return _attach_assurance(plane, assurance)


def _backends_in_use() -> tuple[str, ...]:
    """The backend names (see ``fssaira.kernel.assurance.BACKEND_MODULES``) this env selects."""
    database_url = os.getenv("FSSAI_DATABASE_URL", "").strip()
    if database_url:
        state = "sqlite" if database_url.lower().startswith("sqlite") else "postgres"
    elif os.getenv("FSSAI_REDIS_URL"):
        state = "redis"
    else:
        state = "memory"
    return (state, "kafka") if os.getenv("FSSAI_KAFKA_BOOTSTRAP") else (state,)


def _backend_assurance(declared: str) -> dict[str, dict]:
    """Require (pilot/production) or record (teaching) backend conformance assurance.

    Records are read from ``FSSAI_CONFORMANCE_RECORDS`` (JSON: one record or a list),
    produced by :func:`fssaira.kernel.assurance.run_and_record` on the target stack.
    """
    from .kernel.assurance import (
        AssuranceRefused,
        AssuranceStatus,
        assurance_status,
        load_records,
        require_assurance,
    )

    enforce = declared in {"pilot", "production"}
    path = os.getenv("FSSAI_CONFORMANCE_RECORDS", "").strip()
    records: dict = {}
    if path:
        try:
            records = load_records(path)
        except (OSError, ValueError, AssuranceRefused) as exc:
            if enforce:
                raise RuntimeError(
                    f"refusing to start a {declared} deployment: conformance records at "
                    f"FSSAI_CONFORMANCE_RECORDS are unreadable ({type(exc).__name__})"
                ) from exc
    statuses: dict[str, dict] = {}
    for backend in _backends_in_use():
        if enforce:
            try:
                status = require_assurance(backend, records.get(backend))
            except AssuranceRefused as refused:
                raise RuntimeError(
                    f"refusing to start a {declared} deployment: backend {backend!r} has no "
                    f"current passing conformance record ({refused.code}); run "
                    "fssaira.kernel.assurance.run_and_record on this stack and set "
                    "FSSAI_CONFORMANCE_RECORDS"
                ) from refused
        elif path:
            status = assurance_status(backend, records.get(backend))
        else:
            status = AssuranceStatus(backend, False, "NOT_REQUIRED_TEACHING", notes=(
                "teaching profile: backend assurance is recorded, not enforced",))
        statuses[backend] = status.to_dict()
    return statuses


def _attach_assurance(plane: ControlPlane, assurance: dict[str, dict]) -> ControlPlane:
    """Expose the backend assurance status on the assembled plane."""
    plane.backend_assurance = assurance  # type: ignore[attr-defined]
    return plane


def _build_model():
    """Select a model backend while honouring the fail-closed setting."""
    from .models import ModelSelection, select_model

    try:
        return select_model(probe=os.getenv("FSSAI_MODEL_PROBE", "1") != "0")
    except Exception as exc:
        # ``select_model`` already refuses an unreachable backend when fallback
        # is denied. Do not defeat that decision at the final assembly boundary.
        if os.getenv("FSSAI_MODEL_FALLBACK", "allow").strip().lower() == "deny":
            raise
        from .models.deterministic import DeterministicModel

        return ModelSelection(
            requested=os.getenv("FSSAI_MODEL", "ollama"),
            backend=DeterministicModel("control-plane"),
            fell_back=True,
            detail=str(exc),
        )


def transport_findings() -> list[Warning_]:
    """Plain-text links, unauthenticated events and a missing notary.

    Each is ``high`` in general and ``blocking`` when the deployment declares
    itself ``production``: the documentation says production needs verified TLS,
    authenticated events and signed checkpoints, so declaring production without
    them is refused rather than published on /health.
    """
    from urllib.parse import parse_qs, urlparse

    production = os.getenv("FSSAI_DEPLOYMENT_PROFILE", "teaching").strip().lower() == "production"
    severity = "blocking" if production else "high"
    findings: list[Warning_] = []
    database = os.getenv("FSSAI_DATABASE_URL", "")
    if database.startswith(("postgres://", "postgresql://")):
        mode = (parse_qs(urlparse(database).query).get("sslmode") or ["prefer"])[0]
        if mode in {"disable", "allow", "prefer"}:
            findings.append(Warning_(
                severity, "PLAINTEXT_DATABASE_TRANSPORT",
                f"the database connection may be unencrypted (sslmode={mode})",
                "use sslmode=verify-full with sslrootcert; see deploy/compose.tls.yaml"))
        elif mode != "verify-full":
            findings.append(Warning_(
                severity, "UNVERIFIED_DATABASE_TLS",
                f"sslmode={mode} encrypts but does not verify the server's identity",
                "use sslmode=verify-full with sslrootcert"))
    redis = os.getenv("FSSAI_REDIS_URL", "")
    if redis.startswith("redis://") and not database:
        findings.append(Warning_(
            severity, "PLAINTEXT_STATE_TRANSPORT", "the Redis state connection is unencrypted",
            "use a rediss:// URL with FSSAI_REDIS_CA_FILE"))
    if os.getenv("FSSAI_KAFKA_BOOTSTRAP"):
        if os.getenv("FSSAI_KAFKA_SECURITY_PROTOCOL", "").strip().upper() != "SSL":
            findings.append(Warning_(
                severity, "PLAINTEXT_EVENT_TRANSPORT", "lifecycle events travel unencrypted",
                "set FSSAI_KAFKA_SECURITY_PROTOCOL=SSL and FSSAI_KAFKA_SSL_CA_LOCATION"))
        if not os.getenv("FSSAI_EVENT_ENVELOPE_KEY"):
            findings.append(Warning_(
                severity, "UNAUTHENTICATED_EVENTS",
                "anything that can reach the broker can publish lifecycle events that the "
                "monitor will count",
                "set FSSAI_EVENT_ENVELOPE_KEY here and in every consumer"))
    if not os.getenv("FSSAI_NOTARY_KEY_FILE"):
        findings.append(Warning_(
            "blocking" if production else "medium", "NO_EVIDENCE_NOTARY",
            "no signed checkpoints are kept, so deleting the newest evidence is undetectable",
            "set FSSAI_NOTARY_KEY_FILE and FSSAI_NOTARY_CHECKPOINT_DIR"))
    return findings


def configuration_warnings() -> list[Warning_]:
    """Everything about this configuration that would fail an institutional review."""
    from .security import AuthConfig

    warnings: list[Warning_] = list(transport_findings())
    signing_key = os.getenv("FSSAI_APPROVAL_SIGNING_KEY", "")
    if not signing_key or signing_key.startswith(TEACHING_KEY_PREFIX):
        warnings.append(Warning_(
            "blocking", "TEACHING_APPROVAL_KEY",
            "the public teaching approval key is active; approvals are forgeable by anyone "
            "who has read this repository",
            "set FSSAI_APPROVAL_SIGNING_KEY from a secret manager",
        ))
    if os.getenv("FSSAI_EVIDENCE_TOKEN", "teaching-evidence-writer") == "teaching-evidence-writer":
        warnings.append(Warning_(
            "blocking", "TEACHING_EVIDENCE_TOKEN",
            "the default evidence write credential is active",
            "set FSSAI_EVIDENCE_TOKEN and hold it only in the evidence service",
        ))
    if not os.getenv("FSSAI_DATABASE_URL"):
        if os.getenv("FSSAI_REDIS_URL"):
            warnings.append(Warning_(
                "medium", "NO_TRANSACTIONAL_DURABILITY",
                "state is durable but the register and the evidence ledger are separate stores; "
                "an interrupted outcome is possible and must be reconciled",
                "set FSSAI_DATABASE_URL to enable single-transaction execution",
            ))
        else:
            warnings.append(Warning_(
                "high", "VOLATILE_STATE",
                "in-memory state is active; every record is lost on restart",
                "set FSSAI_DATABASE_URL (postgresql:// or sqlite:///)",
            ))
    elif os.getenv("FSSAI_REDIS_URL"):
        warnings.append(Warning_(
            "info", "REDIS_SHADOWED_BY_SQL",
            "both SQL and Redis state URLs are configured; the control plane uses SQL "
            "for state and does not write the Redis state adapters in this process",
            "remove FSSAI_REDIS_URL, or run a separate Redis-profile conformance deployment",
        ))
    if not os.getenv("FSSAI_KAFKA_BOOTSTRAP"):
        warnings.append(Warning_(
            "info", "IN_MEMORY_EVENTS",
            "in-memory event transport is active; events are not replayable across processes",
            "set FSSAI_KAFKA_BOOTSTRAP",
        ))
    try:
        auth_issues = AuthConfig.from_env().warnings()
    except ValueError as exc:
        auth_issues = [f"invalid authentication configuration: {exc}"]
    for issue in auth_issues:
        warnings.append(Warning_("blocking", "AUTHENTICATION", issue,
                                 "see docs/OPERATIONS.md, 'Authentication modes'"))
    model = os.getenv("FSSAI_MODEL", "ollama")
    base_url = os.getenv("FSSAI_MODEL_BASE_URL", "")
    if base_url and not _is_local_model_url(base_url):
        warnings.append(Warning_(
            "high", "NON_LOCAL_MODEL",
            f"the model endpoint {base_url} is not local; prompts and retrieved evidence "
            "leave the sovereign boundary",
            "host the model inside the boundary, or remove the data-residency claim",
        ))
    if model in ("compromised", "class-downgrading", "null"):
        warnings.append(Warning_(
            "blocking", "ADVERSARIAL_MODEL",
            f"the '{model}' backend is an evaluation fixture that behaves maliciously on purpose",
            "set FSSAI_MODEL to ollama or another real backend",
        ))
    warnings.extend(_oversight_warnings())
    return warnings


def _is_local_model_url(value: str) -> bool:
    """Classify the parsed endpoint host, never a matching substring."""
    try:
        hostname = urlparse(value).hostname
    except ValueError:
        return False
    if not hostname:
        return False
    if hostname in {"localhost", "host.docker.internal"}:
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def _oversight_warnings() -> list[Warning_]:
    """What this deployment has declared about review, assistance, and delegation.

    Every one of these reports an *absent declaration* rather than a detected
    fault, because that is what is actually knowable here. A deployment cannot
    be inspected for how attentive its reviewers are, which model reviews its
    model's work, or how many hands a permission passes through — but it can be
    asked whether anyone wrote those numbers down, and an institution that has
    not is running on assumptions it never agreed to.
    """
    from .assisted_review import AssistanceMode, AssistedReviewPolicy, ReviewAssistance
    from .delegation import DelegationPolicy
    from .exact_action import ExecutionDenied

    findings: list[Warning_] = []

    review_policy_invalid = False
    try:
        review_policy = ReviewLoadPolicy.from_env()
    except ValueError as exc:
        review_policy_invalid = True
        review_policy = None
        findings.append(Warning_(
            "blocking", "INVALID_REVIEW_POLICY", str(exc),
            "correct the FSSAI_REVIEW_* declaration; the deployment assembly fails closed",
        ))
    if review_policy is None and not review_policy_invalid:
        findings.append(Warning_(
            "high", "NO_DECLARED_REVIEW_CAPACITY",
            "no review capacity is declared, so approvals are unlimited: this deployment "
            "routes consequential actions to a named human and assumes that human has "
            "infinite attention",
            "set FSSAI_REVIEW_MAX_PER_WINDOW and FSSAI_REVIEW_DELIBERATION_FLOOR from a "
            "roster you would defend; `fssaira oversight <profile> --sweep` computes the ceiling",
        ))
    elif review_policy is not None:
        coherence = review_policy.declared_consistency()
        if not coherence["consistent"]:
            findings.append(Warning_(
                "medium", "INCOHERENT_REVIEW_POLICY",
                f"the declared quota and deliberation floor contradict each other: "
                f"{coherence['note']}",
                "raise the quota, or state plainly that the lower number is the capacity "
                "you are willing to staff",
            ))

    assistance_invalid = False
    try:
        assistance = ReviewAssistance.from_env()
    except ValueError as exc:
        assistance_invalid = True
        assistance = ReviewAssistance()
        findings.append(Warning_(
            "blocking", "INVALID_REVIEW_ASSISTANCE", str(exc),
            "use the documented mode and explicit true/false declarations",
        ))
    if not assistance_invalid and assistance.mode is not AssistanceMode.UNAIDED:
        if not assistance.declared_by:
            findings.append(Warning_(
                "blocking", "ASSISTANCE_NOT_DECLARED",
                "review assistance is configured but no accountable owner declared its "
                "independence properties",
                "set FSSAI_REVIEW_ASSISTANCE_DECLARED_BY to the role answerable for it",
            ))
        if review_policy is not None:
            gate = AssistedReviewPolicy()
            try:
                gate.check(assistance, review_policy.min_deliberation_seconds)
            except ExecutionDenied as denial:
                findings.append(Warning_(
                    "blocking", denial.code,
                    str(denial),
                    "raise FSSAI_REVIEW_DELIBERATION_FLOOR, or establish and declare the "
                    "independence that buys the throughput",
                ))
        if not assistance.is_independent:
            findings.append(Warning_(
                "high", "DEPENDENT_REVIEW_ASSISTANT",
                f"the review assistant is {assistance.independence_score}/3 independent of the "
                "proposing model; on the cases where a proposal is substantively wrong a "
                "dependent assistant is wrong the same way, and no runtime signal distinguishes it",
                "declare a different model, a different evidence path, and an adversarial "
                "posture — or keep the unaided deliberation floor",
            ))

    delegation_invalid = False
    try:
        delegation = DelegationPolicy.from_env()
    except ValueError as exc:
        delegation_invalid = True
        delegation = None
        findings.append(Warning_(
            "blocking", "INVALID_DELEGATION_POLICY", str(exc),
            "correct the FSSAI_*DELEGATION* declaration; the chain verifier fails closed",
        ))
    if delegation is None and not delegation_invalid:
        findings.append(Warning_(
            "info", "NO_DECLARED_DELEGATION_BOUND",
            "no delegation depth is declared. This is correct for a deployment where one "
            "agent calls one tool, and wrong for one that calls a tool server, a plugin, or "
            "a sub-agent it did not write",
            "set FSSAI_MAX_DELEGATION_DEPTH if authority is passed onward at all",
        ))
    return findings


def production_configuration_warnings() -> list[str]:
    """Backwards-compatible flat list, as returned by v0.5.0's ``/health``."""
    return [item.message for item in configuration_warnings()]


def readiness() -> dict:
    """A single verdict an operator or a CI gate can act on."""
    warnings = configuration_warnings()
    blocking = [item for item in warnings if item.severity == "blocking"]
    return {
        "ready_for_pilot": not blocking,
        "blocking": [item.to_dict() for item in blocking],
        "warnings": [item.to_dict() for item in warnings if item.severity != "blocking"],
        "note": (
            "readiness here means 'no known teaching defaults are active'. It is not an "
            "assessment of the deployment, the domain profile, or the institution's controls."
        ),
    }


__all__ = [
    "Warning_", "build_control_plane", "configuration_warnings",
    "production_configuration_warnings", "readiness",
]
