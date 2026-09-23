"""Two-minute demonstration of a cached-receipt authorization boundary.

The unsafe branch is an explicitly modeled historical pattern, not a checkout
of the old implementation. It only operates on a local synthetic receipt.
"""
import json
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from trustkernel.guard import ActionClass, Guard  # noqa: E402
from trustkernel.kernel.exact_action import ExecutionDenied  # noqa: E402


def demonstrate():
    guard = Guard(clock=lambda: 1000)
    effects = []

    @guard.tool(resource="service", action_class=ActionClass.HIGH_IMPACT, approver_role="release_manager")
    def deploy(service, build):
        effects.append((service, build))
        return {"service": service, "build": build, "receipt": "SYNTHETIC-INTERNAL-RECEIPT"}

    ctx = guard.root("coordinator", tools={"deploy"}, resources={"payments"})
    proposal = guard.propose(ctx, "deploy", resource="payments", service="payments", build="v2")
    approval = guard.approve(proposal, approver="reviewer", role="release_manager")
    first = deploy(ctx, service="payments", build="v2", approval=approval)
    forged = replace(approval, signature="00" * 64)
    # Positive control: a cache keyed only by an unauthenticated digest returns data.
    unsafe_cache = {proposal.digest: first}
    unsafe_disclosure = unsafe_cache.get(forged.proposal_digest)
    guarded_disclosure = None
    code = None
    try:
        guarded_disclosure = deploy(ctx, service="payments", build="v2", approval=forged)
    except ExecutionDenied as exc:
        code = exc.code
    replay = deploy(ctx, service="payments", build="v2", approval=approval)
    passed = (unsafe_disclosure == first and guarded_disclosure is None
              and code == "APPROVAL_SIGNATURE_INVALID" and replay == first and len(effects) == 1)
    return {"unsafe_model_released_receipt": unsafe_disclosure is not None,
            "guard_released_receipt": guarded_disclosure is not None,
            "guard_denial": code, "valid_replay_matches": replay == first,
            "deploy_effects": len(effects), "experiment_passed": passed}


if __name__ == "__main__":
    result = demonstrate()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["experiment_passed"] else 1)
