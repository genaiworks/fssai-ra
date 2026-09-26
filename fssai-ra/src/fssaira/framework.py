"""The Trust by Construction framework as something an organisation can run.

Everything here is driven by one file, ``framework_catalogue.yaml``: the
controls, their maturity levels, dependencies, implementations, verifications,
refusal codes, owners and standards mappings. From it this module provides the
three things an organisation moving to agent swarms needs on day one:

* :func:`assess` -- a self-assessment. Answer each control's plain-language
  question; get the maturity level you can *evidence*, the level you merely
  *claim*, per-domain levels, and warnings where an answer is not allowed.
* :func:`roadmap` -- the unmet controls in the order they can be built: waves
  by maturity level, dependencies first, each with owner, what to build and how
  to prove it.
* :func:`init_workspace` -- a starter kit: assessment template, sector pack,
  contract examples, hardened agent-cell manifests, witness and time-server
  registries, a CI workflow that runs the assurance report, runbooks and the
  evidence-bundle checklist.

:func:`validate` is what keeps the framework honest: it fails if any control
cites a module, test or refusal code that does not exist, depends on a control
at a higher level, or forms a dependency cycle.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

CATALOGUE = Path(__file__).with_name("framework_catalogue.yaml")
REPO = Path(__file__).resolve().parents[2]
STATUSES = ("evidenced", "implemented", "partial", "planned", "no", "n/a")
SECTORS = {"education": "education", "healthcare": "healthcare", "finance": "finance",
           "corporate": "corporate", "government": "benefits", "benefits": "benefits"}


@dataclass(frozen=True)
class Control:
    id: str
    domain: str
    level: int
    name: str
    objective: str
    prevents: str
    question: str
    owner: str
    requires: tuple[str, ...]
    implementation: tuple[str, ...]
    verify: tuple[str, ...]
    codes: tuple[str, ...]
    standards: tuple[str, ...]
    applies_when: str | None = None


@dataclass(frozen=True)
class Pattern:
    """Stable manuscript identity tied to operational controls and bounded evidence."""

    id: str
    name: str
    family: str
    rule: str
    controls: tuple[str, ...]
    verify: tuple[str, ...]
    codes: tuple[str, ...]
    scope: str
    limits: str
    observation: str


@dataclass(frozen=True)
class Catalogue:
    version: str
    levels: dict[int, str]
    domains: dict[str, str]
    controls: tuple[Control, ...]
    patterns: tuple[Pattern, ...] = ()

    def by_id(self) -> dict[str, Control]:
        return {c.id: c for c in self.controls}


def load(path: Path = CATALOGUE) -> Catalogue:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    controls = tuple(Control(**{**c, **{k: tuple(c.get(k) or ()) for k in (
        "requires", "implementation", "verify", "codes", "standards")}})
        for c in raw["controls"])
    patterns = tuple(Pattern(**{**p, **{k: tuple(p.get(k) or ()) for k in (
        "controls", "verify", "codes")}}) for p in raw["patterns"])
    return Catalogue(str(raw["version"]), {int(k): v for k, v in raw["levels"].items()},
                     dict(raw["domains"]), controls, patterns)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate(catalogue: Catalogue | None = None, root: Path = REPO) -> list[str]:
    """Every reason the catalogue is not trustworthy; empty when it is."""
    from .refusal_registry import scan
    from .threats import locator_exists

    catalogue = catalogue or load()
    problems: list[str] = []
    ids = [c.id for c in catalogue.controls]
    if len(ids) != len(set(ids)):
        problems.append("duplicate control ids")
    index = catalogue.by_id()
    codes = set(scan())
    for c in catalogue.controls:
        where = f"{c.id}:"
        if c.domain not in catalogue.domains or not c.id.startswith(c.domain + "-"):
            problems.append(f"{where} domain {c.domain} does not match id")
        if c.level not in catalogue.levels:
            problems.append(f"{where} unknown level {c.level}")
        for dep in c.requires:
            if dep not in index:
                problems.append(f"{where} requires unknown {dep}")
            elif index[dep].level > c.level:
                problems.append(f"{where} level {c.level} requires {dep} at level {index[dep].level}")
        for path in c.implementation:
            if not (root / path).exists():
                problems.append(f"{where} implementation missing: {path}")
        if not c.verify:
            problems.append(f"{where} has no verification")
        for check in c.verify:
            if check.startswith("tests/") and not locator_exists(root, check):
                problems.append(f"{where} test missing: {check}")
            elif not check.startswith(("tests/", "command: ", "attestation: ")):
                problems.append(f"{where} verification kind unknown: {check}")
        for code in c.codes:
            if code not in codes:
                problems.append(f"{where} refusal code not registered: {code}")
        for field in ("objective", "prevents", "question", "owner"):
            if not str(getattr(c, field)).strip():
                problems.append(f"{where} {field} is empty")
    try:
        _topological(catalogue.controls)
    except ValueError as cycle:
        problems.append(str(cycle))
    if catalogue.patterns:
        pattern_ids = [p.id for p in catalogue.patterns]
        if len(pattern_ids) != len(set(pattern_ids)):
            problems.append("duplicate pattern ids")
        if set(pattern_ids) != {f"P{n}" for n in range(1, 35)}:
            problems.append("canonical patterns must cover P1-P34 exactly")
        for p in catalogue.patterns:
            if not p.controls:
                problems.append(f"{p.id}: no operational controls")
            for cid in p.controls:
                if cid not in index:
                    problems.append(f"{p.id}: unknown operational control {cid}")
            if p.scope not in {"local-reference", "deployment-dependent", "bounded-mitigation"}:
                problems.append(f"{p.id}: unknown evidence scope {p.scope}")
            for field in ("name", "family", "rule", "limits", "observation"):
                if not str(getattr(p, field)).strip():
                    problems.append(f"{p.id}: {field} is empty")
            if not p.verify:
                problems.append(f"{p.id}: no verification")
            for check in p.verify:
                if not check.startswith("tests/") or not locator_exists(root, check):
                    problems.append(f"{p.id}: test missing: {check}")
            for code in p.codes:
                if code not in codes:
                    problems.append(f"{p.id}: refusal code not registered: {code}")
    return problems


def _topological(controls) -> list:
    index = {c.id: c for c in controls}
    order, state = [], {}

    def visit(cid: str, trail: tuple[str, ...]) -> None:
        if state.get(cid) == "done":
            return
        if state.get(cid) == "active":
            raise ValueError("dependency cycle: " + " -> ".join((*trail, cid)))
        state[cid] = "active"
        for dep in sorted(index[cid].requires, key=lambda d: (index[d].level, d)):
            if dep in index:
                visit(dep, (*trail, cid))
        state[cid] = "done"
        order.append(index[cid])

    for c in sorted(controls, key=lambda c: (c.level, c.id)):
        visit(c.id, ())
    return order


# ---------------------------------------------------------------------------
# Assessment and roadmap
# ---------------------------------------------------------------------------

def _level(controls, met) -> int:
    level = 0
    for candidate in sorted({c.level for c in controls}):
        if all(met(c) for c in controls if c.level <= candidate):
            level = candidate
        else:
            break
    return level


def assess(answers: dict[str, str], catalogue: Catalogue | None = None) -> dict:
    """Score answers of the form ``{control_id: status}`` against the catalogue."""
    catalogue = catalogue or load()
    warnings, status = [], {}
    for c in catalogue.controls:
        value = str(answers.get(c.id, "no")).strip().lower()
        if value not in STATUSES:
            warnings.append(f"{c.id}: unknown status {value!r}, counted as 'no'")
            value = "no"
        if value == "n/a" and not c.applies_when:
            warnings.append(f"{c.id}: cannot be n/a (it always applies), counted as 'no'")
            value = "no"
        status[c.id] = value
    for extra in sorted(set(answers) - set(status)):
        warnings.append(f"{extra}: not a control in catalogue {catalogue.version}")
    applicable = [c for c in catalogue.controls if status[c.id] != "n/a"]

    def evidenced(c):
        return status[c.id] == "evidenced"

    def claimed(c):
        return status[c.id] in ("evidenced", "implemented")

    domains = {}
    for code, name in catalogue.domains.items():
        in_domain = [c for c in applicable if c.domain == code]
        domains[code] = {"name": name, "evidenced_level": _level(in_domain, evidenced),
                         "claimed_level": _level(in_domain, claimed),
                         "evidenced": sum(evidenced(c) for c in in_domain),
                         "applicable": len(in_domain)}
    counts = {s: sum(1 for v in status.values() if v == s) for s in STATUSES}
    evidenced_level = _level(applicable, evidenced)
    claimed_level = _level(applicable, claimed)
    return {"catalogue": catalogue.version, "assessment_basis": "self-reported control status",
            "evidenced_level": evidenced_level,
            "evidenced_level_name": catalogue.levels.get(evidenced_level, "Model-centred"),
            "claimed_level": claimed_level,
            "claim_gap": claimed_level - evidenced_level,
            "counts": counts, "domains": domains, "status": status, "warnings": warnings}


def roadmap(answers: dict[str, str], catalogue: Catalogue | None = None) -> dict:
    """Unmet applicable controls in build order: waves by level, dependencies first."""
    catalogue = catalogue or load()
    result = assess(answers, catalogue)
    status = result["status"]
    unmet = [c for c in _topological(catalogue.controls)
             if status[c.id] not in ("evidenced", "n/a")]
    waves: dict[int, list[dict]] = {}
    for c in unmet:
        waves.setdefault(c.level, []).append({
            "id": c.id, "name": c.name, "status": status[c.id], "owner": c.owner,
            "blocked_by": [d for d in c.requires if status.get(d) not in ("evidenced", "n/a")],
            "why": c.prevents, "build": list(c.implementation), "prove": list(c.verify),
            "evidence_only": status[c.id] == "implemented"})
    return {"from_level": result["evidenced_level"],
            "waves": [{"to_level": level, "name": catalogue.levels[level], "controls": items}
                      for level, items in sorted(waves.items())]}


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_markdown(catalogue: Catalogue | None = None) -> str:
    catalogue = catalogue or load()
    out = [
        "# Framework control catalogue",
        "",
        "> **Documentation navigation:** [Documentation map](../README.md) · "
        "[Framework](../FRAMEWORK.md) · [Master guide](../MASTER_GUIDE.md)",
        ">",
        "> **Recommended next:** Answer the questions below in the assessment template "
        "(`fssaira framework init`), then run `fssaira framework assess`.",
        "",
        f"Generated from `src/fssaira/framework_catalogue.yaml` (catalogue {catalogue.version}) "
        "by `fssaira framework render`. Do not edit by hand: a test fails if this file and "
        "the catalogue differ.",
        "",
        f"**{len(catalogue.controls)} controls** in {len(catalogue.domains)} domains. "
        "Maturity levels: " + " · ".join(f"{k} {v}" for k, v in sorted(catalogue.levels.items()))
        + ".",
        "",
        "| Domain | Controls | By level |",
        "|---|---|---|",
    ]
    for code, name in catalogue.domains.items():
        in_domain = [c for c in catalogue.controls if c.domain == code]
        by_level = ", ".join(f"L{lvl}: {sum(c.level == lvl for c in in_domain)}"
                             for lvl in sorted({c.level for c in in_domain}))
        out.append(f"| **{code}** {name} | {len(in_domain)} | {by_level} |")
    for code, name in catalogue.domains.items():
        out += ["", f"## {code} — {name}", ""]
        for c in (c for c in catalogue.controls if c.domain == code):
            out += [
                f"### {c.id} · {c.name} (level {c.level})",
                "",
                f"- **Objective:** {c.objective}",
                f"- **Prevents:** {c.prevents}",
                f"- **Ask yourself:** {c.question}",
                f"- **Owner:** {c.owner}"
                + (f" · **Applies when:** {c.applies_when}" if c.applies_when else ""),
                "- **Requires:** " + (", ".join(c.requires) if c.requires else "nothing"),
                "- **Implemented in:** " + ", ".join(f"`{p}`" for p in c.implementation),
                "- **Prove it:** " + "; ".join(f"`{v}`" for v in c.verify),
            ]
            if c.codes:
                out.append("- **Refusal codes:** " + ", ".join(f"`{x}`" for x in c.codes))
            out += ["- **Standards:** " + ", ".join(c.standards), ""]
    return "\n".join(out).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Starter kit
# ---------------------------------------------------------------------------


def pattern_manifest(catalogue: Catalogue | None = None) -> dict:
    """The paper, CLI and guides consume the same pattern identities and scale."""
    catalogue = catalogue or load()
    return {
        "framework": "Trust by Construction",
        "catalogue_version": catalogue.version,
        "basis": "Catalogue bindings; test execution and deployment evidence are separate",
        "levels": {0: "Model-centred", **catalogue.levels},
        "pattern_count": len(catalogue.patterns),
        "control_count": len(catalogue.controls),
        "patterns": [asdict(p) for p in catalogue.patterns],
    }


def render_patterns(catalogue: Catalogue | None = None) -> str:
    catalogue = catalogue or load()
    index = catalogue.by_id()
    lines = [
        "# Trust by Construction canonical patterns", "",
        "> **Documentation navigation:** [Documentation map](../README.md) · "
        "[Framework](../FRAMEWORK.md) · [Operational controls](CONTROLS.md)",
        ">",
        "> **Recommended next:** Map each pattern to its operational controls in "
        "[CONTROLS.md](CONTROLS.md), then assess your deployment with `fssaira framework assess`.", "",
        f"Generated from `src/fssaira/framework_catalogue.yaml` (catalogue {catalogue.version}) "
        "by `fssaira framework render`. Edit the catalogue, not this document.", "",
        f"**{len(catalogue.patterns)} patterns, {len(catalogue.controls)} operational controls, "
        "one framework.** P1–P10 retain the reviewed V27 decision and composition core. "
        "P11–P34 retain V28's evidence, containment, visibility and consequence extensions. "
        "Controls add owners, dependencies and assessment obligations; they are not a second pattern list.", "",
        "The evidence scopes below describe reference mechanisms and their limits. "
        "A named test is an executable evidence locator, not a claim that it passed on your host. "
        "Observations may be refusals, configuration findings or properties; only the separately "
        "listed registered codes belong to the refusal-code registry.", "",
        "## One assessment scale", "",
        "| Level | Name |", "|---|---|", "| 0 | Model-centred (no evidenced level) |",
        *[f"| {level} | {name} |" for level, name in sorted(catalogue.levels.items())], "",
        "V28's alternative labels for levels 3–5 are superseded. Level 0 is a baseline, "
        "not an additional certified tier. Assessment answers are self-reported; an evidence "
        "bundle and reviewer must substantiate them. No level grants blanket production approval.", "",
        "## Pattern index", "",
        "| Pattern | Family | Operational controls | Evidence scope |",
        "|---|---|---|---|",
    ]
    for p in catalogue.patterns:
        lines.append(f"| {p.id} {p.name} | {p.family} | {', '.join(p.controls)} | {p.scope} |")
    for p in catalogue.patterns:
        lines += ["", f"## {p.id} {p.name}", "", p.rule, "",
                  "- **Operational controls:** " + ", ".join(p.controls),
                  "- **Implementation:** " + ", ".join(f"`{path}`" for path in sorted({
                      path for cid in p.controls for path in index[cid].implementation})),
                  "- **Test:** " + "; ".join(f"`{check}`" for check in p.verify),
                  f"- **Test observation:** {p.observation}",
                  "- **Registered refusal codes:** " + (", ".join(f"`{c}`" for c in p.codes)
                                                        or "none specified for this binding"),
                  f"- **Evidence scope:** {p.scope}", f"- **Limits:** {p.limits}"]
    return "\n".join(lines).rstrip() + "\n"

_K8S = """\
# Hardened agent cell. Verify it from inside with fssaira.agent_cell.probe_cell.
apiVersion: v1
kind: Pod
metadata:
  name: agent-cell
  namespace: agents
  labels: {role: agent-cell}
