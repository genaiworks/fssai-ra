"""The control contract is the paper's original contribution, so it is tested.

Seven fields per requirement is not a documentation convention. It is a
diagnostic: a capability whose protected asset, permitted operation, enforcement
point, owner, failure test, evidence artifact, and failure response cannot all
be named is a capability nobody is ready to automate. These tests make an
incomplete entry a build failure rather than a reviewer's problem.
"""
from fssaira import ControlContract
from helpers import CONTRACT_DIR

REQUIRED = ("protected_asset", "permitted_operation", "enforcement_point",
            "owner", "test", "evidence_artifact", "failure_response")

#: The five architectural domains from the paper, plus the cross-cutting
#: services that must be administered separately from the agent runtime.
FIVE_DOMAINS = {
    "import_boundary", "event_transport", "reproducible_data",
    "bounded_intelligence", "accountable_action",
}

#: The two composition domains. Separate from the five because they govern what
#: happens *between* components rather than inside one: authority passed from
#: agent to agent, and a human approval whose independence now depends on a
#: model. Asserted by name so that deleting either is a deliberate edit — a
#: subset check alone would let a whole domain disappear without failing.
COMPOSITION_DOMAINS = {"delegated_authority", "assisted_review"}


def test_contract_loads_and_validates():
    contract = ControlContract.load(CONTRACT_DIR)
    contract.validate()  # raises on a missing field or a duplicate id
    assert len(contract) >= 20


def test_every_requirement_is_complete():
    for requirement in ControlContract.load(CONTRACT_DIR):
        for field in REQUIRED:
            assert getattr(requirement, field), f"{requirement.id} is missing {field}"


def test_all_five_domains_are_present():
    domains = {requirement.domain for requirement in ControlContract.load(CONTRACT_DIR)}
    assert domains >= FIVE_DOMAINS


def test_the_composition_domains_are_present():
    """The controls that govern what happens between components.

    One agent under one grant, approved by one unaided human, is no longer the
    shape being deployed. Both halves of that sentence now have a domain, and
    both are named here so that losing one is a visible edit.
    """
    domains = {requirement.domain for requirement in ControlContract.load(CONTRACT_DIR)}
    missing = sorted(COMPOSITION_DOMAINS - domains)
    assert not missing, f"the control contract has lost these domains: {missing}"


def test_every_composition_requirement_names_an_enforcement_point_not_a_policy():
    """A composition control that is only a written rule is worth nothing.

    These two domains are the newest and therefore the easiest to fill with
    aspiration. Each entry must name where the rule is *enforced*, and the
    enforcement point must not simply restate the permitted operation.
    """
    for requirement in ControlContract.load(CONTRACT_DIR):
        if requirement.domain not in COMPOSITION_DOMAINS:
            continue
        point = requirement.enforcement_point.strip()
        assert len(point) > 40, f"{requirement.id} enforcement point is too thin to locate"
        assert point.lower() != requirement.permitted_operation.strip().lower(), (
            f"{requirement.id} restates the permitted operation instead of naming "
            "where it is enforced"
        )


def test_cross_cutting_controls_are_declared_separately():
    """Identity, keys, evidence custody, and the manual fallback are not one
    domain's business. Burying them inside a domain is how they end up owned by
    the team that runs the agent."""
    contract = ControlContract.load(CONTRACT_DIR)
    cross_cutting = contract.by_domain("cross_cutting")

    assert cross_cutting, "cross-cutting controls must be declared"
    owners = {requirement.owner for requirement in cross_cutting}
    assert len(owners) >= 3, f"cross-cutting controls share too few owners: {owners}"


def test_every_domain_names_more_than_one_owner():
    """Separation of duties starts in the contract. A domain where one person
    owns every control has no independent enforcement point, whatever the
    architecture diagram says."""
    contract = ControlContract.load(CONTRACT_DIR)
    all_owners = {requirement.owner for requirement in contract}
    assert len(all_owners) >= 8, f"only {len(all_owners)} distinct owners across the contract"


def test_each_failure_response_describes_an_action_not_a_sentiment():
    vague = {"monitor", "be careful", "review", "tbd", "n/a", ""}
    for requirement in ControlContract.load(CONTRACT_DIR):
        response = requirement.failure_response.strip().lower()
        assert response not in vague, f"{requirement.id} failure response is not actionable"
        assert len(response) > 20, f"{requirement.id} failure response is too thin to follow"
