"""A multi-agent incident loop with trustkernel.guard at the tool dispatcher.

    python examples/guarded_agent_loop.py

The "model" here is a script of tool calls, so the run is reproducible offline. In your
stack, replace ``SCRIPT`` with the tool calls your LLM emits. The only integration point
is ``dispatch``: every tool call goes through a guarded function with the calling
agent's context. Nothing else in your framework changes.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trustkernel.guard import ActionClass, Guard  # noqa: E402
from trustkernel.kernel.disclosure import DisclosureDenied  # noqa: E402
from trustkernel.kernel.exact_action import ExecutionDenied  # noqa: E402

PACK = Path(__file__).resolve().parents[1] / "worlds" / "devtools" / "pack.yaml"
guard = Guard.from_pack(PACK)

# -- your tools, unchanged except for one decorator each -------------------------------


@guard.tool(resource="service", reads=("build-telemetry",))
def read_metrics(service):
    return f"{service}: error rate 0.8%, p99 212ms"


@guard.tool(resource="service", reads=("secret-credentials",))
def read_secret(service):
    return "postgres://db-pay.internal:5432/payments?user=pay_svc&password=SYNTHETIC-PAY-DB-PW-7f3a"


@guard.tool(resource="service", action_class=ActionClass.HIGH_IMPACT, approver_role="release_manager")
def trigger_deploy(service, build):
    return f"deployed {service}@{build}"


TOOLS = {f.guarded_tool: f for f in (read_metrics, read_secret, trigger_deploy)}

# -- the agent tree ------------------------------------------------------------------------

coordinator = guard.root("coordinator", tools=set(TOOLS), resources={"svc-payments"})
agents = {
    "coordinator": coordinator,
    "metrics-agent": guard.spawn(coordinator, "metrics-agent", tools={"read_metrics"}, resources={"svc-payments"}),
    "secrets-agent": guard.spawn(coordinator, "secrets-agent", tools={"read_secret"}, resources={"svc-payments"}),
}
# The metrics worker read a CI log containing a prompt injection. From here on it is hostile.
agents["hijacked-worker"] = guard.spawn(agents["metrics-agent"], "hijacked-worker", tools={"read_metrics"},
                                        resources={"svc-payments"})

SCRIPT = [
    ("metrics-agent", "read_metrics", {"service": "svc-payments"}),
    ("secrets-agent", "read_secret", {"service": "svc-payments"}),
    ("hijacked-worker", "read_secret", {"service": "svc-payments"}),                     # never delegated
    ("hijacked-worker", "trigger_deploy", {"service": "svc-payments", "build": "v43"}),  # never delegated
    ("coordinator", "trigger_deploy", {"service": "svc-payments", "build": "v43"}),      # no human approval
]


def dispatch(agent, tool, arguments, approval=None):
    """The one integration point: your framework's tool-call handler."""
    try:
        result = TOOLS[tool](agents[agent], approval=approval, **arguments)
        print(f"  ✓ {agent:<16} {tool:<15} {result}")
        return result
    except ExecutionDenied as exc:
        print(f"  ✕ {agent:<16} {tool:<15} {exc.code}")


print("Agent tool calls:")
for agent, tool, arguments in SCRIPT:
    dispatch(agent, tool, arguments)

print("\nA human approves exactly one deploy:")
proposal = guard.propose(coordinator, "trigger_deploy", resource="svc-payments", service="svc-payments", build="v42")
approval = guard.approve(proposal, approver="raj-release", role="release_manager")
dispatch("coordinator", "trigger_deploy", {"service": "svc-payments", "build": "v40"}, approval)  # swapped build
dispatch("coordinator", "trigger_deploy", {"service": "svc-payments", "build": "v42"}, approval)
dispatch("coordinator", "trigger_deploy", {"service": "svc-payments", "build": "v42"}, approval)  # replay: same result

print("\nThe coordinator summarizes the secrets worker's output and posts it:")
guard.consume(coordinator, agents["secrets-agent"])
for recipient, purpose in (("slack_general", "incident-triage"), ("security_team", "secret-rotation")):
    try:
        guard.release(coordinator, "summary of the incident", recipient=recipient, purpose=purpose)
        print(f"  ✓ release to {recipient}")
    except DisclosureDenied as exc:
        print(f"  ✕ release to {recipient:<14} {exc.code}")

deploys = [d for d in guard.decisions if d.action == "trigger_deploy" and d.code == "EXECUTED"]
print(f"\n{len(guard.decisions)} decisions on a verified hash-chained ledger ({guard.ledger.verify()}); "
      f"{len(deploys)} deploy executed.")