spec:
  automountServiceAccountToken: false   # no ambient cluster credential
  containers:
    - name: agent
      image: registry.example/agent@sha256:REPLACE_WITH_PINNED_DIGEST
      securityContext:
        readOnlyRootFilesystem: true
        allowPrivilegeEscalation: false
        runAsNonRoot: true
        capabilities: {drop: ["ALL"]}
      env:
        - name: GATEWAY_ADDRESS          # reached by address: no DNS egress needed
          value: "REPLACE_WITH_GATEWAY_IP:8443"
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: agent-cell-isolation
  namespace: agents
spec:
  podSelector:
    matchLabels: {role: agent-cell}
  policyTypes: ["Ingress", "Egress"]
  ingress: []
  egress:
    - to:
        - namespaceSelector:
            matchLabels: {kubernetes.io/metadata.name: enforcement}
          podSelector:
            matchLabels: {role: enforcement-gateway}
      ports: [{protocol: TCP, port: 8443}]
# Also block the cloud metadata endpoint at the node (IMDSv2 hop limit 1, or
# workload identity disabled for this namespace).
"""

_WITNESSES = """\
# Witness registry: the VERIFIER decides which organisation runs each key.
# The quorum counts distinct domains, so two keys at one organisation count once.
threshold: 2
witnesses:
  - key_id: witness-regulator
    domain: REPLACE-regulator-or-supervisory-body
    public_key_hex: REPLACE
  - key_id: witness-internal-audit
    domain: {org}-internal-audit        # separate administrators from operations
    public_key_hex: REPLACE
  - key_id: witness-external
    domain: REPLACE-university-auditor-or-civil-society
    public_key_hex: REPLACE
