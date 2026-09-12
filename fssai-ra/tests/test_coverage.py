"""Contract coverage: is each requirement enforced, or only written down?

These tests exist because the contract loader validated that every requirement
*had* a ``test`` field and never that the test *existed*. Eighteen of
twenty-eight requirements turned out to carry a test description bound to
nothing — a control that existed in review and not at runtime, which is the exact
failure this project exists to eliminate, found in its own contract.

The most important test in this file is not the coverage count. It is
``test_every_binding_locator_actually_exists``: without it the coverage report
is a YAML file asserting its own correctness, which would be strictly worse than
having no report at all.
"""
import ast
import os

import pytest

from fssaira.coverage import MECHANISMS, load_bindings, measure_coverage
from helpers import CONTRACT_DIR

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Requirements whose coverage may be organizational. Any *growth* in this set is
#: a deliberate decision that belongs in review, which is why it is pinned here
#: rather than counted. Declaring a control unprovable is how an assurance
#: argument quietly empties out.
MAX_ORGANIZATIONALLY_ATTESTED = 3


def test_every_requirement_is_bound_or_attested():
    report = measure_coverage(CONTRACT_DIR)
    assert report.unverified == 0, (
        "these requirements describe a test in prose and bind it to nothing: "
        f"{', '.join(report.unverified_ids)}"
    )


def test_no_binding_names_a_requirement_that_does_not_exist():
    """A binding pointing at a deleted requirement is a stale governance claim."""
    report = measure_coverage(CONTRACT_DIR)
    assert not report.unknown_bindings, (
        f"bindings name unknown requirements: {report.unknown_bindings}"
    )


def test_every_binding_locator_actually_exists():
    """The test that makes the rest of this file mean anything.

    Every binding naming ``tests/<file>.py::<function>`` is resolved against the
    actual source: the file must exist and must define that function. Without
    this, coverage is a YAML file asserting its own correctness — a more
    convincing version of the problem it was written to detect.

    Locators naming source functions are resolved the same way.
    """
    missing = []
    for binding in load_bindings(CONTRACT_DIR):
        locator = binding.locator
        if "::" not in locator or not locator.endswith(tuple("abcdefghijklmnopqrstuvwxyz_")):
            continue  # conformance check ids and module-level locators
        path, _, symbol = locator.partition("::")
        if not path.endswith(".py"):
            continue
        full = os.path.join(ROOT, path)
        if not os.path.exists(full):
            missing.append(f"{binding.requirement_id}: no such file {path}")
            continue
        with open(full) as handle:
            tree = ast.parse(handle.read(), filename=full)
        defined = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        # A locator may name a method on a class (``ablations::egress_default_deny``
        # style names a result key, resolved below by substring instead).
        if symbol not in defined:
            with open(full) as handle:
                source = handle.read()
            if symbol not in source:
                missing.append(f"{binding.requirement_id}: {path} does not define {symbol}")
    assert not missing, "bindings point at things that do not exist:\n  " + "\n  ".join(missing)


def test_module_locators_resolve_to_real_files():
    unresolved = []
    for binding in load_bindings(CONTRACT_DIR):
        path = binding.locator.partition("::")[0]
        if not path.endswith(".py"):
            continue
        if not os.path.exists(os.path.join(ROOT, path)):
            unresolved.append(f"{binding.requirement_id}: {path}")
    assert not unresolved, f"bindings name missing files: {unresolved}"


def test_organizational_attestation_does_not_grow_silently():
    """Attestation is a weaker claim than a test, so its size is pinned.

    Nothing stops a maintainer from making coverage look perfect by declaring
    every inconvenient control organizational. This test makes that a visible
    edit rather than a quiet one.
    """
    report = measure_coverage(CONTRACT_DIR)
    assert report.organizationally_attested <= MAX_ORGANIZATIONALLY_ATTESTED, (
        f"{report.organizationally_attested} requirements are now attested rather "
        f"than tested, up from {MAX_ORGANIZATIONALLY_ATTESTED}. Declaring a control "
        "unprovable is how an assurance argument empties out; if this is right, "
        "raise the bound deliberately and say why"
    )


def test_an_organizational_declaration_must_name_an_owner_and_a_cadence(tmp_path):
    """An attestation nobody owns on no schedule is not an attestation."""
    (tmp_path / "x.yaml").write_text(
        "domain: d\nrequirements:\n"
        "  - id: X-1\n    verified_by: organizational\n"
        "    protected_asset: a\n    permitted_operation: b\n"
        "    enforcement_point: c\n    owner: d\n    test: e\n"
        "    evidence_artifact: f\n    failure_response: g\n"
    )
    with pytest.raises(ValueError, match="attesting role and a review cadence"):
        measure_coverage(str(tmp_path))


def test_an_unknown_mechanism_is_refused(tmp_path):
    bindings = tmp_path / "bindings"
    bindings.mkdir()
    (bindings / "b.yaml").write_text(
        "bindings:\n  - requirements: [X-1]\n    mechanism: vibes\n    locator: nowhere\n"
    )
    with pytest.raises(ValueError, match="unknown mechanism"):
        load_bindings(str(tmp_path))


def test_every_declared_mechanism_is_used_by_at_least_one_binding():
    """An unused mechanism is a category nobody filled, worth noticing."""
    used = {binding.mechanism for binding in load_bindings(CONTRACT_DIR)}
    unused = set(MECHANISMS) - used - {"attestation"}
    assert not unused, f"declared but unused mechanisms: {sorted(unused)}"


def test_the_report_is_json_serializable_and_states_its_limits():
    import json

    payload = measure_coverage(CONTRACT_DIR).to_dict()
    json.dumps(payload)
    assert payload["limits"], "a coverage figure without its limits invites over-reading"
    assert any("never that it is adequate" in line for line in payload["limits"])


def test_coverage_counts_are_internally_consistent():
    report = measure_coverage(CONTRACT_DIR)
    assert (
        report.machine_verified + report.organizationally_attested + report.unverified
        == report.total
    )
