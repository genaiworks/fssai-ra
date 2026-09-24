"""Lifecycle stages as gates over real enforcement code.

Every gate returns a :class:`GateOutcome` computed by running the check. None
reads a status file someone could edit. A stage passes only if all its gates
pass; its artifact records what each gate observed, with denominators.
"""
from __future__ import annotations

import hashlib
import inspect
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml

from fssaira.kernel.contract import ContractError, load_capability_contracts, verify_bindings

ROOT = Path(__file__).resolve().parents[3]
CREDENTIAL_WORDS: tuple[str, ...] = ("token", "key", "credential", "secret", "signing", "custody")


@dataclass(frozen=True)
class GateOutcome:
    gate: str
    passed: bool
    detail: str
    observed: dict = field(default_factory=dict)


@dataclass
class StageResult:
    stage: str
    gates: list[GateOutcome] = field(default_factory=list)
    artifact: dict = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return bool(self.gates) and all(g.passed for g in self.gates)

    def gate(self, gate_id: str) -> GateOutcome:
        return next(g for g in self.gates if g.gate == gate_id)

    def to_dict(self) -> dict:
        return {"stage": self.stage, "passed": self.passed,
                "gates": [asdict(g) for g in self.gates], "artifact": self.artifact}


# -- 1. frame --------------------------------------------------------------

FRAME_FIELDS: tuple[str, ...] = (
    "capability", "protected_asset", "harm", "accountable_owner", "manual_fallback",
)


def frame(path: Path) -> StageResult:
    """Name one consequential capability, its asset, harm, owner and manual fallback."""
    result = StageResult("frame")
    doc = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if isinstance(doc.get("capabilities"), list):
        result.gates.append(GateOutcome(
            "one_capability", False,
            "frame one consequential capability at a time; start with one and a manual fallback"))
        return result
    empty = [name for name in FRAME_FIELDS if not str(doc.get(name, "")).strip()]
    result.gates.append(GateOutcome(
        "frame_complete", not empty,
        "all framing fields present" if not empty
        else f"open governance decision(s): {', '.join(empty)}",
        {"missing": empty}))
    if not empty:
        body = {name: str(doc[name]).strip() for name in FRAME_FIELDS}
        result.artifact = {**body, "digest": hashlib.sha256(
            json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()}
    return result


# -- 2. contract -----------------------------------------------------------

def contract(root: Path = ROOT, *, register_out: Path | None = None) -> StageResult:
    """Seven fields filled, every named test present, no unverified claim."""
    from fssaira.kernel.claims import build_register

    root = Path(root)
    result = StageResult("contract")
    try:
        capabilities = load_capability_contracts(root / "contract" / "capabilities", root=root)
        result.gates.append(GateOutcome("contract_complete", True,
                                        f"{len(capabilities)} capability contracts with all seven fields",
                                        {"capabilities": len(capabilities)}))
    except ContractError as exc:
        result.gates.append(GateOutcome("contract_complete", False, str(exc)))
        return result

    findings = verify_bindings(root / "contract", root=root)
    result.gates.append(GateOutcome(
        "failure_tests_exist", not findings,
        "every binding and failure test resolves" if not findings else "; ".join(findings),
        {"unresolved": len(findings)}))
    if findings:
        return result

    register = build_register(root)
    counts = register.counts()
    result.gates.append(GateOutcome(
        "claims_register_no_unverified", counts["unverified"] == 0,
        f"machine_verified {counts['machine_verified']}, attested {counts['attested']}, "
        f"unverified {counts['unverified']} of {len(register.rows)} claims",
        {"counts": counts, "denominator": len(register.rows)}))
    result.artifact = {"counts": counts, "counts_by_source": {
        source: register.counts(source) for source in sorted({r.source for r in register.rows})}}
    if register_out is not None:
        Path(register_out).write_text(register.to_yaml(), encoding="utf-8")
        result.artifact["register"] = str(register_out)
    return result


# -- 4. bind ---------------------------------------------------------------

def _credential_parameters(component: object) -> list[str]:
    try:
        params = inspect.signature(component).parameters  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return []
    return [name for name in params if any(word in name.lower() for word in CREDENTIAL_WORDS)]


def check_no_model_holds_a_key(planes: Iterable[object] | None = None) -> GateOutcome:
    """No untrusted component takes a credential, and a live agent holds none.

    Two checks, because either alone can be evaded: a constructor parameter named
    like a credential, and the credential *value* present on a constructed agent.
    """
    from fssaira.pipeline import EVIDENCE_TOKEN, FSSAIRAPipeline
    from fssaira.planes import ALL_PLANES

    chosen = list(planes) if planes is not None else list(ALL_PLANES)
    leaks: list[str] = []
    checked = 0
    for plane in chosen:
        if not getattr(plane, "untrusted", False):
            continue
        for reference, component in plane.load_components().items():  # type: ignore[attr-defined]
            checked += 1
            leaks.extend(f"{reference}({name})" for name in _credential_parameters(component))

    pipeline = FSSAIRAPipeline()
    agent = pipeline.make_agent("bind-gate", tools={"read_case"}, operations={"read_case"})
    for holder in (agent, agent.agent):
        checked += 1
        leaks.extend(f"{type(holder).__name__}.{name}" for name, value in vars(holder).items()
                     if value == EVIDENCE_TOKEN)
    return GateOutcome(
        "no_model_holds_a_key", not leaks,
        f"{checked} untrusted components and live objects checked; no credential held" if not leaks
        else f"credential reachable from the untrusted side: {', '.join(leaks)}",
        {"checked": checked, "leaks": leaks})


def bind(root: Path = ROOT) -> StageResult:
    """Credentials, record access and keys belong to mediators only."""
    result = StageResult("bind")
    result.gates.append(check_no_model_holds_a_key())
    return result


# -- governed configuration digest ------------------------------------------

#: What a falsification run is evidence *about*. If any of it changes, the
#: capability returns to stage 5 (paper §6, stage 7).
GOVERNED_GLOBS: tuple[str, ...] = (
    "src/fssaira/kernel/**/*.py",
    "src/fssaira/mediators/**/*.py",
    "src/fssaira/planes/**/*.py",
    "contract/**/*.yaml",
    "packs/*.yaml",
    "profiles/*.yaml",
    "conference/education/*.yaml",
)


def governed_digest(root: Path = ROOT) -> dict:
    """Digest the governed configuration: kernel, mediators, planes, contracts, packs.

    Paths are included, so a renamed or deleted file changes the digest as well
    as an edited one.
    """
    root = Path(root)
    files = sorted({
        path for pattern in GOVERNED_GLOBS for path in root.glob(pattern)
        if path.is_file() and "__pycache__" not in path.parts
    })
    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8") + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii") + b"\n")
    return {"sha256": digest.hexdigest(), "files": len(files), "globs": list(GOVERNED_GLOBS)}