"""

_TIME = """\
# Independent time servers for anchoring checkpoints (Roughtime-style).
min_servers: 2
tolerance_seconds: 1.0
servers:
  - name: REPLACE-time-source-1
    public_key_hex: REPLACE
  - name: REPLACE-time-source-2
    public_key_hex: REPLACE
  - name: REPLACE-time-source-3
    public_key_hex: REPLACE
"""

_CI = """\
# Runs on every change to the enforcer, a model, a vendor or a policy.
name: agentic-assurance
on: [push, pull_request]
jobs:
  assurance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.12"}
      - run: pip install "fssaira[privacy]"
      - name: Assurance report (fails on any failing section)
        run: fssaira assure report --output evidence/assurance-report.json
      - name: Maturity must not regress
        run: fssaira framework assess assessment.yaml --min-level {target} --output evidence/assessment.json
      - uses: actions/upload-artifact@v4
        with: {name: assurance-evidence, path: evidence/}
"""

_RUNBOOKS = {
    "policy-change.md": """\
# Runbook: changing agent policy

1. Legal / DPO approves the new policy text and the new `policy_version`.
2. Operator runs `migrate_policy(token, new_passport, reason=...)`.
   Refusals: `POLICY_VERSION_NOT_INCREASING`, `POLICY_WORKLOAD_MISMATCH`.
