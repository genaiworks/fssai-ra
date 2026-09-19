"""Lifecycle stages as gates over real enforcement code.

Most gates are computed by running a check against the repository or a live
object. Two places accept an artifact instead: ``operate`` and teaching-profile
``promote`` read a falsification artifact. An artifact is trusted-host evidence,
a JSON file anyone with write access could forge. It is accepted only if it
records a complete scope (every falsifier, ablation on) and matches the current
governed digest. Consequential promotion re-runs falsification rather than
trusting a file. A stage passes only if all its gates pass; its artifact records
what each gate observed, with denominators.
"""
from __future__ import annotations

import contextlib
import hashlib
import inspect
import json
import types
from collections import deque
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from fssaira.kernel.contract import ContractError, load_capability_contracts, verify_bindings

if TYPE_CHECKING:
    from fssaira.kernel.assurance import ConformanceRecord

ROOT = Path(__file__).resolve().parents[3]
CREDENTIAL_WORDS: tuple[str, ...] = ("token", "key", "credential", "secret", "signing", "custody")
FALSIFY_GATES: tuple[str, ...] = ("falsifiers_zero_counterexamples", "ablations_restore_harm")


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
    try:
        doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        result.gates.append(GateOutcome("frame_complete", False, f"frame unreadable: {exc}"))
        return result
    if not isinstance(doc, dict):
        result.gates.append(GateOutcome("frame_complete", False, "a frame must be a mapping of the framing fields"))
        return result
    if isinstance(doc.get("capabilities"), list):
        result.gates.append(GateOutcome(
            "one_capability", False,
            "frame one consequential capability at a time; start with one and a manual fallback"))
        return result
    # A YAML null must not become the string "None" and count as filled.
    empty = [name for name in FRAME_FIELDS
             if not isinstance(doc.get(name), str) or not doc[name].strip()]
    result.gates.append(GateOutcome(
        "frame_complete", not empty,
        "all framing fields present" if not empty
        else f"open governance decision(s): {', '.join(empty)}",
        {"missing": empty}))
    if not empty:
        body = {name: doc[name].strip() for name in FRAME_FIELDS}
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

    try:
        findings = verify_bindings(root / "contract", root=root)
    except (ContractError, ValueError, OSError) as exc:
        findings = [f"bindings unreadable: {exc}"]
    result.gates.append(GateOutcome(
        "failure_tests_exist", not findings,
        "every binding and failure test resolves" if not findings else "; ".join(findings),
        {"unresolved": len(findings)}))
    if findings:
        return result

    try:
        register = build_register(root)
    except (ContractError, ValueError, OSError) as exc:
        result.gates.append(GateOutcome("claims_register_no_unverified", False, f"register not built: {exc}"))
        return result
    counts = register.counts()
    result.gates.append(GateOutcome(
        "claims_register_no_unverified", counts["unverified"] == 0 and bool(register.rows),
        f"machine_verified {counts['machine_verified']}, attested {counts['attested']}, "
        f"unverified {counts['unverified']} of {len(register.rows)} claims",
        {"counts": counts, "denominator": len(register.rows)}))
    result.artifact = {"counts": counts, "counts_by_source": {
        source: register.counts(source) for source in sorted({r.source for r in register.rows})}}
    if register_out is not None:
        Path(register_out).write_text(register.to_yaml(), encoding="utf-8")
        result.artifact["register"] = str(register_out)
    return result


# -- 3. pack ---------------------------------------------------------------

TEMPLATE_PACK = "template.pack.yaml"


def _full(ratio: object) -> bool:
    """Complete means every one of a non-empty denominator; 0 of 0 is not complete."""
    return ratio.denominator > 0 and ratio.numerator == ratio.denominator  # type: ignore[attr-defined]


