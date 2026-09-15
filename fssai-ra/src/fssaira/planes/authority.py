"""Authority plane: purpose-, time- and holder-bound grants and approvals, model
manifests and key custody. Delegation only narrows."""
from __future__ import annotations

from fssaira.planes.base import Plane, Prohibition

PLANE = Plane(
    name="authority",
    responsibility=(
        "Issue purpose-, time- and holder-bound grants and approvals, hold model "
        "manifests, and provide key custody"
    ),
    must_not=(
        Prohibition("accept authority derived from model output",
                    "tests/test_capability_exploits.py::test_a_confident_false_rationale_changes_no_outcome"),
        Prohibition("let a delegation hop pass on authority it does not hold",
                    "tests/test_delegation.py::test_a_hop_cannot_pass_on_authority_it_does_not_hold"),
        Prohibition("derive a signing key from public data",
                    "tests/test_composition_and_key_secrecy.py::test_default_asymmetric_authority_key_is_not_derivable_from_key_id"),
    ),
    components=(
        "fssaira.exact_action:AsymmetricApprovalAuthority",
        "fssaira.delegation:DelegationAuthority",
        "fssaira.grant_delegation:GrantDelegationService",
        "fssaira.disclosure:GrantAuthority",
        "fssaira.model_registry:ModelRegistry",
        "fssaira.key_custody:KeyCustody",
    ),
)