3. Review the result: tasks contracted to quarantine; held effects rerouted to
   the manual queue as `policy_changed_rereview`.
4. Old approvals now refuse with `POLICY_VERSION_CHANGED`; work is re-proposed.
5. File the `tbc_policy_migrated` evidence event with the change record.
""",
    "revocation.md": """\
# Runbook: consent withdrawn or authority revoked

1. Operator runs `revoke_task(token, task_id, reason=...)` (the epoch rises).
2. Confirm queued effects cancel (`STALE_PROPOSAL`) and adapters refuse stale
   proofs (`FRESHNESS_UNPROVEN`).
3. For irreversible effects inside their objection window, confirm cancellation
   with `scheduled_effects`.
4. Record the worst delivery lag of effects committed before the revocation.
""",
    "incident.md": """\
# Runbook: suspected agent compromise or misbehaviour

1. `emergency_stop(token, reason=...)` halts the workload; nothing restores
   authority except a named operator.
2. Pull the agent dossier and decision receipts: who, may, did, stopped, could leak.
   No protected content is needed.
3. Verify evidence integrity: `fssaira small verify --mode full` and the witness quorum.
4. Resume only after the cause is fixed and `fssaira assure report` passes.
""",
    "appeal.md": """\
# Runbook: a person contests an agent-assisted decision