# -- 5. falsify ------------------------------------------------------------

def falsify(root: Path = ROOT, *, include_ablation: bool = True,
            conference_only: Iterable[str] | None = None) -> StageResult:
    """Try to refute the thesis; prove the falsifiers are not no-ops; ablate controls."""
    from fssaira import falsification
    from fssaira.thesis import run_thesis

    result = StageResult("falsify")
    thesis = run_thesis(Path(root))
    conference = falsification.run_falsifiers(conference_only)
    conference_attempts = sum(len(r.attempts) for r in conference)
    conference_violations = sum(r.violations for r in conference)

    # Positive control: remove the controls a falsifier names; it must find harm.
    probe = conference[0] if conference else None
    control_violations = 0
    if probe is not None:
        item = falsification.falsifier(probe.id)
        weakened = [c for c in falsification.ALL_CONTROLS if c not in item.controls]
        control_violations = falsification.run_one(item, weakened).violations

    zero = thesis.counterexamples == 0 and conference_violations == 0
    live = control_violations > 0
    result.gates.append(GateOutcome(
        "falsifiers_zero_counterexamples", zero and live,
        (f"thesis: {thesis.counterexamples} counterexamples in {thesis.attempts} attempts; "
         f"conference: {conference_violations} violations in {conference_attempts} attempts "
         f"across {len(conference)} falsifiers; positive control "
         f"({probe.id if probe else 'none'} with its controls removed): {control_violations} violations"),
        {"thesis_attempts": thesis.attempts, "thesis_counterexamples": thesis.counterexamples,
         "conference_falsifiers": len(conference), "conference_attempts": conference_attempts,
         "conference_violations": conference_violations,
         "positive_control_violations": control_violations}))

    if include_ablation:
        rows = falsification.run_ablation(conference_only)
        dirty = [r for r in rows if r.enabled or r.restored]
        by_falsifier: dict[str, bool] = {}
        for row in rows:
            by_falsifier[row.falsifier] = by_falsifier.get(row.falsifier, False) or row.load_bearing
        unbacked = sorted(f for f, bearing in by_falsifier.items() if not bearing)
        redundant = [f"{r.falsifier}:{r.control}" for r in rows if not r.load_bearing and not r.enabled
                     and not r.restored]
        result.gates.append(GateOutcome(
            "ablations_restore_harm", not dirty and not unbacked,
            (f"{sum(r.load_bearing for r in rows)} of {len(rows)} ablations restored harm; "
             f"every falsifier has a load-bearing control or declared pair"
             if not dirty and not unbacked else
             f"harm with controls on or after restore: {[r.falsifier for r in dirty]}; "
             f"falsifiers with no load-bearing group: {unbacked}"),
            {"rows": len(rows), "load_bearing": sum(r.load_bearing for r in rows),
             "defence_in_depth_rows": redundant}))
    result.artifact = {"thesis": thesis.to_dict()["summary"], "governed_digest": governed_digest(Path(root))}
    return result


