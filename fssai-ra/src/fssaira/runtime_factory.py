"""Environment-driven assembly, and an honest account of what got assembled.

One function builds the control plane for every deployment profile, and one
function reports what is wrong with the resulting configuration. The second
matters as much as the first. A reference architecture that boots happily with
public test keys, in-memory state, and spoofable headers is a reference
architecture that will be deployed that way.

So: the plane always starts -- refusing to boot would push operators toward
forks -- but it reports its own shortcomings on ``/health``, in the CLI's
``doctor`` command, and on the console's landing page, with a severity. The
paper's claim is about testable boundaries; a boundary nobody can see the state
of is not testable.

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

import os
from dataclasses import dataclass
from pathlib import Path

from .control_plane import ControlPlane
from .exact_action import ApprovalAuthority
from .metrics import Metrics
from .profiles import ApplicationProfile

TEACHING_KEY_PREFIX = "non-secret"


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
    profile = ApplicationProfile.load(
        Path(profile_path or os.getenv("FSSAI_PROFILE", "profiles/student_support.yaml"))
    )
    evidence_token = os.getenv("FSSAI_EVIDENCE_TOKEN", "teaching-evidence-writer")
    key_id = os.getenv("FSSAI_APPROVAL_KEY_ID", "teaching-approval-key-1")
    signing_key = os.getenv(
        "FSSAI_APPROVAL_SIGNING_KEY", "non-secret-demo-key-replace-in-production"
    )
    authority = ApprovalAuthority(key_id=key_id, signing_key=signing_key)
    approval_keys = {key_id: signing_key}
    metrics = Metrics()

    events = None
    kafka_bootstrap = os.getenv("FSSAI_KAFKA_BOOTSTRAP")
    if kafka_bootstrap:
        from .kafka_backend import KafkaEventPublisher

        events = KafkaEventPublisher(
            kafka_bootstrap, os.getenv("FSSAI_KAFKA_TOPIC", "fssaira.events")
        )

    model = _build_model()

    # 1. SQL profile: the only one with single-transaction durability.
    database_url = os.getenv("FSSAI_DATABASE_URL")
    if database_url:
        from .atomic_execution import AtomicExecutor, sql_evidence, sql_object_store, sql_register
        from .postgres_backend import database_from_env

        database = database_from_env(database_url, evidence_token=evidence_token)
        return ControlPlane(
            profile,
            register=sql_register(database),
            evidence=sql_evidence(database),
            evidence_token=evidence_token,
            authority=authority,
            objects=sql_object_store(database),
            events=events,
            approval_keys=approval_keys,
            metrics=metrics,
            model=model,
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

    # 2. Redis profile: durable across restarts, two stores, reconciliation needed.
    redis_url = os.getenv("FSSAI_REDIS_URL")
    if redis_url:
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
        return ControlPlane(
            profile,
            register=RedisCaseRegister(client, prefix),
            evidence=RedisEvidenceLedger(client, evidence_token, prefix),
            evidence_token=evidence_token,
            authority=authority,
            objects=RedisObjectStore(client, prefix),
            events=events,
            outcome_store=RedisPendingOutcomeStore(client, prefix),
            approval_use_store=RedisApprovalUseStore(client, prefix),
            approval_keys=approval_keys,
            metrics=metrics,
            model=model,
            durability="best-effort",
        )

    # 3. Teaching profile: everything in memory, nothing survives a restart.
    return ControlPlane(
        profile,
        evidence_token=evidence_token,
        authority=authority,
        approval_keys=approval_keys,
        events=events,
        metrics=metrics,
        model=model,
        durability="volatile",
    )


def _build_model():
    """Select a model backend, never letting it stop the control plane starting."""
    from .models import ModelSelection, select_model

    try:
        return select_model(probe=os.getenv("FSSAI_MODEL_PROBE", "1") != "0")
    except Exception as exc:  # ModelUnavailable with FALLBACK=deny, or a bad name
        from .models.deterministic import DeterministicModel

        return ModelSelection(
            requested=os.getenv("FSSAI_MODEL", "ollama"),
            backend=DeterministicModel("control-plane"),
            fell_back=True,
            detail=str(exc),
        )


def configuration_warnings() -> list[Warning_]:
    """Everything about this configuration that would fail an institutional review."""
    from .security import AuthConfig

    warnings: list[Warning_] = []
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
    if not os.getenv("FSSAI_KAFKA_BOOTSTRAP"):
        warnings.append(Warning_(
            "info", "IN_MEMORY_EVENTS",
            "in-memory event transport is active; events are not replayable across processes",
            "set FSSAI_KAFKA_BOOTSTRAP",
        ))
    for issue in AuthConfig.from_env().warnings():
        warnings.append(Warning_("blocking", "AUTHENTICATION", issue,
                                 "see docs/OPERATIONS.md, 'Authentication modes'"))
    model = os.getenv("FSSAI_MODEL", "ollama")
    base_url = os.getenv("FSSAI_MODEL_BASE_URL", "")
    if base_url and not any(
        host in base_url for host in ("localhost", "127.0.0.1", "::1", "host.docker.internal")
    ):
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
    return warnings


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