1. Locate the decision receipt (policy version, epoch, lineage, digest, outcome).
2. Prove the receipt is in a published checkpoint with `prove_record` / `verify_record`.
3. A named human owner decides; the agent is not consulted about its own decision.
4. Answer within the sector deadline (e.g. FERPA access: 45 days).
""",
}

_BUNDLE = """\
# Evidence bundle before go-live

- [ ] Commit, dependency lock, SBOM and build measurement (`fssaira assure trusted-base`)
- [ ] `fssaira assure report` output and digest, reproduced by the buyer or auditor
- [ ] `fssaira framework assess` at or above the target level, with no warnings
- [ ] Adapter qualification of *your* store and connectors (`adapter_qualification.qualify`)
- [ ] Agent cells measured from inside (`agent_cell.probe_cell`)
- [ ] Witness quorum configured with at least two outside domains
- [ ] Declared review capacity, floor, and staffing (`fssaira assure staffing`)
- [ ] Sector release table validated by legal / the registrar / the DPO
- [ ] Independent security review and pilot exit report (see docs/PILOT_PROTOCOL.md)
"""


def assessment_template(catalogue: Catalogue | None = None) -> str:
    catalogue = catalogue or load()
    lines = [
        f"# Self-assessment against the framework catalogue {catalogue.version}.",
        "# Answer each control with one of:",
        "#   evidenced    -- in place AND the named proof has been run in this deployment",
        "#   implemented  -- in place, proof not yet run here (counts toward the claimed level only)",
        "#   partial | planned | no",
        "#   n/a          -- only where the control says 'applies when' and that is not true",
        "# Then run: fssaira framework assess assessment.yaml",
        "",
    ]
    for code, name in catalogue.domains.items():
        lines.append(f"# --- {code}: {name} ---")
        for c in (c for c in catalogue.controls if c.domain == code):
            lines.append(f"# L{c.level} {c.name}. {c.question}")
            if c.applies_when:
                lines.append(f"#    (may be n/a unless: {c.applies_when})")
            lines.append(f'{c.id}: "no"')
        lines.append("")
    return "\n".join(lines)


def init_workspace(directory: Path, *, org: str, sector: str, target_level: int = 4,
                   catalogue: Catalogue | None = None) -> list[Path]:
    """Write a starter kit; refuses to overwrite an existing workspace."""
    catalogue = catalogue or load()
    if sector not in SECTORS:
        raise ValueError(f"sector must be one of {sorted(SECTORS)}")
    if target_level not in catalogue.levels:
        raise ValueError("target level must be 1-5")
    directory = Path(directory)
    if directory.exists() and any(directory.iterdir()):
        raise FileExistsError(f"{directory} is not empty")
    written: list[Path] = []

    def write(rel: str, text: str) -> None:
        path = directory / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        written.append(path)

    pack = REPO / "packs" / f"{SECTORS[sector]}.pack.yaml"
    write("README.md", _readme(org, sector, target_level, catalogue))
    write("assessment.yaml", assessment_template(catalogue))
    if pack.exists():
        (directory / "policy").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(pack, directory / "policy" / pack.name)
        written.append(directory / "policy" / pack.name)
    for name in ("education-passport.json", "education-task.json"):
        source = REPO / "profiles" / "tbc" / name
        if source.exists():
            target = directory / "policy" / name.replace("education-", "example-")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            written.append(target)
    write("deploy/k8s/agent-cell.yaml", _K8S)
    write("deploy/witnesses.yaml", _WITNESSES.replace("{org}", _slug(org)))
    write("deploy/time-servers.yaml", _TIME)
    write(".github/workflows/agentic-assurance.yml", _CI.replace("{target}", str(target_level)))
    for name, text in _RUNBOOKS.items():
        write(f"runbooks/{name}", text)
    write("evidence/BUNDLE.md", _BUNDLE)
    return written


def _slug(text: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in text.lower()).strip("-") or "org"


def _readme(org: str, sector: str, target: int, catalogue: Catalogue) -> str:
    level_name = catalogue.levels[target]
    first = [c for c in _topological(catalogue.controls) if c.level == 1]
    return f"""# {org}: agentic-swarm programme workspace

