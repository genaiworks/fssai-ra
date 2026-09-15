"""Intelligence plane (untrusted): advisory semantic router, replaceable attested
models, agents and retrieval.

Everything here may be capable, persuasive, misaligned or manipulated. Its
output is a proposal or a draft, never an effect or a disclosure.
"""
from __future__ import annotations

from fssaira.planes.base import Plane, Prohibition

PLANE = Plane(
    name="intelligence",
    responsibility=(
        "Classify intent, rank approved models, and draft or propose over tokens and "
        "labelled context"
    ),
    must_not=(
        Prohibition("widen authority through routing",
                    "tests/test_privilege_invariance.py::test_routing_cannot_widen_authority"),
        Prohibition("introduce a capability through model output",
                    "tests/test_privilege_invariance.py::test_model_output_cannot_introduce_a_capability"),
        Prohibition("escalate its own privileges through a compromised update",
                    "tests/test_attacks.py::test_compromised_update_is_quarantined_and_no_self_escalation"),
        Prohibition("run as a substituted or unapproved model endpoint",
                    "tests/test_privacy_integration.py::test_http_model_registry_rejects_substitution_or_unapproved_use"),
    ),
    components=(
        "fssaira.semantic_router:SemanticRouter",
        "fssaira.bounded_intelligence:BoundedAgent",
        "fssaira.bounded_intelligence:TaskRouter",
    ),
    untrusted=True,
)
