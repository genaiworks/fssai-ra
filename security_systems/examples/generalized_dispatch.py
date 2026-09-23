"""One dispatcher for three synthetic application adapters, no world pack needed."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from trustkernel.guard import ActionClass, Guard  # noqa: E402
from trustkernel.kernel.exact_action import ExecutionDenied  # noqa: E402
from trustkernel.runtime import GuardedDispatcher  # noqa: E402


def run(operation, resource, approved_value):
    guard = Guard()
    effects = []

    @guard.tool(operation, resource="resource", action_class=ActionClass.HIGH_IMPACT, approver_role="reviewer")
    def adapter(resource, value):
        effects.append({"resource": resource, "value": value})
        return effects[-1]

    owner = guard.root("owner", tools={operation}, resources={resource})
    worker = guard.spawn(owner, "worker", tools=set())
    # These IDs are supplied by the authenticated transport, not the model.
    dispatcher = GuardedDispatcher(guard, {"owner-session": owner, "worker-session": worker})
    request = {"tool": operation, "arguments": {"resource": resource, "value": approved_value}}
    approval = guard.approve(dispatcher.propose("owner-session", request), approver="human", role="reviewer")
    denied = []
    for caller, call in [
        ("worker-session", request),
        ("owner-session", {"tool": operation, "arguments": {"resource": resource, "value": "swapped"}}),
    ]:
        try:
            dispatcher.dispatch(caller, call, approval=approval)
        except ExecutionDenied as exc:
            denied.append(exc.code)
    first = dispatcher.dispatch("owner-session", request, approval=approval)
    second = dispatcher.dispatch("owner-session", request, approval=approval)
    return {"operation": operation, "denials": denied, "effects": effects,
            "passed": len(denied) == 2 and len(effects) == 1 and first == second}


if __name__ == "__main__":
    results = [run(*config) for config in [
        ("deploy", "service-7", "v2"),
        ("refund", "order-8", "approved-adjustment"),
        ("publish", "article-9", "reviewed-copy"),
    ]]
    print(json.dumps(results, indent=2))
    raise SystemExit(0 if all(result["passed"] for result in results) else 1)