Sector: **{sector}** · Target maturity: **level {target} ({level_name})** · Framework catalogue {catalogue.version}

This workspace was generated by `fssaira framework init`. It holds your
answers, your configuration and your evidence -- not the framework itself.

## The journey

| Step | Do | Command |
|---|---|---|
| 1. Assess | answer every question in `assessment.yaml` honestly | `fssaira framework assess assessment.yaml` |
| 2. Plan | build the waves in dependency order | `fssaira framework assess assessment.yaml --roadmap` |
| 3. Start | keys out, contracts in: {", ".join(c.id for c in first)} | see `deploy/k8s/agent-cell.yaml` |
| 4. Build | adapt `policy/` (sector pack, passport, task contract) | `fssaira pack-check policy/*.pack.yaml` |
| 5. Qualify | your store and connectors, your cells | `adapter_qualification.qualify`, `agent_cell.probe_cell` |
| 6. Operate | runbooks in `runbooks/`, staffing to the floor | `fssaira assure staffing ...` |
| 7. Prove | CI runs the report on every change | `fssaira assure report` |
| 8. Procure | vendors run the same report; compare digests | see docs/MASTER_GUIDE.md §11 |

## Rules that do not bend

- An answer is `evidenced` only when the named proof has run **in this deployment**.
- `n/a` is allowed only where a control names the condition, and that condition is false.
- Understaffed review is fixed with people, never by lowering the floor.
- Every model, vendor, policy or enforcer change reruns the assurance report.
"""


def load_answers(path: Path) -> dict[str, str]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("assessment must map control ids to statuses")
    def status(value) -> str:
        # YAML 1.1 reads a bare `no` as False; an organisation typing it means "no".
        if value is False:
            return "no"
        if value is True:
            return "yes"          # ambiguous: assess() warns and counts it as "no"
        return "n/a" if value is None else str(value)

    return {str(k): status(v) for k, v in data.items()}


def to_json(value) -> str:
    return json.dumps(value, indent=2, sort_keys=True)


__all__ = ["CATALOGUE", "Catalogue", "Control", "STATUSES", "assess", "assessment_template",
           "init_workspace", "load", "load_answers", "render_markdown", "roadmap", "validate"]
