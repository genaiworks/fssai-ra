#!/usr/bin/env python3
"""Collect every committed, machine-written result into ``audit/results.json``.

The results already exist, spread over three regenerated locations:
``evaluation/results/`` (proven by ``scripts/generate_results.py --check``),
``conference/evidence/`` (``scripts/conference_evidence.py --check``) and
``audit/adaptive-results.json`` (the joined-workflow adaptive run). This script
does not recompute any of them. It reads them and writes one file in which every
leaf says where it came from::

    {"value": 30, "denominator": 30, "unit": "adversarial scenarios contained",
     "source": "evaluation/results/v1.0.0-student-support.json#/containment/scenarios_contained",
     "denominator_source": "...#/containment/scenarios_total"}

Denominators travel with their numerators and unlike units are never pooled: a
scenario, a bounded configuration, an operation sequence, an ablation, a task and
an episode each keep their own suite.

Three kinds of leaf are not a plain pointer read, and each says so explicitly in
a ``derivation`` field so a test can re-execute it:

* ``count_where_positive`` / ``sum_field`` / ``length`` over raw per-episode
  records (Table 5), always with a ``cross_check`` pointer to the summary field
  the count must equal; the collector refuses to write if they disagree.
* ``key_name``: a denominator that the source file declares only in a key name
  (for example ``successes_when_one_control_removed_150_attempts``).
* ``claims_register``: ``fssaira.kernel.claims.build_register(ROOT).counts()``,
  a pure function of the contract files, whose legacy-contract counts must agree
  with the committed summary.

There are no timestamps, so the file is deterministic.

    python scripts/collect_results.py          # write audit/results.json
    python scripts/collect_results.py --check  # fail if it has drifted
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

OUTPUT = Path("audit") / "results.json"
GENERATED_BY = "scripts/collect_results.py"
SCHEMA_VERSION = 1

TAG = "v1.0.0"
EVAL = f"evaluation/results/{TAG}-"
SUMMARY = f"{EVAL}summary.json"
CONFERENCE = "conference/evidence/"
ADAPTIVE = "audit/adaptive-results.json"
LIVE_LOCAL = "audit/live-local.json"

#: Summary figure that totals each disclosure arm. The arm keys themselves are
#: read from the per-pack JSON; an arm the summary does not total is an error.
DISCLOSURE_ARM_TOTALS = {
    "unguarded": "disclosure_contained_unguarded",
    "access_controlled": "disclosure_contained_access_controlled",
    "this_architecture": "disclosure_contained",
}


class CollectionError(RuntimeError):
    """A committed source is missing, inconsistent, or disagrees with itself."""


# ---------------------------------------------------------------------------
# JSON pointers (RFC 6901)
# ---------------------------------------------------------------------------

def escape_token(token: str) -> str:
    """Escape one reference token for a JSON pointer."""
    return str(token).replace("~", "~0").replace("/", "~1")


def pointer(*tokens: object) -> str:
    """Build a JSON pointer from reference tokens."""
    return "".join("/" + escape_token(str(token)) for token in tokens)


def resolve_pointer(document: Any, json_pointer: str) -> Any:
    """Resolve ``json_pointer`` against ``document``; raise ``KeyError`` if absent."""
    if json_pointer in ("", "#"):
        return document
    if not json_pointer.startswith("/"):
        raise KeyError(f"not a JSON pointer: {json_pointer!r}")
    current = document
    for raw in json_pointer[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            if not token.isdigit() or int(token) >= len(current):
                raise KeyError(f"{json_pointer}: no index {token!r}")
            current = current[int(token)]
        elif isinstance(current, dict):
            if token not in current:
                raise KeyError(f"{json_pointer}: no member {token!r}")
            current = current[token]
        else:
            raise KeyError(f"{json_pointer}: cannot descend into a scalar at {token!r}")
    return current


def split_source(source: str) -> tuple[str, str]:
    """Split ``relpath#/pointer`` into its path and pointer."""
    rel, _, json_pointer = source.partition("#")
    return rel, json_pointer