def pack(root: Path = ROOT, *, paths: Iterable[Path] | None = None, evaluate: bool = False) -> StageResult:
    """Every pack loads drift-free at or above the kernel floor; optionally regenerate its evidence.

    The shipped template is excluded from the repository-wide run because its
    ``REPLACE_ME`` placeholders are designed to fail until an author fills them.
    """
    from fssaira.kernel.packs import PackError, evaluate_pack, load_pack

    root = Path(root)
    chosen = ([Path(p) for p in paths] if paths else
              sorted(p for p in (root / "packs").glob("*.pack.yaml") if p.name != TEMPLATE_PACK))
    result = StageResult("pack")
    loaded = []
    failures: list[dict] = []
    for path in chosen:
        try:
            loaded.append(load_pack(path, root=root))
        except PackError as exc:
            failures.append({"pack": str(path),
                             "findings": [f"{f.code} at {f.where}: {f.detail}" for f in exc.findings]})
        except (ValueError, OSError) as exc:  # fail as a gate, never as a traceback
            failures.append({"pack": str(path), "findings": [f"{type(exc).__name__}: {exc}"]})
    ok = bool(chosen) and not failures
    result.gates.append(GateOutcome(
        "pack_floor_passes", ok,
        (f"{len(loaded)} of {len(chosen)} packs load drift-free at or above the kernel floor"
         if ok else f"{len(failures)} of {len(chosen)} packs refused" if chosen else "no pack found"),
        {"loaded": len(loaded), "denominator": len(chosen), "failures": failures,
         "floor_exemptions": {m.sector: list(m.floor_exemptions) for m in loaded}}))

    if evaluate and loaded:
        incomplete: list[str] = []
        evaluations: list[dict] = []
        for manifest in loaded:
            evaluation = evaluate_pack(manifest)
            evaluations.append(asdict(evaluation))
            if not evaluation.action:
                incomplete.append(f"{manifest.sector}: no action profile evaluated")
            for action in evaluation.action:
                if (not action.invariants_hold or action.violations.value or action.unauthorized_mutations.value
                        or action.states_explored.value <= 0
                        or not _full(action.scenarios) or not _full(action.benign)):
                    incomplete.append(f"{manifest.sector}:{action.profile_id}:action")
            for disclosure in evaluation.disclosure:
                if not (_full(disclosure.hostile) and _full(disclosure.benign) and _full(disclosure.checks)):
                    incomplete.append(f"{manifest.sector}:{disclosure.profile_id}:disclosure")
        result.gates.append(GateOutcome(
            "pack_evidence_regenerates", not incomplete,
            ("every pack's hostile scenarios contained, benign tasks completed, checks load-bearing, "
             "zero violations and zero unauthorized mutations" if not incomplete
             else f"incomplete: {incomplete}"),
            {"evaluations": evaluations, "incomplete": incomplete}))

    result.artifact = {"packs": [
        {"sector": m.sector, "path": str(m.path), "limits": list(m.limits),
         "floor_exemptions": list(m.floor_exemptions)} for m in loaded]}
    return result


# -- 4. bind ---------------------------------------------------------------

def _credential_parameters(component: object) -> list[str]:
    try:
        params = inspect.signature(component).parameters  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return []
    return [name for name in params if any(word in name.lower() for word in CREDENTIAL_WORDS)]


_LEAVES = (bytes, bytearray, int, float, complex, bool, type(None))


def find_reachable_secret(start: object, secret: str, *, label: str = "model", max_depth: int = 8,
                          stop: Iterable[object] = ()) -> list[str]:
    """Paths from ``start`` to a string equal to ``secret``, walking object references.

    Follows instance attributes, slots, containers, bound-method ``__self__`` and
    closure cells. It deliberately does not follow modules, classes or function
    globals: those make everything in a process reachable. Objects in ``stop``
    (the mediators) are not entered; that they are reachable is reported by the
    caller as an in-process limit, not a leak of the model.
    """
    stop_ids = {id(obj) for obj in stop}
    seen: set[int] = set()
    found: list[str] = []
    queue: deque[tuple[object, str, int]] = deque([(start, label, 0)])
    while queue:
        obj, path, depth = queue.popleft()
        if isinstance(obj, str):
            if obj == secret:
                found.append(path)
            continue
        if isinstance(obj, (*_LEAVES, type, types.ModuleType)):
            continue
        if id(obj) in seen or id(obj) in stop_ids or depth >= max_depth:
            continue
        seen.add(id(obj))
        children: list[tuple[object, str]] = []
        if isinstance(obj, dict):
            children += [(k, f"{path}<key>") for k in obj]
            children += [(v, f"{path}[{k!r}]") for k, v in obj.items()]
        elif isinstance(obj, (list, tuple, set, frozenset, deque)):
            children += [(v, f"{path}[{i}]") for i, v in enumerate(obj)]
        else:
            if inspect.ismethod(obj):
                children.append((obj.__self__, f"{path}.__self__"))
                obj = obj.__func__
            if isinstance(obj, types.FunctionType):
                for index, cell in enumerate(obj.__closure__ or ()):
                    with contextlib.suppress(ValueError):  # an empty cell has no contents
                        children.append((cell.cell_contents, f"{path}.<closure {index}>"))
            attributes = getattr(obj, "__dict__", None)
            if isinstance(attributes, dict):
                children += [(v, f"{path}.{k}") for k, v in attributes.items()]
            for slot in getattr(type(obj), "__slots__", ()) or ():
                if isinstance(slot, str) and hasattr(obj, slot):
                    children.append((getattr(obj, slot), f"{path}.{slot}"))
        queue.extend((child, child_path, depth + 1) for child, child_path in children)
    return found


