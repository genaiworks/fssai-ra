"""Execution plane (mediator, Rule 1): recheck policy, identity, version, approval
and replay; bind the exact proposal digest; one write plus reconciliation."""
from __future__ import annotations

from fssaira.planes.base import Plane, Prohibition

PLANE = Plane(
    name="execution",
    responsibility=(
        "Recheck policy, identity, version, approval and replay, bind the exact proposal "
        "digest, and perform one write with external reconciliation"
    ),
    must_not=(
        Prohibition("trust a reused approval",
                    "tests/test_exact_action.py::test_retry_is_idempotent_and_cross_request_reuse_is_denied"),
        Prohibition("trust a changed proposal",
                    "tests/test_exact_action.py::test_target_or_arguments_changed_after_approval_are_denied"),
        Prohibition("trust a model-supplied action class",
                    "tests/test_privilege_invariance.py::test_a_call_that_understates_its_class_is_reclassified"),
        Prohibition("execute after the context authority behind the proposal was withdrawn",
                    "tests/test_composition_and_key_secrecy.py::test_execute_denied_after_context_grant_revoked"),
    ),
    components=(
        "fssaira.exact_action:AccountableExecutor",
        "fssaira.atomic_execution:AtomicExecutor",
        "fssaira.accountable_action:PolicyEnforcementPoint",
    ),
    mediator=True,
)
