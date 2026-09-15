"""Evidence plane: bind intent to outcome; append-only hash chain; checkpoint signed
by a key the writer does not hold."""
from __future__ import annotations

from fssaira.planes.base import Plane, Prohibition

PLANE = Plane(
    name="evidence",
    responsibility=(
        "Bind intent to outcome in an append-only hash chain with an externally keyed checkpoint"
    ),
    must_not=(
        Prohibition("be rewritable by the writer whose actions it records",
                    "tests/test_conference_falsification.py::test_notary_detects_rewrite_truncation_and_forged_checkpoints"),
        Prohibition("accept an append without the evidence write credential",
                    "tests/test_atomic_execution.py::test_the_evidence_write_credential_is_enforced_by_the_store"),
        Prohibition("hide an edit to a past record",
                    "tests/test_attacks.py::test_insider_record_tampering_is_detected"),
    ),
    components=(
        "fssaira.evidence:EvidenceLedger",
        "fssaira.evidence_notary:EvidenceNotary",
    ),
)