def check_no_model_holds_a_key(planes: Iterable[object] | None = None, *, model: object | None = None) -> GateOutcome:
    """No untrusted component takes a credential, and nothing reachable from the model carries one.

    Three checks, because each alone can be evaded: a constructor parameter named
    like a credential; the credential value stored directly on the agent wrapper
    or its grant; and the credential value reachable, at any depth, from the model
    object the untrusted side runs as. The wrapper's reference to the enforcement
    point is reported, not hidden: in one process a mediator reference makes its
    credential reachable to code with the wrapper's privileges, which is why
    process isolation is a deployment obligation.
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
    mediators = (pipeline.pep, pipeline.evidence, pipeline.import_boundary)
    for holder in (agent, agent.agent):
        checked += 1
        leaks.extend(f"{type(holder).__name__}.{name}" for name, value in vars(holder).items()
                     if isinstance(value, str) and value == EVIDENCE_TOKEN)
    target = model if model is not None else agent.model
    checked += 1
    leaks.extend(find_reachable_secret(target, EVIDENCE_TOKEN, stop=mediators))
    mediator_refs = sorted(name for name, value in vars(agent).items()
                           if any(value is m for m in mediators))
    return GateOutcome(
        "no_model_holds_a_key", not leaks,
        (f"{checked} untrusted components and live objects checked; no credential reachable from the model. "
         f"The agent wrapper holds mediator reference(s) {mediator_refs}: in-process reachability is not "
         "isolation" if not leaks
         else f"credential reachable from the untrusted side: {', '.join(leaks)}"),
        {"checked": checked, "leaks": leaks, "mediator_references": mediator_refs})


def bind(root: Path = ROOT) -> StageResult:
    """Credentials, record access and keys belong to mediators only."""
    result = StageResult("bind")
    result.gates.append(check_no_model_holds_a_key())
    return result


# -- governed configuration digest ------------------------------------------

#: What a falsification run is evidence *about*: the enforcement code itself, the
#: gates, the named failure tests, and the declarations they check. If any of it
#: changes, the capability returns to stage 5 (paper §6, stage 7).
GOVERNED_GLOBS: tuple[str, ...] = (
    "src/fssaira/**/*.py",
    "tests/**/*.py",
    "scripts/*.py",
    "contract/**/*.yaml",
    "packs/*.yaml",
    "profiles/*.yaml",
    "conference/education/*.yaml",
    "conference/attacks/*.yaml",
    "deploy/**/*.yaml",
    "threats/**/*.yaml",
    "docs/SPECIFICATION.md",
    "pyproject.toml",
)


def _pack_source_files(root: Path) -> set[Path]:
    """Sources referenced by pack manifests, which may live outside the globs."""
    files: set[Path] = set()
    for manifest in (root / "packs").glob("*.pack.yaml"):
        try:
            doc = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            continue
        sources = doc.get("sources") if isinstance(doc, dict) else None
        if not isinstance(sources, dict):
            continue
        references = list(sources.get("profiles") or [])
        if sources.get("governed_learning_pack"):
            references.append(sources["governed_learning_pack"])
        for reference in references:
            if not isinstance(reference, str):
                continue
            path = Path(reference)
            path = path if path.is_absolute() else (manifest.parent / path).resolve()
            if path.is_file():
                files.add(path)
    return files


def governed_digest(root: Path = ROOT) -> dict:
    """Digest the governed configuration: enforcement source, tests, declarations, pack sources.

    Paths are included, so a renamed or deleted file changes the digest as well
    as an edited one. Sources outside the repository are included by absolute path.
    """
    root = Path(root).resolve()
    files = {
        path.resolve() for pattern in GOVERNED_GLOBS for path in root.glob(pattern)
        if path.is_file() and "__pycache__" not in path.parts
    } | _pack_source_files(root)
    digest = hashlib.sha256()
    for path in sorted(files):
        name = path.relative_to(root).as_posix() if path.is_relative_to(root) else path.as_posix()
        digest.update(name.encode("utf-8") + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii") + b"\n")
    return {"sha256": digest.hexdigest(), "files": len(files), "globs": list(GOVERNED_GLOBS)}


# -- 5. falsify ------------------------------------------------------------

def falsify(root: Path = ROOT, *, include_ablation: bool = True,
            conference_only: Iterable[str] | None = None) -> StageResult:
    """Try to refute the thesis; prove the falsifiers are not no-ops; ablate controls."""
    from fssaira import falsification
    from fssaira.thesis import run_thesis

    root = Path(root)
    only = list(conference_only) if conference_only else None
    result = StageResult("falsify")
    scope = {"conference_only": only, "ablation": include_ablation}
    try:
        thesis = run_thesis(root)
        conference = falsification.run_falsifiers(only)
    except Exception as exc:  # a crash is a failed gate, never a pass or a traceback
        result.gates.append(GateOutcome("falsifiers_zero_counterexamples", False,
                                        f"falsifiers could not run: {type(exc).__name__}: {exc}"))
        result.artifact = {"scope": scope, "governed_digest": governed_digest(root)}
        return result
    conference_attempts = sum(len(r.attempts) for r in conference)
    conference_violations = sum(r.violations for r in conference)

    # Positive control: remove the controls a falsifier names; it must find harm.
    probe = conference[0] if conference else None
    control_violations = 0
    if probe is not None:
        item = falsification.falsifier(probe.id)
        weakened = [c for c in falsification.ALL_CONTROLS if c not in item.controls]
        control_violations = falsification.run_one(item, weakened).violations

    attempted = thesis.attempts > 0 and conference_attempts > 0
    zero = thesis.counterexamples == 0 and conference_violations == 0
    live = control_violations > 0
    result.gates.append(GateOutcome(
        "falsifiers_zero_counterexamples", attempted and zero and live,
        (f"thesis: {thesis.counterexamples} counterexamples in {thesis.attempts} attempts; "
         f"conference: {conference_violations} violations in {conference_attempts} attempts "
         f"across {len(conference)} falsifiers; positive control "
         f"({probe.id if probe else 'none'} with its controls removed): {control_violations} violations"
         + ("" if attempted else "; no attempts were made")),
        {"thesis_attempts": thesis.attempts, "thesis_counterexamples": thesis.counterexamples,
         "conference_falsifiers": len(conference), "conference_attempts": conference_attempts,
         "conference_violations": conference_violations,
         "positive_control_violations": control_violations}))

    if include_ablation:
        rows = falsification.run_ablation(only)
        dirty = [r for r in rows if r.enabled or r.restored]
        by_falsifier: dict[str, bool] = {}
        for row in rows:
            by_falsifier[row.falsifier] = by_falsifier.get(row.falsifier, False) or row.load_bearing
        unbacked = sorted(f for f, bearing in by_falsifier.items() if not bearing)
        redundant = [f"{r.falsifier}:{r.control}" for r in rows if not r.load_bearing and not r.enabled
                     and not r.restored]
        ok = bool(rows) and not dirty and not unbacked
        result.gates.append(GateOutcome(
            "ablations_restore_harm", ok,
            (f"{sum(r.load_bearing for r in rows)} of {len(rows)} ablations restored harm; "
             f"every falsifier has a load-bearing control or declared pair" if ok else
             "no ablation rows were produced" if not rows else
             f"harm with controls on or after restore: {[r.falsifier for r in dirty]}; "
             f"falsifiers with no load-bearing group: {unbacked}"),
            {"rows": len(rows), "load_bearing": sum(r.load_bearing for r in rows),
             "defence_in_depth_rows": redundant}))
    result.artifact = {"thesis": thesis.to_dict()["summary"], "scope": scope,
                       "governed_digest": governed_digest(root)}
    return result


def _scope_complete(scope: object) -> bool:
    return isinstance(scope, dict) and scope.get("conference_only") is None and scope.get("ablation") is True


def _from_falsify_result(recorded: dict, root: Path, gate_id: str, *, source: str) -> GateOutcome:
    """Read one falsify gate from a falsify result dict, refusing stale or partial runs."""
    artifact = recorded.get("artifact") or {}
    if (artifact.get("governed_digest") or {}).get("sha256") != governed_digest(root)["sha256"]:
        return GateOutcome(gate_id, False, "governed configuration changed since falsification; re-run stage 5")
    scope = artifact.get("scope")
    if not _scope_complete(scope):
        return GateOutcome(gate_id, False,
                           f"partial falsification scope {scope!r} cannot authorize: every falsifier with "
                           "ablation is required")
    gate = next((g for g in recorded.get("gates", []) if g.get("gate") == gate_id), None)
    if gate is None:
        return GateOutcome(gate_id, False, f"the falsification run did not run {gate_id}")
    return GateOutcome(gate_id, bool(gate.get("passed")), f"{source}: {gate.get('detail', '')}",
                       dict(gate.get("observed") or {}))


def _read_artifact(path: Path | None) -> dict | None:
    if path is None or not Path(path).is_file():
        return None
    try:
        body = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return body if isinstance(body, dict) else None


# -- 6. promote ------------------------------------------------------------

#: The fresh runs whose output must match committed evidence (paper §6, stage 6).
DEFAULT_EVIDENCE_COMMANDS: tuple[tuple[str, ...], ...] = (
    ("scripts/generate_results.py", "--check"),
    ("scripts/conference_evidence.py", "--check"),
    ("scripts/collect_results.py", "--check"),
)
#: Backends cheap enough to re-run the conformance suite against during promotion.
_RERUNNABLE = ("memory", "sqlite")


def check_backend_conformance(backends: Iterable[str], records_path: Path | Iterable[Path] | None, *,
                              allowed: Iterable[str] = (), rerun: bool = True) -> GateOutcome:
    """Every configured backend has a current passing record; cheap ones are re-run fresh.

    ``records_path`` is one file, or one per backend (a deployment using several
    backends need not merge them into a single JSON list by hand). Each file
    holds one record or a list; when a backend appears in more than one file,
    the last file wins, and that ambiguity is itself reported as a problem.
    """
    from fssaira.conformance import memory_bundle, sql_bundle
    from fssaira.kernel.assurance import (
        AssuranceRefused,
        load_records,
        require_assurance,
        run_and_record,
    )

    chosen = list(backends)
    allowed_set = set(allowed)
    problems: list[str] = []
    observed: dict[str, dict] = {}
    if not chosen:
        return GateOutcome("backend_conformance_current", False,
                           "no backend declared; name every backend the deployment uses")
    paths = ([records_path] if isinstance(records_path, (str, Path))
             else list(records_path) if records_path is not None else [])
    records: dict[str, ConformanceRecord] = {}
    for path in paths:
        if not Path(path).is_file():
            continue
        try:
            loaded = load_records(path)
        except (OSError, ValueError, KeyError, TypeError, AssuranceRefused) as exc:
            problems.append(f"{path}: conformance records unreadable ({type(exc).__name__})")
            continue
        collisions = sorted(set(loaded) & set(records))
        if collisions:
            problems.append(f"{path}: duplicate record(s) for {collisions}; each backend "
                            "needs exactly one current record")
        records.update(loaded)
    for backend in chosen:
        if allowed_set and backend not in allowed_set:
            problems.append(f"{backend}: not allowed by the deployment profile")
            continue
        try:
            status = require_assurance(backend, records.get(backend))
        except AssuranceRefused as refused:
            problems.append(f"{backend}: {refused.code}")
            continue
        observed[backend] = status.to_dict()
        record = records[backend]
        if not record.executed:
            problems.append(f"{backend}: the record executed no checks")
            continue
        if rerun and backend in _RERUNNABLE:
            fresh = run_and_record(backend, memory_bundle() if backend == "memory" else sql_bundle())
            if fresh.failures:
                problems.append(f"{backend}: fresh conformance run has {len(fresh.failures)} failing check(s)")
            elif len(fresh.executed) != len(record.executed):
                problems.append(f"{backend}: fresh run executed {len(fresh.executed)} checks, "
                                f"the record {len(record.executed)}")
            observed[backend]["fresh_run_executed"] = len(fresh.executed)
    return GateOutcome(
        "backend_conformance_current", not problems,
        (f"{len(chosen)} backend(s) hold a current passing conformance record for their exact code"
         if not problems else "; ".join(problems)),
        {"backends": observed, "problems": problems})


def check_evidence_matches_fresh_run(root: Path, commands: Iterable[Iterable[str]] | None = None) -> GateOutcome:
    """Run each regenerator in ``--check`` mode; any mismatch or missing script fails."""
    import subprocess
    import sys

    root = Path(root)
    chosen = [tuple(c) for c in (commands if commands is not None else DEFAULT_EVIDENCE_COMMANDS)]
    failures: list[str] = []
    for command in chosen:
        argv = list(command)
        if argv and argv[0].endswith(".py"):
            script = root / argv[0]
            if not script.is_file():
                failures.append(f"{argv[0]}: missing")
                continue
            argv = [sys.executable, str(script), *argv[1:]]
        try:
            completed = subprocess.run(argv, cwd=root, capture_output=True, text=True, timeout=3600)
        except (OSError, subprocess.TimeoutExpired) as exc:
            failures.append(f"{' '.join(command)}: {type(exc).__name__}")
            continue
        if completed.returncode != 0:
            tail = (completed.stdout + completed.stderr).strip().splitlines()[-1:] or [""]
            failures.append(f"{' '.join(command)}: exit {completed.returncode} {tail[0][:200]}")
    return GateOutcome(
        "evidence_matches_fresh_run", bool(chosen) and not failures,
        (f"{len(chosen)} regenerator(s) match committed evidence" if chosen and not failures
         else "; ".join(failures) or "no evidence command configured"),
        {"commands": [" ".join(c) for c in chosen], "failures": failures})


def check_interface_inventory(path: Path | None) -> GateOutcome:
    """Every interface a directional claim depends on names a control and an owner."""
    from fssaira.diode_transport import Interface, InterfaceInventory

    if path is None or not Path(path).is_file():
        return GateOutcome("interface_inventory_owned", False,
                           "no interface inventory supplied; a deployment must inventory its own interfaces")
    doc = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    inventory = InterfaceInventory()
    items = doc.get("interfaces") if isinstance(doc, dict) else None
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        inventory.add(Interface(**{key: item[key] if isinstance(item.get(key), str) else ""
                                   for key in ("name", "direction", "control", "owner")},
                                note=item["note"] if isinstance(item.get("note"), str) else ""))
    uncontrolled_items = inventory.uncontrolled
    uncontrolled = [i.name for i in (uncontrolled_items() if callable(uncontrolled_items) else uncontrolled_items)]
    ok = bool(inventory.interfaces) and not uncontrolled
    return GateOutcome(
        "interface_inventory_owned", ok,
        (f"{len(inventory.interfaces)} interfaces, each with a control and an owner" if ok else
         "empty inventory" if not inventory.interfaces else f"no control or owner: {uncontrolled}"),
        {"interfaces": len(inventory.interfaces), "uncontrolled": uncontrolled})


def promote(root: Path = ROOT, *, profile_path: Path, backends: Iterable[str] = (),
            records_path: Path | Iterable[Path] | None = None, obligations_path: Path | None = None,
            interfaces_path: Path | None = None, falsify_artifact: Path | None = None,
            evidence_commands: Iterable[Iterable[str]] | None = None,
            rerun_conformance: bool = True, falsify_only: Iterable[str] | None = None) -> StageResult:
    """Run exactly the gates the deployment profile requires; a failed or missing gate blocks promotion.

    A consequential profile re-runs falsification itself and never trusts an
    artifact. ``falsify_only`` narrows that run, which makes it a partial scope
    that cannot pass. A teaching profile may use a complete, current artifact.
    """
    from fssaira.lifecycle.deploy import DeployProfileError, load_deploy_profile
    from fssaira.lifecycle.obligations import check_obligations

    root = Path(root)
    result = StageResult("promote")
    try:
        profile = load_deploy_profile(profile_path)
    except (DeployProfileError, OSError, yaml.YAMLError) as exc:
        result.gates.append(GateOutcome("deploy_profile_valid", False, str(exc)))
        return result
    result.gates.append(GateOutcome("deploy_profile_valid", True, f"profile {profile.name} ({profile.stage})"))

    contract_result: StageResult | None = None
    falsify_result: dict | None = None
    for gate_id in profile.required_gates:
        if gate_id in ("contract_complete", "failure_tests_exist", "claims_register_no_unverified"):
            contract_result = contract_result or contract(root)
            found = next((g for g in contract_result.gates if g.gate == gate_id), None)
            result.gates.append(found or GateOutcome(gate_id, False, "not reached: an earlier contract gate failed"))
        elif gate_id == "pack_floor_passes":
            result.gates.append(pack(root).gate(gate_id))
        elif gate_id == "no_model_holds_a_key":
            result.gates.append(check_no_model_holds_a_key())
        elif gate_id in FALSIFY_GATES:
            if profile.consequential:
                if falsify_result is None:
                    falsify_result = falsify(root, include_ablation=True, conference_only=falsify_only).to_dict()
                result.gates.append(_from_falsify_result(falsify_result, root, gate_id, source="fresh run"))
            else:
                recorded = _read_artifact(falsify_artifact)
                result.gates.append(
                    GateOutcome(gate_id, False, "no readable falsification artifact; run `fssaira falsify --out <file>`")
                    if recorded is None else _from_falsify_result(recorded, root, gate_id, source="artifact"))
        elif gate_id == "backend_conformance_current":
            result.gates.append(check_backend_conformance(backends, records_path,
                                                          allowed=profile.allowed_backends,
                                                          rerun=rerun_conformance))
        elif gate_id == "evidence_matches_fresh_run":
            result.gates.append(check_evidence_matches_fresh_run(root, evidence_commands))
        elif gate_id == "table4_obligations_signed":
            report = check_obligations(obligations_path)
            result.gates.append(GateOutcome(gate_id, report.complete, report.detail,
                                            {"present": report.present, "denominator": report.denominator}))
        elif gate_id == "interface_inventory_owned":
            result.gates.append(check_interface_inventory(interfaces_path))
        else:  # a gate id the loader accepted but this stage cannot run is a failure, never a pass
            result.gates.append(GateOutcome(gate_id, False, "no implementation for this gate"))
    result.artifact = {"profile": profile.name, "consequential": profile.consequential,
                       "required_gates": list(profile.required_gates),
                       "governed_digest": governed_digest(root)}
    return result


# -- 7. operate ------------------------------------------------------------

def operate(root: Path = ROOT, *, falsify_artifact: Path | None = None,
            executor: object | None = None, monitor: object | None = None,
            allow_not_run: bool = False) -> StageResult:
    """Keep what was falsified the thing that runs; reconcile; stay inside review capacity.

    ``executor`` and ``monitor`` are live objects in a running deployment. A gate
    whose object is absent is listed under ``not_run``. The stage then fails
    unless ``allow_not_run`` is set, and even then those gates are reported, never
    passed.
    """
    root = Path(root)
    result = StageResult("operate")
    current = governed_digest(root)
    not_run: list[dict] = []

    recorded = _read_artifact(falsify_artifact)
    if recorded is None:
        result.gates.append(GateOutcome(
            "change_returns_to_falsify", False,
            "no readable falsification artifact; run `fssaira falsify --out <file>` and pass it here",
            {"current_digest": current["sha256"]}))
    else:
        outcomes = [_from_falsify_result(recorded, root, gate_id, source="artifact") for gate_id in FALSIFY_GATES]
        failed = [o for o in outcomes if not o.passed]
        result.gates.append(GateOutcome(
            "change_returns_to_falsify", not failed,
            ("governed configuration unchanged since a complete, passing falsification run "
             "(artifact is trusted-host evidence)" if not failed
             else "; ".join(f"{o.gate}: {o.detail}" for o in failed) + "; return to stage 5"),
            {"current_digest": current["sha256"]}))

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

    if not_run and not allow_not_run:
        result.gates.append(GateOutcome(
            "live_gates_run", False,
            f"{len(not_run)} live gate(s) did not run: {', '.join(i['gate'] for i in not_run)}; "
            "supply the live objects or pass allow_not_run for an offline check",
            {"not_run": [i["gate"] for i in not_run]}))
    result.artifact = {"governed_digest": current, "not_run": not_run}
    return result
