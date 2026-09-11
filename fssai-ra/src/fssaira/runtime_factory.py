"""Environment-driven assembly for memory and Redis/Kafka deployment profiles."""
from __future__ import annotations

import os
from pathlib import Path

from .control_plane import ControlPlane
from .exact_action import ApprovalAuthority
from .profiles import ApplicationProfile


def build_control_plane() -> ControlPlane:
    profile_path = Path(os.getenv("FSSAI_PROFILE", "profiles/student_support.yaml"))
    profile = ApplicationProfile.load(profile_path)
    evidence_token = os.getenv("FSSAI_EVIDENCE_TOKEN", "teaching-evidence-writer")
    key_id = os.getenv("FSSAI_APPROVAL_KEY_ID", "teaching-approval-key-1")
    signing_key = os.getenv(
        "FSSAI_APPROVAL_SIGNING_KEY", "non-secret-demo-key-replace-in-production"
    )
    authority = ApprovalAuthority(key_id=key_id, signing_key=signing_key)
    approval_keys = {key_id: signing_key}

    events = None
    kafka_bootstrap = os.getenv("FSSAI_KAFKA_BOOTSTRAP")
    if kafka_bootstrap:
        from .kafka_backend import KafkaEventPublisher
        events = KafkaEventPublisher(
            kafka_bootstrap, os.getenv("FSSAI_KAFKA_TOPIC", "fssaira.events")
        )

    redis_url = os.getenv("FSSAI_REDIS_URL")
    if not redis_url:
        return ControlPlane(
            profile,
            evidence_token=evidence_token,
            authority=authority,
            approval_keys=approval_keys,
            events=events,
        )

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
    )


def production_configuration_warnings() -> list[str]:
    warnings = []
    if os.getenv("FSSAI_APPROVAL_SIGNING_KEY", "").startswith("non-secret") or not os.getenv(
        "FSSAI_APPROVAL_SIGNING_KEY"
    ):
        warnings.append("teaching approval key is active")
    if not os.getenv("FSSAI_REDIS_URL"):
        warnings.append("in-memory state is active")
    if not os.getenv("FSSAI_KAFKA_BOOTSTRAP"):
        warnings.append("in-memory event transport is active")
    return warnings