# -- 7. operate ------------------------------------------------------------

def operate(root: Path = ROOT, *, falsify_artifact: Path | None = None,
            executor: object | None = None, monitor: object | None = None) -> StageResult:
    """Keep what was falsified the thing that runs; reconcile; stay inside review capacity.

    ``executor`` and ``monitor`` are live objects in a running deployment. When
    either is absent its gate is reported under ``not_run``, never as passed.
    """
    root = Path(root)
    result = StageResult("operate")
    current = governed_digest(root)
    not_run: list[dict] = []

    if falsify_artifact is None or not Path(falsify_artifact).is_file():
        result.gates.append(GateOutcome(
            "change_returns_to_falsify", False,
            "no falsification artifact; run `fssaira falsify --out <file>` and pass it here",
            {"current_digest": current["sha256"]}))
    else:
        recorded = json.loads(Path(falsify_artifact).read_text(encoding="utf-8"))
        recorded_digest = ((recorded.get("artifact") or {}).get("governed_digest") or {}).get("sha256")
        passed_before = recorded.get("passed") is True
        unchanged = recorded_digest == current["sha256"]
        detail = ("governed configuration unchanged since a passing falsification run"
                  if passed_before and unchanged else
                  "the recorded falsification run did not pass; return to stage 5" if not passed_before else
                  "governed configuration changed since falsification; return to stage 5")
        result.gates.append(GateOutcome(
            "change_returns_to_falsify", passed_before and unchanged, detail,
            {"recorded_digest": recorded_digest, "current_digest": current["sha256"],
             "recorded_passed": passed_before}))

    if executor is None:
        not_run.append({"gate": "reconciliation_clear", "reason": "no live executor supplied"})
    else:
        pending = executor.pending_outcome_count  # type: ignore[attr-defined]
        count = int(pending() if callable(pending) else pending)
        result.gates.append(GateOutcome(
            "reconciliation_clear", count == 0,
            "no uncertain effect awaits reconciliation" if count == 0 else
            f"{count} uncertain effect(s) await reconciliation; do not retry, reconcile",
            {"pending_outcomes": count}))

    if monitor is None:
        not_run.append({"gate": "review_capacity_not_breached", "reason": "no live oversight monitor supplied"})
    else:
        report = monitor.report()  # type: ignore[attr-defined]
        headroom = float(report.headroom)
        result.gates.append(GateOutcome(
            "review_capacity_not_breached", headroom > 0.0,
            f"worst-reviewer headroom {headroom:.2%} of the declared per-window ceiling" if headroom > 0.0
            else "a reviewer is saturated; new consequential work takes the manual fallback",
            {"headroom": headroom, "approvals": report.approvals,
             "declared_consistency": monitor.policy.declared_consistency()}))  # type: ignore[attr-defined]

    result.artifact = {"governed_digest": current, "not_run": not_run}
    return result
