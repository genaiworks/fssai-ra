"""The drop-in guard, attacked through the API an adopter actually calls."""
from dataclasses import replace

import pytest

from trustkernel.guard import ActionClass, AgentContext, Guard
from trustkernel.kernel.disclosure import DisclosureDenied
from trustkernel.kernel.exact_action import ExecutionDenied
from trustkernel.world import WorldSpec


class Clock:
    def __init__(self, now: float = 1_000_000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def guard(clock):
    return Guard.from_pack(WorldSpec.load("devtools").pack_path, clock=clock, approval_seed=b"\x01" * 32)


@pytest.fixture
def tools(guard):
    calls = []

    @guard.tool(resource="service", reads=("build-telemetry",))
    def read_metrics(service):
        calls.append(("read_metrics", service))
        return f"metrics for {service}"

    @guard.tool(resource="service", reads=("secret-credentials",))
    def read_secret(service):
        calls.append(("read_secret", service))
        return "postgres://...password=SYNTHETIC"

    @guard.tool(resource="service", action_class=ActionClass.HIGH_IMPACT, approver_role="release_manager")
    def trigger_deploy(service, build):
        calls.append(("trigger_deploy", service, build))
        return f"{service}@{build}"

    return {"read_metrics": read_metrics, "read_secret": read_secret, "trigger_deploy": trigger_deploy, "calls": calls}


def lead(guard):
    return guard.root("coordinator", tools={"read_metrics", "read_secret", "trigger_deploy"},
                      resources={"acme-api", "billing"})


def code_of(excinfo):
    return excinfo.value.code


# -- whole-chain delegation ------------------------------------------------------------


def test_a_narrow_worker_does_its_job_and_nothing_more(guard, tools):
    worker = guard.spawn(lead(guard), "reader-agent", tools={"read_metrics"}, resources={"acme-api"})
    assert tools["read_metrics"](worker, service="acme-api") == "metrics for acme-api"
    for call, kwargs in (("read_metrics", {"service": "billing"}), ("read_secret", {"service": "acme-api"}),
                         ("trigger_deploy", {"service": "acme-api", "build": "v43"})):
        with pytest.raises(ExecutionDenied) as refused:
            tools[call](worker, **kwargs)
        assert code_of(refused) == "OUT_OF_EFFECTIVE_SCOPE", call
    assert tools["calls"] == [("read_metrics", "acme-api")]


def test_a_hop_that_widens_its_parent_is_refused_at_use(guard, tools):
    narrow = guard.spawn(lead(guard), "agent-a", tools={"read_metrics"}, resources={"acme-api"})
    widened = guard.spawn(narrow, "agent-b", tools={"read_metrics", "read_secret"}, resources={"acme-api"})
    with pytest.raises(ExecutionDenied) as refused:
        tools["read_secret"](widened, service="acme-api")
    assert code_of(refused) == "SCOPE_NOT_ATTENUATED"


def test_a_sibling_chain_cannot_be_presented_as_your_own(guard, tools):
    root = lead(guard)
    broad = guard.spawn(root, "assistant-broad", tools={"read_secret"}, resources={"acme-api"})
    guard.spawn(root, "assistant-narrow", tools={"read_metrics"}, resources={"acme-api"})
    stolen = replace(broad, principal="assistant-narrow")
    with pytest.raises(ExecutionDenied) as refused:
        tools["read_secret"](stolen, service="acme-api")
    assert code_of(refused) == "REQUESTER_NOT_CHAIN_LEAF"
    assert ("read_secret", "acme-api") not in tools["calls"]


def test_a_delegate_does_not_outlive_its_delegator(guard, tools, clock):
    short = guard.spawn(lead(guard), "agent-a", tools={"read_metrics"}, ttl_seconds=60)
    longer = guard.spawn(short, "agent-b", tools={"read_metrics"}, ttl_seconds=3600)
    assert longer.chain[-1].expires_at == short.chain[-1].expires_at   # clamped at issue
    assert tools["read_metrics"](longer, service="acme-api")
    clock.now += 120
    with pytest.raises(ExecutionDenied) as expired:
        tools["read_metrics"](longer, service="acme-api")
    assert code_of(expired) in ("ROOT_GRANT_EXPIRED", "DELEGATION_EXPIRED")
    # A hop forged to outlive its parent is refused outright, whatever the clock says.
    from trustkernel.kernel.delegation import Delegation
    stretched = Delegation(delegator="agent-a", delegate="agent-b", scope=longer.chain[-1].scope,
                           issued_at=clock.now - 120, expires_at=clock.now + 9999,
                           key_id=longer.chain[-1].key_id).signed_with(guard.delegation.keys[longer.chain[-1].key_id])
    clock.now -= 100
    with pytest.raises(ExecutionDenied) as refused:
        tools["read_metrics"](replace(longer, chain=(short.chain[0], stretched)), service="acme-api")
    assert code_of(refused) == "DELEGATION_OUTLIVES_DELEGATOR"


def test_depth_is_bounded_by_the_pack(guard, tools):
    ctx = lead(guard)
    for name in ("a", "b", "c"):
        ctx = guard.spawn(ctx, f"agent-{name}", tools={"read_metrics"})
    assert tools["read_metrics"](ctx, service="acme-api")        # depth 3: at the pack's bound
    ctx = guard.spawn(ctx, "agent-d", tools={"read_metrics"})
    with pytest.raises(ExecutionDenied) as refused:
        tools["read_metrics"](ctx, service="acme-api")
    assert code_of(refused) == "DEPTH_EXCEEDED"


def test_a_chain_rooted_in_nothing_confers_nothing(guard, tools):
    rogue_root = guard.root("some-other-service", tools={"read_secret"})
    forged = AgentContext("coordinator", lead(guard).root, rogue_root.chain)
    child = guard.spawn(AgentContext("some-other-service", forged.root), "agent-a", tools={"read_secret"})
    with pytest.raises(ExecutionDenied) as refused:
        tools["read_secret"](child, service="acme-api")
    assert code_of(refused) == "CHAIN_NOT_ROOTED"


def test_consequential_authority_cannot_be_passed_on_by_a_machine(guard, tools):
    """D7: the owner may hand deploy rights to one agent; that agent may not hand them on."""
    deployer = guard.spawn(lead(guard), "deployer", tools={"trigger_deploy"}, resources={"acme-api"},
                           max_action_class=ActionClass.HIGH_IMPACT)
    sub = guard.spawn(deployer, "sub-deployer", tools={"trigger_deploy"}, resources={"acme-api"},
                      max_action_class=ActionClass.HIGH_IMPACT, human_approved=False)
    for ctx, build in ((sub, "v43"), (deployer, "v42")):
        proposal = guard.propose(ctx, "trigger_deploy", resource="acme-api", service="acme-api", build=build)
        approval = guard.approve(proposal, approver="raj-release", role="release_manager")
        if ctx is sub:
            with pytest.raises(ExecutionDenied) as refused:
                tools["trigger_deploy"](ctx, service="acme-api", build=build, approval=approval)
            assert code_of(refused) == "CONSEQUENCE_NOT_DELEGABLE"
        else:
            assert tools["trigger_deploy"](ctx, service="acme-api", build=build, approval=approval) == "acme-api@v42"
    assert [c for c in tools["calls"] if c[0] == "trigger_deploy"] == [("trigger_deploy", "acme-api", "v42")]


# -- exact-action approval ----------------------------------------------------------------


def test_a_deploy_runs_exactly_once_for_exactly_what_was_approved(guard, tools):
    root = lead(guard)
    with pytest.raises(ExecutionDenied) as missing:
        tools["trigger_deploy"](root, service="acme-api", build="v42")
    assert code_of(missing) == "APPROVAL_REQUIRED"

    proposal = guard.propose(root, "trigger_deploy", resource="acme-api", service="acme-api", build="v42")
    wrong_role = guard.approve(proposal, approver="maya-oncall", role="oncall_engineer")
    with pytest.raises(ExecutionDenied) as role:
        tools["trigger_deploy"](root, service="acme-api", build="v42", approval=wrong_role)
    assert code_of(role) == "APPROVER_ROLE_NOT_ALLOWED"

    approval = guard.approve(guard.propose(root, "trigger_deploy", resource="acme-api", service="acme-api",
                                           build="v42"), approver="raj-release", role="release_manager")
    with pytest.raises(ExecutionDenied) as swapped:
        tools["trigger_deploy"](root, service="acme-api", build="v40", approval=approval)
    assert code_of(swapped) == "APPROVAL_PAYLOAD_MISMATCH"
    assert tools["trigger_deploy"](root, service="acme-api", build="v42", approval=approval) == "acme-api@v42"
    assert tools["trigger_deploy"](root, service="acme-api", build="v42", approval=approval) == "acme-api@v42"
    assert [c for c in tools["calls"] if c[0] == "trigger_deploy"] == [("trigger_deploy", "acme-api", "v42")]


def test_an_agent_cannot_approve_its_own_proposal(guard):
    root = lead(guard)
    proposal = guard.propose(root, "trigger_deploy", resource="acme-api", service="acme-api", build="v42")
    with pytest.raises(ExecutionDenied) as refused:
        guard.approve(proposal, approver="coordinator", role="release_manager")
    assert code_of(refused) == "SEPARATION_OF_DUTIES"


def test_approvals_expire(guard, tools, clock):
    root = lead(guard)
    approval = guard.approve(guard.propose(root, "trigger_deploy", resource="acme-api", service="acme-api",
                                           build="v42"), approver="raj-release", role="release_manager",
                             ttl_seconds=60)
    clock.now += 61
    with pytest.raises(ExecutionDenied) as expired:
        tools["trigger_deploy"](root, service="acme-api", build="v42", approval=approval)
    assert code_of(expired) == "APPROVAL_EXPIRED"


# -- labels ------------------------------------------------------------------------------------


def test_a_credential_cannot_reach_general_chat_through_a_summarizer(guard, tools):
    root = lead(guard)
    reader = guard.spawn(root, "reader-agent", tools={"read_secret"}, resources={"acme-api"})
    summarizer = guard.spawn(root, "summarizer-agent", tools=set())
    tools["read_secret"](reader, service="acme-api")
    guard.consume(summarizer, reader)
    with pytest.raises(DisclosureDenied) as refused:
        guard.release(summarizer, "summary: all fine", recipient="slack_general", purpose="incident-triage")
    assert refused.value.code == "RECIPIENT_CLASS_NOT_CLEARED"
    assert guard.release(summarizer, "rotate this", recipient="security_team", purpose="secret-rotation")


def test_clean_work_is_released_and_every_decision_is_on_the_ledger(guard, tools):
    worker = guard.spawn(lead(guard), "reader-agent", tools={"read_metrics"}, resources={"acme-api"})
    tools["read_metrics"](worker, service="acme-api")
    assert guard.release(worker, "p99 is fine", recipient="slack_general", purpose="incident-triage")
    with pytest.raises(DisclosureDenied) as purpose:
        guard.release(worker, "p99 is fine", recipient="slack_general", purpose="secret-rotation")
    assert purpose.value.code == "RECIPIENT_PURPOSE_NOT_ALLOWED"
    assert [d.code for d in guard.decisions][-1] == "RECIPIENT_PURPOSE_NOT_ALLOWED"
    assert guard.ledger.verify() and len(guard.ledger) == len(guard.decisions)


def test_tool_arguments_must_be_keywords_so_approvals_can_bind_them(guard, tools):
    with pytest.raises(TypeError):
        tools["read_metrics"](lead(guard), "acme-api")