def sha256_file(path: Path) -> str:
    """Hex SHA-256 of a file's bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Derivations a test can re-execute
# ---------------------------------------------------------------------------

def _field(record: Any, field_pointer: str) -> Any:
    return resolve_pointer(record, field_pointer)


DERIVATIONS: dict[str, Callable[[Any, dict[str, Any]], Any]] = {
    "count_where_positive": lambda items, spec: sum(
        1 for item in items if _field(item, spec["field"]) > 0),
    "sum_field": lambda items, spec: sum(_field(item, spec["field"]) for item in items),
    "length": lambda items, spec: len(items),
}


def apply_derivation(items: Any, spec: dict[str, Any]) -> Any:
    """Re-execute a declared derivation over the resolved ``source`` value."""
    op = spec["op"]
    if op not in DERIVATIONS:
        raise CollectionError(f"unknown derivation {op!r}")
    return DERIVATIONS[op](items, spec)


def key_name_number(json_pointer: str) -> int:
    """The number a source declares in the last key of ``json_pointer``."""
    last = json_pointer.rsplit("/", 1)[-1]
    numbers = re.findall(r"(?<![A-Za-z])\d+(?![A-Za-z])", last)
    if len(numbers) != 1:
        raise CollectionError(f"key {last!r} does not declare exactly one number")
    return int(numbers[0])


def claims_register_counts(register_root: Path) -> dict[str, dict[str, int]]:
    """Counts of the claims register, overall and by row source."""
    from fssaira.kernel.claims import build_register

    register = build_register(register_root)
    sources = sorted({row.source for row in register.rows})
    return {"all": register.counts(), **{source: register.counts(source) for source in sources}}


# ---------------------------------------------------------------------------
# The collector
# ---------------------------------------------------------------------------

class Collector:
    """Reads committed JSON and builds provenance-carrying leaves."""

    def __init__(self, root: Path, register_root: Path | None = None) -> None:
        self.root = Path(root)
        self.register_root = Path(register_root) if register_root else self.root
        self._documents: dict[str, Any] = {}
        self.read: set[str] = set()

    # -- reading ----------------------------------------------------------
    def document(self, rel: str) -> Any:
        """Load (once) and return the JSON document at ``rel``."""
        if rel not in self._documents:
            path = self.root / rel
            if not path.exists():
                raise CollectionError(f"missing committed source: {rel}")
            self._documents[rel] = json.loads(path.read_text(encoding="utf-8"))
            self.read.add(rel)
        return self._documents[rel]

    def get(self, rel: str, json_pointer: str) -> Any:
        """Resolve a pointer into a committed document."""
        try:
            return resolve_pointer(self.document(rel), json_pointer)
        except KeyError as exc:
            raise CollectionError(f"{rel}#{json_pointer}: {exc}") from exc

    # -- leaves -------------------------------------------------------------
    def leaf(self, rel: str, json_pointer: str, unit: str, *,
             denominator: str | tuple[str, str] | None = None,
             note: str | None = None) -> dict[str, Any]:
        """A leaf read directly from ``rel#json_pointer``, with optional denominator."""
        value = self.get(rel, json_pointer)
        out: dict[str, Any] = {"value": value, "denominator": None, "unit": unit,
                               "source": f"{rel}#{json_pointer}"}
        if denominator is not None:
            drel, dptr = denominator if isinstance(denominator, tuple) else (rel, denominator)
            out["denominator"] = self.get(drel, dptr)
            out["denominator_source"] = f"{drel}#{dptr}"
            self._check_ratio(out)
        if note:
            out["note"] = note
        return out

    def key_name_leaf(self, rel: str, json_pointer: str, unit: str,
                      note: str) -> dict[str, Any]:
        """A value the source declares only as a number inside a key name."""
        self.get(rel, json_pointer)  # the member must exist
        return {"value": key_name_number(json_pointer), "denominator": None, "unit": unit,
                "source": f"{rel}#{json_pointer}", "derivation": {"op": "key_name"},
                "note": note}

    def derived_leaf(self, rel: str, items_pointer: str, spec: dict[str, Any],
                     cross_check: str, unit: str, *,
                     denominator: tuple[dict[str, Any], str] | None = None) -> dict[str, Any]:
        """A leaf counted from raw records, refused unless it equals ``cross_check``."""
        items = self.get(rel, items_pointer)
        value = apply_derivation(items, spec)
        expected = self.get(rel, cross_check)
        if value != expected:
            raise CollectionError(
                f"{rel}#{items_pointer}: {spec['op']} gives {value}, "
                f"but the summary field {cross_check} says {expected}")
        out: dict[str, Any] = {"value": value, "denominator": None, "unit": unit,
                               "source": f"{rel}#{items_pointer}", "derivation": spec,
                               "cross_check": f"{rel}#{cross_check}"}
        if denominator is not None:
            dspec, dcheck = denominator
            dvalue = apply_derivation(items, dspec)
            if dvalue != self.get(rel, dcheck):
                raise CollectionError(f"{rel}#{items_pointer}: denominator disagrees with {dcheck}")
            out["denominator"] = dvalue
            out["denominator_source"] = f"{rel}#{items_pointer}"
            out["denominator_derivation"] = dspec
            out["denominator_cross_check"] = f"{rel}#{dcheck}"
            self._check_ratio(out)
        return out

    @staticmethod
    def _check_ratio(out: dict[str, Any]) -> None:
        value, denominator = out["value"], out["denominator"]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise CollectionError(f"{out['source']}: a ratio needs a numeric value")
        if denominator < value:
            raise CollectionError(f"{out['source']}: denominator {denominator} < value {value}")

    def figure(self, key: str, unit: str, *, denominator: str | None = None,
               note: str | None = None) -> dict[str, Any]:
        """A leaf from the committed paper-figures summary."""
        den = (SUMMARY, pointer("figures", denominator)) if denominator else None
        return self.leaf(SUMMARY, pointer("figures", key), unit, denominator=den, note=note)

    def conference(self, key: str, unit: str, *, denominator: str | None = None,
                   note: str | None = None) -> dict[str, Any]:
        """A leaf from the committed conference evidence summary."""
        rel = f"{CONFERENCE}summary.json"
        den = (rel, pointer("figures", denominator)) if denominator else None
        return self.leaf(rel, pointer("figures", key), unit, denominator=den, note=note)

    # -----------------------------------------------------------------------
    # Suites
    # -----------------------------------------------------------------------
    def comparison_arms(self) -> dict[str, Any]:
        """Identical hostile inputs sent to weaker designs; three separate suites."""
        rel = f"{EVAL}architecture-comparison.json"
        actions = []
        for index, arm in enumerate(self.document(rel)["arms"]):
            label = arm["arm"]
            letter = label.split("·")[0].strip().lower()
            actions.append({
                "arm": label,
                "attacks_succeeded": self.leaf(rel, pointer("arms", index, "attacks_succeeded"),
                                               "attacks that succeeded",
                                               denominator=pointer("arms", index, "attacks_attempted")),
                "harmful_actions": self.figure(f"arm_{letter}_harms",
                                               "harmful actions reaching the protected asset"),
                "containment_rate": self.leaf(rel, pointer("arms", index, "containment_rate"),
                                              "share of attacks contained (rate)"),
                "benign_completed": self.leaf(rel, pointer("arms", index, "benign_completed"),
                                              "benign tasks completed",
                                              denominator=pointer("arms", index, "benign_attempted")),
            })

        disclosure_rel = f"{EVAL}governed-disclosure.json"
        profiles = self.document(disclosure_rel)["profiles"]
        arm_keys = list(profiles[0]["summary"]["contained_by_arm"])
        flows = []
        for arm in arm_keys:
            if arm not in DISCLOSURE_ARM_TOTALS:
                raise CollectionError(f"disclosure arm {arm!r} has no committed total")
            flows.append({
                "arm": arm,
                "contained": self.figure(DISCLOSURE_ARM_TOTALS[arm], "hostile data flows contained",
                                         denominator="disclosure_hostile_total"),
                "per_pack": [
                    {"pack": profile["profile_id"],
                     "contained": self.leaf(
                         disclosure_rel,
                         pointer("profiles", i, "summary", "contained_by_arm", arm),
                         "hostile data flows contained",
                         denominator=pointer("profiles", i, "summary", "hostile_scenarios"))}
                    for i, profile in enumerate(profiles)
                ],
            })

        delegation_rel = f"{EVAL}delegation.json"
        chains = [
            {"arm": arm,
             "contained": self.leaf(delegation_rel, pointer("arms", arm, "contained"),
                                    "hostile delegation risk classes contained",
                                    denominator=pointer("arms", arm, "of")),
             "benign_chain_completed": self.leaf(
                 delegation_rel, pointer("arms", arm, "benign_chain_completed"),
                 "benign two-hop chain completed (boolean)")}
            for arm in self.document(delegation_rel)["arms"]
        ]
        return {
            "note": "three independent suites with different units; never pooled",
            "actions": {"unit": "attack", "attacks": self.figure(
                "comparison_attacks", "distinct attacks sent to every arm"), "arms": actions},
            "disclosure_flows": {"unit": "hostile data flow", "arms": flows},
            "delegation_chains": {"unit": "delegation risk class", "arms": chains},
        }

    def reference_profile(self) -> dict[str, Any]:
        """The student-support reference profile."""
        evaluation = f"{EVAL}student-support.json"
        verification = f"{EVAL}verification.json"
        return {
            "scenarios": self.leaf(evaluation, "/containment/scenarios_contained",
                                   "adversarial scenarios contained",
                                   denominator="/containment/scenarios_total"),
            "unauthorized_mutations": self.leaf(evaluation, "/containment/unauthorized_mutations",
                                                "unauthorized mutations"),
            "configurations": self.leaf(verification, "/summary/states_explored",
                                        "bounded configurations explored"),
            "violations": self.leaf(verification, "/summary/violations", "invariant violations"),
            "invariants_checked": self.leaf(verification, "/summary/invariants_checked",
                                            "invariants checked"),
            "distinct_denial_controls": self.figure(
                "distinct_denial_codes", "distinct denial controls reached"),
            "ablations": self.leaf(evaluation, "/attribution/controls_load_bearing",
                                   "ablated controls that restored their harm",
                                   denominator="/attribution/controls_declared"),
            "conformance": {
                "backends": self.figure("conformance_backends_verified",
                                        "backend profiles verified"),
                "per_backend": [
                    {"backend": name,
                     "checks": self.leaf(f"{EVAL}conformance-{name}.json", "/summary/checks_passed",
                                         "conformance checks passed",
                                         denominator="/summary/checks_total")}
                    for name in ("memory", "sql")
                ],
            },
            "benign_tasks": self.leaf(evaluation, "/utility/benign_tasks_completed",
                                      "benign tasks completed",
                                      denominator="/utility/benign_tasks_total"),
            "false_denial_rate": self.leaf(evaluation, "/utility/false_denial_rate",
                                           "false-denial rate"),
            "race": {
                "callers": self.leaf(f"{EVAL}race.json", "/callers", "concurrent callers"),
                "mutations": self.leaf(f"{EVAL}race.json", "/mutations", "mutations"),
                "receipts": self.leaf(f"{EVAL}race.json", "/distinct_receipts", "distinct receipts"),
                "replayed": self.leaf(f"{EVAL}race.json", "/replayed", "replay responses"),
            },
        }

    def disclosure(self) -> dict[str, Any]:
        """The governed read path across the packs that declare disclosure."""
        rel = f"{EVAL}governed-disclosure.json"
        profiles = self.document(rel)["profiles"]
        return {
            "packs": self.figure("disclosure_packs", "disclosure packs"),
            "hostile_flows": self.figure("disclosure_contained", "hostile data flows contained",
                                         denominator="disclosure_hostile_total"),
            "load_bearing_checks": self.figure(
                "disclosure_checks_load_bearing", "checks load-bearing in every pack",
                denominator="disclosure_checks_ablated",
                note="summary takes the minimum load-bearing and maximum ablated over packs"),
            "configurations": self.figure("disclosure_states_explored",
                                          "read and release configurations explored"),
            "violations": self.figure("disclosure_violations", "invariant violations"),
            "legitimate_flows": self.figure("disclosure_benign_completed",
                                            "legitimate flows completed",
                                            denominator="disclosure_benign_total"),
            "stateful_sequences": self.figure("disclosure_stateful_sequences",
                                              "stateful operation sequences"),
            "stateful_operations": self.figure(
                "disclosure_stateful_steps_display", "stateful operations (display string)",
                note="the committed summary carries this total only as a display string"),
            "stateful_disagreements": self.figure("disclosure_stateful_disagreements",
                                                  "disagreements with the reference model"),
            "per_pack": [
                {"pack": profile["profile_id"],
                 "hostile_contained": self.leaf(
                     rel, pointer("profiles", i, "summary", "contained_by_arm", "this_architecture"),
                     "hostile data flows contained",
                     denominator=pointer("profiles", i, "summary", "hostile_scenarios")),
                 "load_bearing_checks": self.leaf(
                     rel, pointer("profiles", i, "summary", "checks_load_bearing"),
                     "checks load-bearing", denominator=pointer("profiles", i, "summary", "checks_ablated")),
                 "legitimate_flows": self.leaf(
                     rel, pointer("profiles", i, "summary", "benign_completed"),
                     "legitimate flows completed",
                     denominator=pointer("profiles", i, "summary", "benign_total")),
                 "configurations": self.leaf(
                     rel, pointer("profiles", i, "verification", "summary", "states_explored"),
                     "read and release configurations explored"),
                 "stateful_sequences": self.leaf(
                     rel, pointer("profiles", i, "stateful", "summary", "sequences"),
                     "stateful operation sequences"),
                 "stateful_operations": self.leaf(
                     rel, pointer("profiles", i, "stateful", "summary", "steps"),
                     "stateful operations")}
                for i, profile in enumerate(profiles)
            ],
        }

    def delegation(self) -> dict[str, Any]:
        """Composition under delegation."""
        verification = f"{EVAL}delegation-verification.json"
        delegation = f"{EVAL}delegation.json"
        risk = {arm: self.leaf(delegation, pointer("arms", arm, "contained"),
                               "risk classes contained", denominator=pointer("arms", arm, "of"))
                for arm in self.document(delegation)["arms"]}
        return {
            "chain_shapes": self.leaf(verification, "/states_explored",
                                      "enumerated delegation chain shapes"),
            "violations": self.figure("delegation_violations", "invariant violations"),
            "invariants_load_bearing": self.figure(
                "delegation_invariants_load_bearing", "delegation invariants load-bearing",
                denominator="delegation_invariants_ablated"),
            "risk_classes_by_arm": risk,
            "note": "caller_checked validates each hop against its immediate caller; "
                    "this_architecture verifies the full chain",
        }

    def review_capacity(self) -> dict[str, Any]:
        """Human review as a bounded resource (declared-parameter simulation)."""
        queue = f"{EVAL}oversight.json"
        sweep = f"{EVAL}oversight-sweep.json"
        assisted = f"{EVAL}assisted-review.json"

        def arm_leaves(rel: str, arm: str) -> dict[str, Any]:
            base = ("arms", arm)
            return {
                "arm": arm,
                "harmful_executed": self.leaf(rel, pointer(*base, "harmful_executed"),
                                              "merit failures executed",
                                              denominator=pointer(*base, "merit_refusals_required")),
                "benign_executed": self.leaf(rel, pointer(*base, "benign_executed"),
                                             "legitimate actions completed"),
                "deferred_to_manual": self.leaf(rel, pointer(*base, "deferred_to_manual_fallback"),
                                                "actions deferred to manual review"),
            }

        assisted_arms = [arm_leaves(assisted, arm) | {
            "deliberation_floor_seconds": self.leaf(
                assisted, pointer("arms", arm, "deliberation_floor_seconds"), "seconds")}
            for arm, body in self.document(assisted)["arms"].items() if body.get("started")]
        return {
            "note": "simulation with declared reviewer parameters; not a measurement of reviewers",
            "roster": self.figure("oversight_reviewer_roster", "reviewers (declared roster)"),
            "sustainable_per_day": self.figure("oversight_sustainable_per_day",
                                               "consequential actions per day"),
            "arrivals": self.leaf(queue, "/arrivals", "arrivals in the queue trial"),
            "attentive_capacity": self.leaf(queue, "/reviewer_model/attentive_until",
                                            "declared attentive capacity (arrivals)"),
            "queue_arms": [arm_leaves(queue, arm) for arm in self.document(queue)["arms"]],
            "sweep": {
                "cells": self.leaf(sweep, "/summary/cells_total", "parameter combinations"),
                "harm_possible": self.leaf(sweep, "/summary/cells_where_harm_was_possible",
                                           "cells where harm was possible",
                                           denominator="/summary/cells_total"),
                "load_bearing": self.leaf(sweep, "/summary/cells_where_the_control_was_load_bearing",
                                          "cells where the control was load-bearing",
                                          denominator="/summary/cells_where_harm_was_possible"),
                "harm_reached_zero": self.leaf(sweep, "/summary/cells_where_harm_reached_zero",
                                               "cells where harm reached zero",
                                               denominator="/summary/cells_where_harm_was_possible"),
                "false_positive_deferrals": self.leaf(
                    sweep, "/summary/deferrals_where_there_was_no_harm_to_contain",
                    "deferrals with no harm to contain"),
            },
            "assisted_arms": assisted_arms,
            "dependent_configuration_refused": self.leaf(
                assisted, "/summary/configuration_gate_refused_the_harmful_arm",
                "dependent assistant refused at configuration (boolean)"),
        }

    def transfer(self) -> dict[str, Any]:
        """Per-pack denominators from the domain-pack matrix, never merged."""
        rel = f"{EVAL}domain-pack-matrix.json"
        packs = []
        for i, pack in enumerate(self.document(rel)["profiles"]):
            base = ("profiles", i)
            packs.append({
                "pack": pack["profile_id"],
                "configurations": self.leaf(rel, pointer(*base, "states_explored"),
                                            "bounded configurations explored"),
                "violations": self.leaf(rel, pointer(*base, "violations"), "invariant violations"),
                "scenarios": self.leaf(rel, pointer(*base, "scenarios_contained"),
                                       "hostile scenarios contained",
                                       denominator=pointer(*base, "scenarios_total")),
                "benign_tasks": self.leaf(rel, pointer(*base, "benign_completed"),
                                          "benign tasks completed",
                                          denominator=pointer(*base, "benign_total")),
                "unauthorized_mutations": self.leaf(rel, pointer(*base, "unauthorized_mutations"),
                                                    "unauthorized mutations"),
            })
        return {
            "packs": packs,
            "reported_totals": {
                "note": "totals the result generator itself committed; each pack keeps its "
                        "own denominators above",
                "packs": self.figure("domains_verified", "independently reported domain packs"),
                "configurations": self.figure("domain_pack_states_explored",
                                              "bounded configurations explored"),
                "scenarios": self.figure("domain_pack_scenarios_contained",
                                         "hostile scenarios contained",
                                         denominator="domain_pack_scenarios_total"),
                "benign_tasks": self.figure("domain_pack_benign_completed", "benign tasks completed",
                                            denominator="domain_pack_benign_total"),
                "unauthorized_mutations": self.figure("domain_pack_unauthorized_mutations",
                                                      "unauthorized mutations"),
            },
            "academic_record_correction_conformance": self.leaf(
                f"{EVAL}conformance-second-domain.json", "/summary/checks_passed",
                "conformance checks passed", denominator="/summary/checks_total"),
        }

    def safety_case(self) -> dict[str, Any]:
        """Threat catalogue and falsification of the Mediation Thesis."""
        threats = f"{EVAL}threat-catalogue.json"
        thesis = f"{EVAL}mediation-thesis.json"
        adaptive = f"{CONFERENCE}adaptive-results.json"
        families = self.document(threats)["summary"]["by_family"]
        return {
            "threat_classes": {
                "total": self.leaf(threats, "/summary/threats", "failure classes"),
                "contained": self.leaf(threats, "/summary/contained", "failure classes contained",
                                       denominator="/summary/threats"),
                "bounded": self.leaf(threats, "/summary/bounded", "failure classes bounded",
                                     denominator="/summary/threats"),
                "residual": self.leaf(threats, "/summary/residual", "failure classes residual",
                                      denominator="/summary/threats"),
                "alignment": self.figure("threats_alignment_total", "alignment failure classes",
                                         denominator="threats_total"),
                "missing_locators": self.leaf(threats, "/summary/missing_locators",
                                              "evidence locators that do not exist"),
                "by_family": {
                    family: {status: self.leaf(threats, pointer("summary", "by_family", family, status),
                                               f"{family} failure classes {status}")
                             for status in counts}
                    for family, counts in families.items()
                },
            },
            "falsifiers": {
                "count": self.leaf(thesis, "/summary/falsifiers", "falsifiers"),
                "attempts": self.leaf(thesis, "/summary/attempts", "bounded attempts"),
                "counterexamples": self.leaf(thesis, "/summary/counterexamples", "counterexamples"),
                "per_falsifier": [
                    {"id": falsifier["id"], "name": falsifier["name"],
                     "attempts": self.leaf(thesis, pointer("falsifiers", i, "attempts"), "bounded attempts"),
                     "counterexamples": self.leaf(thesis, pointer("falsifiers", i, "counterexamples"),
                                                  "counterexamples")}
                    for i, falsifier in enumerate(self.document(thesis)["falsifiers"])
                ],
            },
            "positive_control": {
                "note": "education-demo adaptive attacker with one mediator removed; proves the "
                        "attacker and oracle are not a no-op",
                "control_removed": self.document(adaptive)["positive_control"]["control_removed"],
                "forbidden_outcomes": self.leaf(adaptive, "/positive_control/forbidden_outcomes",
                                                "episodes with a forbidden outcome",
                                                denominator="/positive_control/episodes"),
            },
        }

    def self_application(self) -> dict[str, Any]:
        """The contract applied to the repository's own requirements."""
        counts = claims_register_counts(self.register_root)
        legacy = {
            "machine_verified": self.figure("coverage_machine_verified",
                                            "requirements machine-verified",
                                            denominator="coverage_requirements"),
            "attested": self.figure("coverage_organizationally_attested",
                                    "requirements organizationally attested",
                                    denominator="coverage_requirements"),
            "unverified": self.figure("coverage_unverified", "requirements unverified",
                                      denominator="coverage_requirements"),
        }
        contract_counts = counts.get("contract", {})
        disagreement = {cls: (contract_counts.get(cls), leaf["value"])
                        for cls, leaf in legacy.items() if contract_counts.get(cls) != leaf["value"]}
        if disagreement:
            raise CollectionError(f"claims register disagrees with the committed summary: {disagreement}")
        self.read.update(self._contract_files())

        def register_leaf(source: str, cls: str) -> dict[str, Any]:
            return {"value": counts[source][cls], "denominator": None,
                    "unit": f"register rows {cls}",
                    "source": "contract/",
                    "derivation": {"op": "claims_register", "row_source": source, "class": cls,
                                   "call": "fssaira.kernel.claims.build_register(ROOT).counts()"}}

        return {
            "note": "the register is computed from the contract files at collection time; "
                    "its legacy-contract rows must agree with the committed summary",
            "claims_register": {source: {cls: register_leaf(source, cls) for cls in counts[source]}
                                for source in counts},
            "legacy_contract_counts": legacy,
            "legacy_counts_agree": True,
        }

    def _contract_files(self) -> set[str]:
        contract = self.register_root / "contract"
        return {str(path.relative_to(self.register_root)) for path in sorted(contract.rglob("*.yaml"))}

    def education_demo(self) -> dict[str, Any]:
        """The earlier governed-learning conference package (one synthetic pack)."""
        redteam = f"{CONFERENCE}redteam-results.json"
        concurrency = f"{CONFERENCE}concurrency-results.json"
        adaptive = f"{CONFERENCE}adaptive-results.json"
        removed_key = next(key for key in self.document(redteam)
                           if key.startswith("successes_when_one_control_removed"))
        removed_attempts = self.key_name_leaf(
            redteam, pointer(removed_key), "red-team attempts per removed control",
            note="the source declares this denominator only in its key name")
        summary = self.document(f"{CONFERENCE}summary.json")["figures"]
        callers_key = next(key for key in self.document(concurrency)["in_memory_executor"]
                           if int(key) == max(int(k) for k in self.document(concurrency)["in_memory_executor"]))
        return {
            "scope": self.leaf(f"{CONFERENCE}summary.json", "/scope", "scope statement"),
            "falsifiers": self.conference("falsifiers_held", "falsifiers held", denominator="falsifiers"),
            "attacks_blocked": self.conference("blocked_attacks", "attack attempts blocked",
                                               denominator="attack_attempts"),
            "attacks_succeeded": self.conference("successful_attacks", "attack attempts succeeded",
                                                 denominator="attack_attempts"),
            "ablations": self.conference("ablation_load_bearing", "ablations that restored harm",
                                         denominator="ablation_rows"),
            "ablation_redundant_single_controls": self.conference(
                "ablation_redundant_single_controls", "single controls independently backed",
                denominator="ablation_rows"),
            "stateful": {
                "sequences": self.conference("stateful_sequences", "stateful sequences"),
                "steps": self.conference("stateful_steps", "stateful steps"),
                "violations": self.conference("stateful_violations", "violations"),
                "false_denials": self.conference("stateful_false_denials", "false denials"),
                "violations_when_control_removed": {
                    control: self.leaf(
                        f"{CONFERENCE}summary.json",
                        pointer("figures", "stateful_violations_when_control_removed", control),
                        f"violations with {control} removed")
                    for control in summary["stateful_violations_when_control_removed"]
                },
            },
            "conformance": self.conference("conformance_pass", "conformance requirements passing",
                                           denominator="conformance_requirements"),
            "malicious_pack_findings": self.conference("malicious_pack_findings",
                                                       "kernel-floor findings on a malicious pack"),
            "education_pack_findings": self.conference("education_pack_findings",
                                                       "kernel-floor findings on the education pack"),
            "delegation_escalations": self.conference("delegation_escalations_refused",
                                                      "delegation escalations refused",
                                                      denominator="delegation_escalation_cases"),
            "model_substitution": self.conference("model_attestation_attacks_refused",
                                                  "model-substitution attacks refused",
                                                  denominator="model_attestation_attacks"),
            "identity_values_seen_by_model": self.conference("identity_values_seen_by_model",
                                                             "identity values seen by the model"),
            "erasure": self.conference("erasure_readable_locations",
                                       "locations readable after erasure",
                                       denominator="erasure_locations_checked"),
            "concurrency": {
                "callers": self.key_name_leaf(
                    concurrency, pointer("in_memory_executor", callers_key), "concurrent callers",
                    note="the source keys each race by its caller count"),
                "mutations": self.leaf(concurrency, pointer("in_memory_executor", callers_key, "mutations"),
                                       "mutations"),
            },
            "overload_approved_without_human": self.conference("overload_approved_without_human",
                                                               "overload approvals without a human"),
            "ten_step_traces": self.conference("ten_step_traces", "ten-step traces"),
            "redteam": {
                "successes": self.conference("redteam_successes", "red-team successes",
                                             denominator="redteam_attempts"),
                "attempts_per_removed_control": removed_attempts,
                "successes_when_one_control_removed": {
                    control: {**self.leaf(redteam, pointer(removed_key, control),
                                          f"red-team successes with {control} removed"),
                              "denominator": removed_attempts["value"],
                              "denominator_source": removed_attempts["source"],
                              "denominator_derivation": {"op": "key_name"}}
                    for control in self.document(redteam)[removed_key]
                },
            },
            "claims": self.conference("claims_pass", "register claims passing", denominator="claims"),
            "adaptive": {
                "tracks": [
                    {"attacker": track["attacker"],
                     "forbidden_outcomes": self.leaf(adaptive, pointer("tracks", i, "forbidden_outcomes"),
                                                     "episodes with a forbidden outcome",
                                                     denominator=pointer("tracks", i, "episodes"))}
                    for i, track in enumerate(self.document(adaptive)["tracks"])
                ],
                "positive_control": self.leaf(adaptive, "/positive_control/forbidden_outcomes",
                                              "episodes with a forbidden outcome, one mediator removed",
                                              denominator="/positive_control/episodes"),
            },
        }

    def joined_workflow(self) -> dict[str, Any]:
        """Table 5 and the joined-workflow adaptive run, counted from raw episodes."""
        document = self.document(ADAPTIVE)
        rows = document["rows"]
        raw = all(isinstance(row.get("runs"), list) and row["runs"]
                  and all("outcome" in run for run in row["runs"]) for row in rows)
        cells = []
        for i, row in enumerate(rows):
            base = ("rows", i)
            if raw:
                runs = pointer(*base, "runs")
                unsupported = self.derived_leaf(
                    ADAPTIVE, runs, {"op": "count_where_positive", "field": "/outcome/unsupported_correction"},
                    pointer(*base, "unsupported_corrections"), "episodes with an unsupported correction",
                    denominator=({"op": "length"}, pointer(*base, "episodes")))
                mutations = self.derived_leaf(
                    ADAPTIVE, runs, {"op": "sum_field", "field": "/outcome/unauthorized_subject_effect"},
                    pointer(*base, "unauthorized_subject_effects"), "unauthorized subject mutations")
                sink = self.derived_leaf(
                    ADAPTIVE, runs, {"op": "sum_field", "field": "/outcome/unauthorized_bytes"},
                    pointer(*base, "unauthorized_bytes"), "unauthorized sink bytes")
            else:
                unsupported = self.leaf(ADAPTIVE, pointer(*base, "unsupported_corrections"),
                                        "episodes with an unsupported correction",
                                        denominator=pointer(*base, "episodes"))
                mutations = self.leaf(ADAPTIVE, pointer(*base, "unauthorized_subject_effects"),
                                      "unauthorized subject mutations")
                sink = self.leaf(ADAPTIVE, pointer(*base, "unauthorized_bytes"), "unauthorized sink bytes")
            cells.append({
                "arm": row["arm"], "strategy": row["strategy"],
                "unsupported_corrections": unsupported,
                "legitimate_completed": self.leaf(ADAPTIVE, pointer(*base, "legitimate_completed"),
                                                  "legitimate workflows completed",
                                                  denominator=pointer(*base, "legitimate_attempted")),
                "unauthorized_subject_mutations": mutations,
                "unauthorized_sink_bytes": sink,
            })
        cases = self.document(LIVE_LOCAL)["cases"]
        return {
            "method": (
                "Table 5 cells counted from raw per-episode records (rows[*].runs[*].outcome) in "
                "audit/adaptive-results.json and cross-checked against each row's summary fields; "
                "legitimate completion read from row summary fields (no raw record exists)"
                if raw else
                "Table 5 cells read from row summary fields in audit/adaptive-results.json "
                "(raw per-episode records absent)"),
            "arms": list(dict.fromkeys(row["arm"] for row in rows)),
            "strategies": list(dict.fromkeys(row["strategy"] for row in rows)),
            "config": {
                "training_episodes": self.leaf(ADAPTIVE, "/training_episodes", "training episodes"),
                "steps_per_episode": self.leaf(ADAPTIVE, "/steps_per_episode", "requests per episode (cap)"),
                "time_limit_seconds_per_episode": self.leaf(ADAPTIVE, "/time_limit_seconds_per_episode",
                                                            "seconds per episode (cap)"),
                "learning": self.leaf(ADAPTIVE, "/learning", "learning parameters (declared string)"),
                "training_environment": self.leaf(ADAPTIVE, "/training_environment",
                                                  "training environment (declared string)"),
                "language_model_RL": self.leaf(ADAPTIVE, "/language_model_RL", "status"),
            },
            "table5": {"unit": "episode; one legitimate workflow per arm and strategy", "cells": cells},
            "live_local": {
                "model": self.leaf(LIVE_LOCAL, "/model", "local model"),
                "prompts": {"value": len(cases), "denominator": None, "unit": "fresh local prompts",
                            "source": f"{LIVE_LOCAL}#/cases", "derivation": {"op": "length"}},
                "sink_count": {"value": sum(case["sink_count"] for case in cases), "denominator": None,
                               "unit": "released outputs", "source": f"{LIVE_LOCAL}#/cases",
                               "derivation": {"op": "sum_field", "field": "/sink_count"}},
            },
        }

    # -----------------------------------------------------------------------
    def collect(self) -> dict[str, Any]:
        """Build the whole document, sources last."""
        document: dict[str, Any] = {
            "generated_by": GENERATED_BY,
            "schema_version": SCHEMA_VERSION,
            "reading": (
                "Every leaf is {value, denominator, unit, source}. Units differ between suites "
                "(scenario, configuration, sequence, ablation, task, episode) and must never be "
                "pooled into one percentage."),
            "comparison_arms": self.comparison_arms(),
            "reference_profile": self.reference_profile(),
            "disclosure": self.disclosure(),
            "delegation": self.delegation(),
            "review_capacity": self.review_capacity(),
            "transfer": self.transfer(),
            "safety_case": self.safety_case(),
            "self_application": self.self_application(),
            "education_demo": self.education_demo(),
            "joined_workflow": self.joined_workflow(),
        }
        document["sources"] = {
            rel: sha256_file((self.register_root if rel.startswith("contract/") else self.root) / rel)
            for rel in sorted(self.read)
        }
        return document


