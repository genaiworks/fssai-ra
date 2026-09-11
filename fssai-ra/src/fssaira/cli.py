"""``fssaira`` -- the command line for running, checking, and extending the platform.

Everything the paper claims can be reproduced from this one binary on a
disconnected laptop::

    fssaira doctor                          what is this deployment, really?
    fssaira verify profiles/x.yaml          bounded model check of the authority space
    fssaira evaluate profiles/x.yaml        adversarial + utility + ablation suite
    fssaira conformance                     do the configured backends still conform?
    fssaira demo                            the five-minute walkthrough
    fssaira init my-domain                  scaffold a new domain from the template

Design rules for this interface: every command prints a human summary and can
emit machine-readable JSON with ``--output``; every command that makes a
judgement exits non-zero when the judgement is negative, so it can be a CI gate;
and no command mutates anything outside the paths it is given.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import __version__

# ---------------------------------------------------------------------------
# Presentation
# ---------------------------------------------------------------------------

_COLOR = sys.stdout.isatty() and not os.getenv("NO_COLOR")


def _c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLOR else text


def bold(text: str) -> str:
    return _c(text, "1")


def green(text: str) -> str:
    return _c(text, "32")


def red(text: str) -> str:
    return _c(text, "31")


def yellow(text: str) -> str:
    return _c(text, "33")


def dim(text: str) -> str:
    return _c(text, "2")


def heading(text: str) -> None:
    print(f"\n{bold(text)}\n{dim('─' * len(text))}")


def verdict(ok: bool, yes: str, no: str) -> str:
    return green(f"✓ {yes}") if ok else red(f"✗ {no}")


def emit(payload: dict, output: Path | None) -> None:
    rendered = json.dumps(payload, indent=2)
    if output is None:
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered + "\n", encoding="utf-8")
    print(f"\nwrote {output}")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_version(args) -> int:
    print(f"fssaira {__version__}")
    if args.verbose:
        print(f"python {sys.version.split()[0]}")
        import platform as _platform

        print(f"platform {_platform.platform()}")
    return 0


def cmd_validate_profile(args) -> int:
    from .profiles import ApplicationProfile

    profile = ApplicationProfile.load(args.profile)
    print(f"valid profile: {profile.profile_id} v{profile.version} "
          f"({len(profile.transitions)} transitions)")
    if args.verbose:
        for rule in profile.transitions:
            marker = red("consequential") if rule.consequential else dim("reversible")
            print(f"  {rule.operation}: {rule.from_status} → {rule.to_status} "
                  f"[{marker}, approver: {rule.approval_role}]")
    return 0


def cmd_validate_contract(args) -> int:
    from .contract import ControlContract

    contract = ControlContract.load(args.contract_directory)
    contract.validate()
    print(f"valid contract: {len(contract)} requirements")
    if args.verbose:
        for requirement in contract:
            print(f"  {requirement.id:<8} {requirement.domain:<24} owner: {requirement.owner}")
    return 0


def cmd_contract_show(args) -> int:
    from .contract import ControlContract

    contract = ControlContract.load(args.contract_directory)
    contract.validate()
    from dataclasses import asdict

    payload = {"requirements": [asdict(item) for item in contract], "count": len(contract)}
    if args.output is None:
        for requirement in contract:
            heading(f"{requirement.id} — {requirement.domain}")
            print(f"  protected asset     {requirement.protected_asset}")
            print(f"  permitted operation {requirement.permitted_operation}")
            print(f"  enforcement point   {requirement.enforcement_point}")
            print(f"  owner               {requirement.owner}")
            print(f"  test                {requirement.test}")
            print(f"  evidence artifact   {requirement.evidence_artifact}")
            print(f"  failure response    {requirement.failure_response}")
    emit(payload, args.output)
    return 0


def cmd_evaluate(args) -> int:
    from .evaluation import EvaluationRunner
    from .profiles import ApplicationProfile

    profile = ApplicationProfile.load(args.profile)
    report = EvaluationRunner(profile).run(
        include_utility=not args.no_utility, include_ablations=not args.no_ablations
    )
    payload = report.to_dict()

    heading(f"Adversarial evaluation — {report.profile_id} v{report.profile_version}")
    for item in report.scenarios:
        mark = green("contained") if item.contained else red("NOT CONTAINED")
        print(f"  [{mark}] {item.scenario}")
        if not item.contained:
            print(f"            expected {item.expected}, observed {item.observed}")
    print(f"\n  containment   {report.passed}/{report.total}"
          f"   unauthorized mutations: {report.unauthorized_mutations}")

    if report.utility:
        heading("Utility — does legitimate work still complete?")
        for item in report.utility:
            mark = green("completed") if item.completed else red("FALSE DENIAL")
            print(f"  [{mark}] {item.task}")
        print(f"\n  benign tasks  {report.benign_completed}/{len(report.utility)}"
              f"   false-denial rate: {report.false_denial_rate}")

    if report.ablations:
        heading("Attribution — is each control load-bearing?")
        for item in report.ablations:
            mark = green("load-bearing") if item.load_bearing else yellow("DECORATIVE")
            print(f"  [{mark}] {item.control:<34} {item.baseline_outcome} → {item.ablated_outcome}")
        print(f"\n  authority coverage  {report.coverage.authority_coverage}")

    print()
    print("  " + verdict(report.all_contained, "all declared scenarios contained",
                         "one or more scenarios not contained"))
    print(dim("  A fixture result in a synthetic environment. Not a security certification."))
    emit(payload, args.output)
    return 0 if report.all_contained and report.false_denial_rate == 0.0 else 1


def cmd_verify(args) -> int:
    from .profiles import ApplicationProfile
    from .verification import verify_profile

    profile = ApplicationProfile.load(args.profile)
    report = verify_profile(profile)
    payload = report.to_dict()

    heading(f"Bounded model check — {report.profile_id} v{report.profile_version}")
    for invariant in report.invariants:
        print(f"  {dim('·')} {invariant}")
    print(f"\n  states explored     {report.states_explored}")
    print(f"  mutations observed  {report.mutations_observed}")
    print(f"  violations          {len(report.violations)}")
    if args.verbose:
        heading("Denial outcomes observed")
        for code, count in report.outcome_histogram.items():
            print(f"  {count:>5}  {code}")
    for violation in report.violations:
        print(red(f"\n  VIOLATION {violation.invariant[:40]}…"))
        print(f"    configuration: {violation.configuration}")
        print(f"    detail:        {violation.detail}")
    print()
    print("  " + verdict(report.holds, "invariants hold within the declared bounds",
                         "invariant violated"))
    print(dim(f"  Bounds: {report.bounds['note']}"))
    emit(payload, args.output)
    return 0 if report.holds else 1


def cmd_conformance(args) -> int:
    from .conformance import memory_bundle, run_conformance, sql_bundle
    from .profiles import ApplicationProfile

    profile = ApplicationProfile.load(args.profile) if args.profile else None
    if args.backend == "sql":
        from .postgres_backend import database_from_env

        database = database_from_env(
            args.database_url or os.getenv("FSSAI_DATABASE_URL") or "sqlite://",
            evidence_token="conformance-evidence-writer",
        )
        bundle = sql_bundle(database, profile)
    else:
        bundle = memory_bundle(profile)

    report = run_conformance(bundle)
    heading(f"Conformance — backends: {', '.join(f'{k}={v}' for k, v in report.backends.items())}")
    print(report.render())
    print(dim("\n  Behavioural conformance for these fixtures. Not an audit or certification."))
    emit(report.to_dict(), args.output)
    return 0 if report.passed else 1


def cmd_race_test(args) -> int:
    """Run a bounded many-caller replay race against the atomic executor."""
    from .profiles import ApplicationProfile
    from .race import run_replay_race

    profile = ApplicationProfile.load(args.profile)
    report = run_replay_race(profile, callers=args.callers)
    heading(f"Concurrent replay race — {report.callers} callers")
    print(f"  executions returned  {report.executions_returned}")
    print(f"  replay responses     {report.replayed}")
    print(f"  mutations            {report.mutations}")
    print(f"  distinct receipts    {report.distinct_receipts}")
    print(f"  evidence records     {report.intent_records} intent, {report.outcome_records} outcome")
    print("\n  " + verdict(report.passed, "one mutation and one complete record",
                              "concurrent replay invariant failed"))
    print(dim(f"  Bounds: {report.bounds}"))
    emit(report.to_dict(), args.output)
    return 0 if report.passed else 1


def cmd_resilience(args) -> int:
    from .profiles import ApplicationProfile
    from .resilience import run_resilience

    report = run_resilience(ApplicationProfile.load(args.profile), callers=args.callers)
    heading("Process isolation and crash recovery")
    for item in (*report.process_races, *report.crash_recovery):
        name = item.get("scenario", item.get("checkpoint"))
        print("  " + verdict(item["passed"], name, name + " failed"))
    for bound in report.bounds:
        print(dim("  " + bound))
    emit(report.to_dict(), args.output)
    return 0 if report.passed else 1


def cmd_doctor(args) -> int:
    from .runtime_factory import configuration_warnings, readiness
    from .security import AuthConfig

    heading("FSSAI-RA configuration report")
    print(f"  version         {__version__}")
    print(f"  profile         {os.getenv('FSSAI_PROFILE', 'profiles/student_support.yaml')}")
    print(f"  database        {os.getenv('FSSAI_DATABASE_URL') or dim('not configured')}")
    print(f"  redis           {os.getenv('FSSAI_REDIS_URL') or dim('not configured')}")
    print(f"  kafka           {os.getenv('FSSAI_KAFKA_BOOTSTRAP') or dim('not configured')}")
    print(f"  model           {os.getenv('FSSAI_MODEL', 'ollama')}")
    print(f"  auth mode       {AuthConfig.from_env().mode}")

    heading("Durability")
    if os.getenv("FSSAI_DATABASE_URL"):
        print(green("  single-transaction: the mutation and its evidence commit together"))
    elif os.getenv("FSSAI_REDIS_URL"):
        print(yellow("  best-effort: durable, but an interrupted outcome needs reconciliation"))
    else:
        print(red("  volatile: state is in memory and is lost on restart"))

    heading("Model backend")
    try:
        from .models import build_model

        backend = build_model()
        status = backend.health() if hasattr(backend, "health") else {"reachable": None}
        reachable = status.get("reachable")
        label = (green("reachable") if reachable else
                 (red("unreachable") if reachable is False else dim("unknown")))
        print(f"  {getattr(backend, 'name', '?')}: {label}")
        for key in ("host", "base_url", "model", "model_installed", "detail", "sovereignty_warning"):
            if status.get(key) not in (None, ""):
                print(f"    {key}: {status[key]}")
    except Exception as exc:
        print(red(f"  could not construct the configured model backend: {exc}"))

    warnings = configuration_warnings()
    heading(f"Findings ({len(warnings)})")
    order = {"blocking": 0, "high": 1, "medium": 2, "info": 3}
    palette = {"blocking": red, "high": red, "medium": yellow, "info": dim}
    for item in sorted(warnings, key=lambda w: order.get(w.severity, 9)):
        print(f"  [{palette[item.severity](item.severity):>8}] {item.code}")
        print(f"             {item.message}")
        if item.remedy:
            print(dim(f"             → {item.remedy}"))

    state = readiness()
    print()
    print("  " + verdict(state["ready_for_pilot"],
                         "no known teaching defaults are active",
                         f"{len(state['blocking'])} blocking finding(s) must be resolved first"))
    print(dim("  " + state["note"]))
    emit({"readiness": state, "findings": [w.to_dict() for w in warnings]}, args.output)
    return 0 if state["ready_for_pilot"] else 1


def cmd_plugins(args) -> int:
    from . import plugins

    heading("Registered backends")
    current_port = None
    for info in plugins.available(args.port):
        if info.port != current_port:
            current_port = info.port
            print(f"\n  {bold(info.port)}")
        print(f"    {info.name:<20} {dim(info.origin)}")
        if info.summary:
            print(dim(f"      {info.summary[:96]}"))
    print(dim("\n  Add your own with an entry point in the fssaira.<port>s group,"))
    print(dim("  or point FSSAI_<PORT> at a 'module:Attribute' path."))
    return 0


def cmd_model_list(args) -> int:
    from .models import DEFAULT_BACKEND, available_models

    heading("Model backends")
    for item in available_models():
        marker = green(" (default)") if item["name"] == DEFAULT_BACKEND else ""
        print(f"  {item['name']:<22}{marker}")
        if item["summary"]:
            print(dim(f"    {item['summary'][:100]}"))
    return 0


def cmd_model_health(args) -> int:
    from .models import build_model

    backend = build_model(args.name)
    status = backend.health() if hasattr(backend, "health") else {"reachable": None}
    print(json.dumps(status, indent=2))
    return 0 if status.get("reachable", True) else 1


def cmd_model_propose(args) -> int:
    from .bounded_intelligence import UntrustedEvidence
    from .models import build_model
    from .models.base import CapabilityCatalogue

    backend = build_model(args.name)
    catalogue = CapabilityCatalogue.default()
    evidence = [UntrustedEvidence("cli", text) for text in (args.evidence or [])]
    calls = backend.propose(args.task, evidence)

    heading(f"Proposals from {getattr(backend, 'name', '?')} — nothing has executed")
    if not calls:
        print(dim("  (no proposals)"))
    for call in calls:
        capability = catalogue.get(call.tool)
        authoritative = capability.action_class.value if capability else "high_impact"
        flag = red(" needs a named human") if authoritative == "high_impact" else ""
        egress = red(" egress") if capability and capability.egress else ""
        print(f"  {call.tool}({call.args or ''}) → {call.target[:60]}")
        print(dim(f"    declared: {call.action_class.value}   authoritative: "
                  f"{authoritative}{flag}{egress}"))
        if call.rationale:
            print(dim(f"    rationale (recorded, never trusted): {call.rationale[:100]}"))
    print(dim("\n  The action class is read from the capability catalogue, not from the model."))
    return 0


def cmd_evidence_verify(args) -> int:
    records = json.loads(Path(args.path).read_text(encoding="utf-8"))
    if isinstance(records, dict):
        records = records.get("records", [])
    from .evidence import GENESIS_HASH, _digest

    previous, problems = GENESIS_HASH, []
    for index, record in enumerate(records):
        if record["seq"] != index:
            problems.append(f"sequence gap at position {index}: found seq {record['seq']}")
        if record["prev_hash"] != previous:
            problems.append(f"broken link at seq {record['seq']}")
        recomputed = _digest(
            record["seq"], record["ts"], record["kind"], record["payload"], record["prev_hash"]
        )
        if recomputed != record["hash"]:
            problems.append(f"altered record at seq {record['seq']}")
        previous = record["hash"]

    heading(f"Evidence chain — {len(records)} record(s)")
    for problem in problems:
        print(red(f"  {problem}"))
    print("  " + verdict(not problems, "chain intact", f"{len(problems)} problem(s) found"))
    print(dim("  Tamper-evidence detects alteration; it does not prevent it."))
    emit({"records": len(records), "intact": not problems, "problems": problems}, args.output)
    return 0 if not problems else 2


def cmd_diode_inventory(args) -> int:
    from .diode_transport import InterfaceInventory

    inventory = InterfaceInventory.reference()
    heading("Interface inventory — every path a directional claim depends on")
    for interface in inventory.interfaces:
        arrow = {"inward": "→", "outward": "←", "bidirectional": "↔"}[interface.direction]
        print(f"  {arrow} {interface.name}")
        print(dim(f"      control: {interface.control}   owner: {interface.owner}"))
        if interface.note:
            print(dim(f"      {interface.note}"))
    print(dim("\n  A hardware diode governs one link. Everything above needs its own control."))
    emit(inventory.to_dict(), args.output)
    return 0


def cmd_diode_receive(args) -> int:
    import time

    from .diode_transport import UdpDiodeReceiver

    received = []

    def handle(item: dict) -> None:
        received.append(item)
        print(json.dumps(item)[:400])

    receiver = UdpDiodeReceiver(
        handle, host=args.host, port=args.port, key=args.key, require_key=not args.insecure
    )
    print(f"listening on {args.host}:{receiver.port} (receive only; this process never sends)")
    receiver.start()
    try:
        while True:
            time.sleep(0.5)
            if args.count and len(received) >= args.count:
                break
    except KeyboardInterrupt:  # pragma: no cover - interactive
        pass
    finally:
        receiver.stop()
    print(json.dumps(receiver.stats.snapshot(), indent=2))
    return 0


def cmd_diode_send(args) -> int:
    from .diode_transport import UdpDiodeSender

    payload = json.loads(Path(args.file).read_text()) if args.file else {"text": args.text}
    with UdpDiodeSender(args.host, args.port, key=args.key, redundancy=args.redundancy) as sender:
        item_id = sender.send_inward(payload)
    print(f"sent {item_id} ({sender.frames_sent} frames, redundancy {args.redundancy})")
    print(dim("no acknowledgement is possible: there is no return path"))
    return 0


def cmd_db_ddl(args) -> int:
    from .postgres_backend import append_only_grants, ddl

    print(ddl(args.schema))
    if args.role:
        print("-- Append-only enforcement at the database level")
        print(append_only_grants(args.role, args.schema))
    return 0


def cmd_db_init(args) -> int:
    from .postgres_backend import database_from_env

    database = database_from_env(args.database_url or os.getenv("FSSAI_DATABASE_URL"))
    print(f"schema ready on {database.dialect.name}")
    return 0


def cmd_serve(args) -> int:
    try:
        import uvicorn
    except ImportError:
        print(red("serving requires the 'api' extra: pip install 'fssaira[api]'"))
        return 1
    target = "fssaira.import_api:create_import_app" if args.gateway else "fssaira.api:create_default_app"
    uvicorn.run(target, factory=True, host=args.host, port=args.port, reload=args.reload)
    return 0


def cmd_init(args) -> int:
    """Scaffold a new domain: profile, contract entry, and a starter test."""
    from .scaffold import scaffold_domain

    created = scaffold_domain(
        Path(args.directory), domain_id=args.domain_id or Path(args.directory).name,
        title=args.title, owner=args.owner, resource=args.resource,
    )
    heading(f"Created {len(created)} file(s)")
    for path in created:
        print(f"  {path}")
    print(dim("\n  Next: edit the transitions, then run"))
    print(dim(f"    fssaira validate-profile {args.directory}/profile.yaml"))
    print(dim(f"    fssaira verify {args.directory}/profile.yaml"))
    print(dim(f"    fssaira evaluate {args.directory}/profile.yaml"))
    return 0


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fssaira",
        description="Fail-Secure Sovereign AI Reference Architecture",
        epilog="Every consequential capability needs an authorization boundary, "
               "an executable failure test, and a named recovery owner.",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--version", action="version", version=f"fssaira {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_output(target):
        target.add_argument("--output", type=Path, help="also write a machine-readable JSON report")
        return target

    version = sub.add_parser("version", help="print version information")
    version.set_defaults(func=cmd_version)

    doctor = add_output(sub.add_parser("doctor", help="report what this deployment actually is"))
    doctor.set_defaults(func=cmd_doctor)

    validate_profile = sub.add_parser("validate-profile", help="validate a domain profile")
    validate_profile.add_argument("profile", type=Path)
    validate_profile.set_defaults(func=cmd_validate_profile)

    validate_contract = sub.add_parser("validate-contract", help="validate control-contract YAML")
    validate_contract.add_argument("contract_directory", type=Path)
    validate_contract.set_defaults(func=cmd_validate_contract)

    contract = add_output(sub.add_parser("contract", help="show the seven-field control contract"))
    contract.add_argument("contract_directory", type=Path, nargs="?", default=Path("contract"))
    contract.set_defaults(func=cmd_contract_show)

    evaluate = add_output(sub.add_parser(
        "evaluate", help="adversarial scenarios, utility baseline, and control ablations"))
    evaluate.add_argument("profile", type=Path)
    evaluate.add_argument("--no-utility", action="store_true")
    evaluate.add_argument("--no-ablations", action="store_true")
    evaluate.set_defaults(func=cmd_evaluate)

    verify = add_output(sub.add_parser(
        "verify", help="bounded model check of a profile's authority invariants"))
    verify.add_argument("profile", type=Path)
    verify.set_defaults(func=cmd_verify)

    conformance = add_output(sub.add_parser(
        "conformance", help="run the portable conformance suite against configured backends"))
    conformance.add_argument("--backend", choices=("memory", "sql"), default="memory")
    conformance.add_argument("--profile", type=Path, default=None)
    conformance.add_argument("--database-url", default=None)
    conformance.set_defaults(func=cmd_conformance)

    race = add_output(sub.add_parser(
        "race-test", help="race many callers against one approved exact action"))
    race.add_argument("profile", type=Path)
    race.add_argument("--callers", type=int, default=32)
    race.set_defaults(func=cmd_race_test)

    resilience = add_output(sub.add_parser(
        "resilience", help="independent-process races and abrupt-exit recovery on synthetic SQLite data"))
    resilience.add_argument("profile", type=Path)
    resilience.add_argument("--callers", type=int, choices=range(2, 33), default=8, metavar="2..32")
    resilience.set_defaults(func=cmd_resilience)

    plugins_cmd = sub.add_parser("plugins", help="list registered backends for every port")
    plugins_cmd.add_argument("--port", default=None)
    plugins_cmd.set_defaults(func=cmd_plugins)

    model = sub.add_parser("model", help="inspect and exercise model backends")
    model_sub = model.add_subparsers(dest="model_command", required=True)
    model_list = model_sub.add_parser("list", help="list available backends")
    model_list.set_defaults(func=cmd_model_list)
    model_health = model_sub.add_parser("health", help="probe a backend")
    model_health.add_argument("name", nargs="?", default=None)
    model_health.set_defaults(func=cmd_model_health)
    model_propose = model_sub.add_parser("propose", help="ask a backend for proposals (nothing executes)")
    model_propose.add_argument("task")
    model_propose.add_argument("--name", default=None)
    model_propose.add_argument("--evidence", action="append")
    model_propose.set_defaults(func=cmd_model_propose)

    evidence = sub.add_parser("evidence", help="work with exported evidence")
    evidence_sub = evidence.add_subparsers(dest="evidence_command", required=True)
    evidence_verify = add_output(evidence_sub.add_parser(
        "verify", help="re-verify an exported hash chain"))
    evidence_verify.add_argument("path", type=Path)
    evidence_verify.set_defaults(func=cmd_evidence_verify)

    diode = sub.add_parser("diode", help="the one-way import path")
    diode_sub = diode.add_subparsers(dest="diode_command", required=True)
    diode_inventory = add_output(diode_sub.add_parser(
        "inventory", help="list the interfaces a directional claim depends on"))
    diode_inventory.set_defaults(func=cmd_diode_inventory)
    diode_receive = diode_sub.add_parser("receive", help="run a receive-only high-side listener")
    diode_receive.add_argument("--host", default="127.0.0.1")
    diode_receive.add_argument("--port", type=int, default=51820)
    diode_receive.add_argument("--key", default=os.getenv("FSSAI_DIODE_KEY"))
    diode_receive.add_argument("--insecure", action="store_true",
                               help="accept unauthenticated frames (states the risk explicitly)")
    diode_receive.add_argument("--count", type=int, default=0, help="stop after N items")
    diode_receive.set_defaults(func=cmd_diode_receive)
    diode_send = diode_sub.add_parser("send", help="send one item inward; no reply is possible")
    diode_send.add_argument("--host", default="127.0.0.1")
    diode_send.add_argument("--port", type=int, default=51820)
    diode_send.add_argument("--key", default=os.getenv("FSSAI_DIODE_KEY"))
    diode_send.add_argument("--redundancy", type=int, default=3)
    diode_send.add_argument("--text", default="hello from the low side")
    diode_send.add_argument("--file", type=Path, default=None)
    diode_send.set_defaults(func=cmd_diode_send)

    db = sub.add_parser("db", help="database schema for the transactional profile")
    db_sub = db.add_subparsers(dest="db_command", required=True)
    db_ddl = db_sub.add_parser("ddl", help="print the schema for review by a DBA")
    db_ddl.add_argument("--schema", default="fssaira")
    db_ddl.add_argument("--role", default=None, help="also print append-only grants for this role")
    db_ddl.set_defaults(func=cmd_db_ddl)
    db_init = db_sub.add_parser("init", help="create the schema")
    db_init.add_argument("--database-url", default=None)
    db_init.set_defaults(func=cmd_db_init)

    serve = sub.add_parser("serve", help="run the control API (or the import gateway)")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8080)
    serve.add_argument("--gateway", action="store_true", help="serve the low-side import gateway")
    serve.add_argument("--reload", action="store_true")
    serve.set_defaults(func=cmd_serve)

    init = sub.add_parser("init", help="scaffold a new domain profile, contract, and test")
    init.add_argument("directory")
    init.add_argument("--domain-id", default=None)
    init.add_argument("--title", default="Replace Me")
    init.add_argument("--owner", default="accountable_service_owner")
    init.add_argument("--resource", default="governed_resource")
    init.set_defaults(func=cmd_init)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not hasattr(args, "verbose"):
        args.verbose = False
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
