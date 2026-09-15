"""Resilience plane: fail secure, revoke, reconcile uncertain effects, route to
manual fallback."""
from __future__ import annotations

from fssaira.planes.base import Plane, Prohibition

PLANE = Plane(
    name="resilience",
    responsibility=(
        "Fail secure, revoke, reconcile uncertain effects, and route work to manual fallback"
    ),
    must_not=(
        Prohibition("auto-retry an uncertain irreversible external effect",
                    "tests/kernel/test_kernel_state_machine.py::test_an_uncertain_irreversible_effect_is_never_retried"),
        Prohibition("report a completed mutation with a missing outcome as anything but uncertain",
                    "tests/test_exact_action.py::test_completed_mutation_is_marked_uncertain_then_reconciled_once"),
        Prohibition("leave partial state after an abrupt exit",
                    "tests/test_resilience.py::test_abrupt_exit_recovers_all_or_nothing_and_retry_is_safe"),
        Prohibition("release anything when its intent evidence cannot be written",
                    "tests/test_disclosure.py::test_intent_evidence_failure_releases_nothing"),
    ),
    components=(
        "fssaira.kernel.state_machine:EffectRecord",
        "fssaira.exact_action:PendingOutcomeStore",
        "fssaira.review_queue:BoundedReviewQueue",
        "fssaira.resilience:run_resilience",
    ),
)
