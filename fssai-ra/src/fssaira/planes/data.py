"""Governed data plane: stable identifiers, replayable events, versioned snapshots,
per-subject envelope encryption at rest."""
from __future__ import annotations

from fssaira.planes.base import Plane, Prohibition

PLANE = Plane(
    name="data",
    responsibility=(
        "Keep stable identifiers, replayable events and versioned snapshots, with "
        "sensitive fields encrypted under per-subject keys"
    ),
    must_not=(
        Prohibition("be mutated except through an approved, exact, current-version proposal",
                    "tests/test_exact_action.py::test_tampered_approval_is_rejected_before_mutation"),
        Prohibition("leave a partial record after a failed load, or lose its version high-water mark on restore",
                    "tests/test_privacy_integration.py::test_record_load_failure_is_atomic_and_restore_preserves_version_high_water"),
        Prohibition("retain plaintext identity lookup keys or serve erased subjects from cache",
                    "tests/test_privacy_integration.py::test_vault_does_not_retain_plaintext_lookup_keys_and_erased_cache_cannot_be_used"),
    ),
    components=(
        "fssaira.encrypted_records:EncryptedRecordSource",
        "fssaira.reproducible_data:SnapshotStore",
        "fssaira.event_transport:EventLog",
        "fssaira.exact_action:CaseRegister",
    ),
)