def collect(root: Path = ROOT, register_root: Path | None = None) -> dict[str, Any]:
    """Collect ``audit/results.json`` content for the repository at ``root``."""
    return Collector(root, register_root).collect()


def encode(document: dict[str, Any]) -> str:
    """Deterministic JSON text."""
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def check(root: Path = ROOT, register_root: Path | None = None,
          committed: Path | None = None) -> list[str]:
    """Differences between a fresh collection and the committed file (empty if none)."""
    path = committed or (Path(root) / OUTPUT)
    if not path.exists():
        return [f"no committed results at {path}"]
    fresh = collect(root, register_root)
    stored = json.loads(path.read_text(encoding="utf-8"))
    fresh.pop("generated_by", None)
    stored.pop("generated_by", None)
    keys = sorted(set(fresh) | set(stored))
    return [f"{key} differs" for key in keys if fresh.get(key) != stored.get(key)]


def iter_leaves(node: Any, path: str = "") -> list[tuple[str, dict[str, Any]]]:
    """Every provenance leaf in a results document, with its JSON pointer."""
    found: list[tuple[str, dict[str, Any]]] = []
    if isinstance(node, dict):
        if "value" in node and "source" in node:
            return [(path, node)]
        for key, child in node.items():
            if key != "sources":
                found += iter_leaves(child, f"{path}/{escape_token(key)}")
    elif isinstance(node, list):
        for index, child in enumerate(node):
            found += iter_leaves(child, f"{path}/{index}")
    return found


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="rebuild in memory and compare with the committed audit/results.json")
    args = parser.parse_args()
    try:
        if args.check:
            drift = check()
            if drift:
                print("audit/results.json has drifted from its sources: " + "; ".join(drift)
                      + "\nregenerate with: python scripts/collect_results.py")
                return 1
            print(f"audit/results.json matches its committed sources "
                  f"({len(iter_leaves(collect()))} leaves)")
            return 0
        document = collect()
    except CollectionError as exc:
        print(f"collection refused: {exc}")
        return 1
    (ROOT / OUTPUT).write_text(encode(document), encoding="utf-8")
    print(f"wrote {OUTPUT} ({len(iter_leaves(document))} leaves, {len(document['sources'])} sources)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
