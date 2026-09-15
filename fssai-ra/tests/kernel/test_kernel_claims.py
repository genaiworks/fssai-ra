"""The claims register classifies every contracted assertion three ways.

The register is computed, never typed: its legacy rows must agree with
``fssaira.coverage.measure_coverage`` row for row, so no count in it can be
edited to match the paper.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from fssaira.coverage import measure_coverage
from fssaira.kernel.claims import CLAIM_CLASSES, build_register

ROOT = Path(__file__).resolve().parents[2]


def test_there_are_exactly_three_claim_classes():
    assert CLAIM_CLASSES == ("machine_verified", "attested", "unverified")


def test_every_row_has_one_of_the_three_classes():
    register = build_register(ROOT)
    assert register.rows
    assert {row.status for row in register.rows} <= set(CLAIM_CLASSES)


def test_legacy_rows_agree_with_measured_coverage_row_for_row():
    register = build_register(ROOT)
    coverage = measure_coverage(str(ROOT / "contract"))
    mapping = {"machine_verified": "machine_verified",
               "organizationally_attested": "attested",
               "unverified": "unverified"}
    expected = {row.requirement_id: mapping[row.status] for row in coverage.requirements}
    actual = {row.id: row.status for row in register.rows if row.source == "contract"}
    assert actual == expected


def test_capability_rows_are_machine_verified_through_a_resolved_test():
    register = build_register(ROOT)
    rows = [row for row in register.rows if row.source == "capability"]
    assert rows
    for row in rows:
        assert row.status == "machine_verified"
        assert "::" in row.evidence[0]


def test_counts_are_derived_from_rows():
    register = build_register(ROOT)
    counts = register.counts()
    assert sum(counts[c] for c in CLAIM_CLASSES) == len(register.rows)
    assert counts == register.counts(source=None)
    legacy = register.counts(source="contract")
    assert sum(legacy.values()) == len(measure_coverage(str(ROOT / "contract")).requirements)


def test_yaml_is_deterministic_and_round_trips():
    first = build_register(ROOT).to_yaml()
    second = build_register(ROOT).to_yaml()
    assert first == second
    doc = yaml.safe_load(first)
    assert set(doc) == {"classes", "counts", "counts_by_source", "rows"}
    assert doc["counts"] == build_register(ROOT).counts()
