"""The seven-field control contract is the narrow waist: enforced, not described.

An empty field is an open governance decision and fails the build. A failure
test that is named but does not exist fails the build. Existence means the exact
pytest node resolves in the parsed file, never that a name appears somewhere as
a substring.
"""
from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

from fssaira.kernel.contract import (
    FIELDS,
    CapabilityContract,
    ContractError,
    load_capability_contracts,
    resolve_test_locator,
    verify_bindings,
)

ROOT = Path(__file__).resolve().parents[2]

GOOD = {
    "id": "CAP-X",
    "protected_asset": "a record",
    "permitted_operation": "one transition",
    "enforcement_point": "the executor",
    "accountable_owner": "records officer",
    "failure_test": "tests/test_sample.py::test_refuses",
    "evidence_artifact": "receipt",
    "failure_response": "deny and route to manual fallback",
}


def _repo(tmp_path: Path, entries: list[dict], test_source: str | None = None) -> Path:
    (tmp_path / "contract" / "capabilities").mkdir(parents=True)
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_sample.py").write_text(test_source if test_source is not None else textwrap.dedent("""
        def test_refuses():
            assert True

        def test_refuses_twice():
            assert True

        def helper():
            return 1

        class TestGroup:
            def test_method(self):
                assert True
    """))
    doc = {"domain": "sample", "capabilities": entries}
    (tmp_path / "contract" / "capabilities" / "sample.yaml").write_text(yaml.safe_dump(doc))
    return tmp_path


def test_the_seven_fields_are_exactly_the_papers_fields():
    assert FIELDS == (
        "protected_asset", "permitted_operation", "enforcement_point",
        "accountable_owner", "failure_test", "evidence_artifact", "failure_response",
    )


def test_a_complete_contract_loads(tmp_path):
    root = _repo(tmp_path, [GOOD])
    [cap] = load_capability_contracts(root / "contract" / "capabilities", root=root)
    assert isinstance(cap, CapabilityContract)
    assert cap.id == "CAP-X" and cap.domain == "sample"
    assert cap.failure_test_path == root / "tests" / "test_sample.py"


@pytest.mark.parametrize("field", FIELDS)
def test_an_empty_field_is_an_open_governance_decision(tmp_path, field):
    root = _repo(tmp_path, [{**GOOD, field: "   "}])
    with pytest.raises(ContractError, match="open governance decision"):
        load_capability_contracts(root / "contract" / "capabilities", root=root)


@pytest.mark.parametrize("field", FIELDS)
def test_a_missing_field_is_an_open_governance_decision(tmp_path, field):
    entry = {k: v for k, v in GOOD.items() if k != field}
    root = _repo(tmp_path, [entry])
    with pytest.raises(ContractError, match="open governance decision"):
        load_capability_contracts(root / "contract" / "capabilities", root=root)


def test_legacy_key_names_are_not_accepted_in_capability_contracts(tmp_path):
    entry = {k: v for k, v in GOOD.items() if k != "accountable_owner"}
    entry["owner"] = "records officer"
    root = _repo(tmp_path, [entry])
    with pytest.raises(ContractError, match="unknown field 'owner'"):
        load_capability_contracts(root / "contract" / "capabilities", root=root)


def test_duplicate_capability_ids_fail(tmp_path):
    root = _repo(tmp_path, [GOOD, dict(GOOD)])
    with pytest.raises(ContractError, match="duplicate"):
        load_capability_contracts(root / "contract" / "capabilities", root=root)


def test_a_named_but_missing_test_fails_the_build(tmp_path):
    root = _repo(tmp_path, [{**GOOD, "failure_test": "tests/test_sample.py::test_does_not_exist"}])
    with pytest.raises(ContractError, match="does not exist"):
        load_capability_contracts(root / "contract" / "capabilities", root=root)


def test_a_missing_test_file_fails_the_build(tmp_path):
    root = _repo(tmp_path, [{**GOOD, "failure_test": "tests/test_absent.py::test_refuses"}])
    with pytest.raises(ContractError, match="does not exist"):
        load_capability_contracts(root / "contract" / "capabilities", root=root)


def test_a_substring_of_a_real_test_name_is_not_existence(tmp_path):
    root = _repo(tmp_path, [GOOD], test_source="def test_refuses_quietly():\n    assert True\n")
    with pytest.raises(ContractError, match="does not exist"):
        load_capability_contracts(root / "contract" / "capabilities", root=root)


def test_a_name_in_a_comment_or_string_is_not_existence(tmp_path):
    source = "# def test_refuses():\nNAME = 'def test_refuses():'\n"
    root = _repo(tmp_path, [GOOD], test_source=source)
    with pytest.raises(ContractError, match="does not exist"):
        load_capability_contracts(root / "contract" / "capabilities", root=root)


def test_a_helper_is_not_a_failure_test(tmp_path):
    root = _repo(tmp_path, [{**GOOD, "failure_test": "tests/test_sample.py::helper"}])
    with pytest.raises(ContractError, match="not a test"):
        load_capability_contracts(root / "contract" / "capabilities", root=root)


def test_a_failure_test_must_name_a_node_not_a_whole_file(tmp_path):
    root = _repo(tmp_path, [{**GOOD, "failure_test": "tests/test_sample.py"}])
    with pytest.raises(ContractError, match="node"):
        load_capability_contracts(root / "contract" / "capabilities", root=root)


def test_class_methods_resolve_by_exact_path(tmp_path):
    root = _repo(tmp_path, [GOOD])
    assert resolve_test_locator("tests/test_sample.py::TestGroup::test_method", root=root)
    with pytest.raises(ContractError):
        resolve_test_locator("tests/test_sample.py::test_method", root=root)
    with pytest.raises(ContractError):
        resolve_test_locator("tests/test_sample.py::OtherGroup::test_method", root=root)


def test_a_source_locator_may_name_a_unique_method_but_not_an_ambiguous_one(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "runner.py").write_text(textwrap.dedent("""
        class Runner:
            def scenarios(self):
                return []

            def shared(self):
                return 1

        class Other:
            def shared(self):
                return 2
    """))
    assert resolve_test_locator("src/runner.py::scenarios", root=tmp_path, require_test=False)
    assert resolve_test_locator("src/runner.py::Runner::shared", root=tmp_path, require_test=False)
    with pytest.raises(ContractError, match="ambiguous"):
        resolve_test_locator("src/runner.py::shared", root=tmp_path, require_test=False)
    with pytest.raises(ContractError, match="does not exist"):
        resolve_test_locator("src/runner.py::missing", root=tmp_path, require_test=False)


def test_the_method_shorthand_never_applies_to_failure_tests(tmp_path):
    root = _repo(tmp_path, [{**GOOD, "failure_test": "tests/test_sample.py::test_method"}])
    with pytest.raises(ContractError, match="does not exist"):
        load_capability_contracts(root / "contract" / "capabilities", root=root)


def test_a_locator_may_not_escape_the_repository(tmp_path):
    root = _repo(tmp_path, [GOOD])
    with pytest.raises(ContractError, match="outside"):
        resolve_test_locator("../tests/test_sample.py::test_refuses", root=root)


# -- the repository's own contracts ----------------------------------------

def test_the_repository_capability_contracts_all_resolve():
    capabilities = load_capability_contracts(ROOT / "contract" / "capabilities", root=ROOT)
    assert len(capabilities) >= 8
    domains = {cap.domain for cap in capabilities}
    assert {"action", "disclosure", "evidence", "delegation"} <= domains


def test_every_legacy_binding_resolves_strictly():
    assert verify_bindings(ROOT / "contract", root=ROOT) == []


def test_the_strict_binding_check_catches_a_planted_substring_locator(tmp_path):
    (tmp_path / "contract" / "bindings").mkdir(parents=True)
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("def test_alpha_beta():\n    pass\n")
    (tmp_path / "contract" / "bindings" / "core.yaml").write_text(yaml.safe_dump({"bindings": [
        {"requirements": ["R-1"], "mechanism": "unit_test", "locator": "tests/test_a.py::test_alpha"},
    ]}))
    [finding] = verify_bindings(tmp_path / "contract", root=tmp_path)
    assert "test_alpha" in finding


def test_capability_failure_tests_are_collected_by_pytest():
    """Existence in source is not enough: pytest must collect every named node."""
    capabilities = load_capability_contracts(ROOT / "contract" / "capabilities", root=ROOT)
    nodes = sorted({cap.failure_test for cap in capabilities})
    # ``-o addopts=`` so the project's own ``-q`` does not stack into ``-qq``,
    # which prints per-file counts instead of node ids.
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-o", "addopts=",
         "-p", "no:cacheprovider", *nodes],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]
    collected = {line.strip() for line in result.stdout.splitlines() if "::" in line}
    for node in nodes:
        assert any(line == node or line.startswith(node + "[") for line in collected), node
