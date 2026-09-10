"""Remove one control at a time and show the attack now succeeds - evidence
that each control is load-bearing, not decorative."""
from helpers import privileged_agent

from fssaira import ActionClass, FSSAIRAPipeline, ToolCall


def test_removing_egress_control_enables_exfiltration():
    p = FSSAIRAPipeline(allow_egress=True)  # ablation
    agent = privileged_agent(p)
    call = ToolCall(agent.id, "notify_external", "notify_external", target="evil",
                    action_class=ActionClass.REVERSIBLE)
    assert p.pep.check(call, agent).allowed is True  # containment lost


def test_removing_human_approval_enables_unilateral_high_impact():
    p = FSSAIRAPipeline(require_human_for_high_impact=False)  # ablation
    agent = privileged_agent(p)
    call = ToolCall(agent.id, "approve_award", "approve_award", target="case-42",
                    action_class=ActionClass.HIGH_IMPACT)
    assert p.pep.check(call, agent).allowed is True  # containment lost


def test_removing_least_privilege_lets_agent_approve_awards():
    # Grant approval both privilege and a rubber-stamp approver: only the
    # widened privilege is the change under test.
    p = FSSAIRAPipeline(approver=lambda c: (True, "auto"))
    agent = privileged_agent(p)  # over-provisioned == least-privilege removed
    call = ToolCall(agent.id, "approve_award", "approve_award", target="case-42",
                    action_class=ActionClass.HIGH_IMPACT)
    assert p.pep.check(call, agent).allowed is True
