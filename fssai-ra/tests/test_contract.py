from helpers import CONTRACT_DIR

from fssaira import ControlContract

REQUIRED = ("protected_asset", "permitted_operation", "enforcement_point",
            "owner", "test", "evidence_artifact", "failure_response")


def test_contract_loads_and_validates():
    c = ControlContract.load(CONTRACT_DIR)
    c.validate()  # raises on missing field or duplicate id
    assert len(c) >= 8


def test_every_requirement_is_complete():
    c = ControlContract.load(CONTRACT_DIR)
    for r in c:
        for field in REQUIRED:
            assert getattr(r, field), f"{r.id} missing {field}"


def test_all_five_domains_present():
    c = ControlContract.load(CONTRACT_DIR)
    domains = {r.domain for r in c}
    assert domains == {
        "import_boundary", "event_transport", "reproducible_data",
        "bounded_intelligence", "accountable_action",
    }
