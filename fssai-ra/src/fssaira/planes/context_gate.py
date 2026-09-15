"""Context gate (mediator, Rule 2): check grant, purpose, consent, zone and
attestation; tokenize; label every output; restore identity only if entitled."""
from __future__ import annotations

from fssaira.planes.base import Plane, Prohibition

PLANE = Plane(
    name="context_gate",
    responsibility=(
        "Check grant, purpose, consent, zone and attestation before any read; tokenize "
        "identifiers; label every output; release and restore identity only to an "
        "entitled recipient"
    ),
    must_not=(
        Prohibition("let a model lower the label of its own summary",
                    "tests/test_disclosure.py::test_model_claimed_label_cannot_launder_a_summary"),
        Prohibition("declassify without an exact, independent approval",
                    "tests/test_disclosure.py::test_declassification_requires_exact_independent_approval"),
        Prohibition("release after consent or the grant changed since the read",
                    "tests/test_disclosure.py::test_release_rechecks_consent_and_revocation_after_the_read"),
        Prohibition("restore identity from a token issued to another session",
                    "tests/test_privacy_integration.py::test_vault_cross_session_tokens_do_not_restore"),
    ),
    components=(
        "fssaira.disclosure:DisclosureGate",
        "fssaira.privacy_pipeline:PrivacyGate",
        "fssaira.privacy_vault:TokenVault",
    ),
    mediator=True,
)
