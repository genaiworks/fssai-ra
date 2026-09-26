"""``fssaira`` -- the command line for running, checking, and extending the platform.

Public component experiments can be exercised from a source checkout::

    fssaira doctor                          what is this deployment, really?
    fssaira verify profiles/x.yaml          bounded model check of the authority space
    fssaira evaluate profiles/x.yaml        adversarial + utility + ablation suite
    fssaira conformance                     do the configured backends still conform?
    fssaira scale advise --records-per-day N  small-data or big-data tier?
    fssaira small run --archive a.sqlite3   small-data evidence plane, one pass
    python scripts/demo.py --fast           the guided walkthrough
    fssaira init my-domain                  scaffold a new domain from the template

Experiment commands support JSON reports with ``--output``; consult each
subcommand's help for its exact options. A negative experiment judgement exits
nonzero. Service and database commands have their own side effects and setup.
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
    assurance_backend = "memory"
    if args.backend == "sql":
        from .postgres_backend import database_from_env

        database_url = args.database_url or os.getenv("FSSAI_DATABASE_URL") or "sqlite://"
        assurance_backend = "sqlite" if database_url.lower().startswith("sqlite") else "postgres"
        database = database_from_env(database_url, evidence_token="conformance-evidence-writer")
        bundle = sql_bundle(database, profile)
    else:
        bundle = memory_bundle(profile)

    report = run_conformance(bundle)
    heading(f"Conformance — backends: {', '.join(f'{k}={v}' for k, v in report.backends.items())}")
    print(report.render())
    print(dim("\n  Behavioural conformance for these fixtures. Not an audit or certification."))
    emit(report.to_dict(), args.output)

    if args.record_out is not None:
        # A backend inherits no assurance until a record binds it to a passing
        # run on its exact code (kernel.assurance). This is that record, keyed
        # by the module digest so an edit invalidates it. Written as a
        # single-element list so `fssaira.kernel.assurance.load_records` and a
        # `--record-out` from another backend can be concatenated by hand into
        # one file for `fssaira promote --records`.
        from .kernel.assurance import record_from_report

        record = record_from_report(assurance_backend, report)
        Path(args.record_out).write_text(
            json.dumps([record.to_dict()], indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(dim(f"\n  Assurance record for backend {assurance_backend!r} written to {args.record_out}"))

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


def cmd_oversight(args) -> int:
    """Measure whether human review capacity is a declared, bounded quantity."""
    from .oversight import (
        DeclaredReviewerModel,
        ReviewLoadPolicy,
        run_queue_pressure_trial,
        sweep_oversight,
    )
    from .profiles import ApplicationProfile

    profile = ApplicationProfile.load(args.profile)
    policy = ReviewLoadPolicy(
        max_approvals_per_window=args.max_approvals,
        min_deliberation_seconds=args.deliberation_floor,
        second_reviewer_after=args.escalate_after,
    )
    reviewer = DeclaredReviewerModel(attentive_until=args.attentive_until)
    report = run_queue_pressure_trial(
        profile, arrivals=args.arrivals, policy=policy, reviewer=reviewer
    )
    summary = report["summary"]
    capacity = policy.sustainable_actions_per_day(args.reviewers)

    heading(f"Oversight capacity — {report['profile_id']}")
    print(f"  declared ceiling     {policy.max_approvals_per_window} approvals / "
          f"{int(policy.window_seconds)}s per reviewer")
    print(f"  deliberation floor   {policy.min_deliberation_seconds:g}s")
    print(f"  roster of {capacity['reviewers']:<10} sustains {capacity['sustainable_per_day']:g} "
          f"consequential actions/day")
    print(dim(f"  bound by the {capacity['binding_constraint'].replace('_', ' ')}"))

    heading(f"Queue-pressure trial — {report['arrivals']} arrivals, one reviewer")
    without = summary["harmful_executed_without_load_control"]
    with_control = summary["harmful_executed_with_load_control"]
    print(f"  merit failures executed, no load control     {red(str(without))}")
    print(f"  merit failures executed, load control        {green(str(with_control))}")
    print(f"  deferred to the manual fallback              {summary['deferred_to_manual_fallback']}")
    ratio = summary["demand_to_declared_capacity"]
    print(dim(f"  demand ran at {ratio['ratio']}x the declared attentive capacity "
              f"({ratio['arrivals']} arrivals, {ratio['declared_attentive_capacity']} budgeted)"))
    print("\n  " + verdict(
        summary["load_control_is_load_bearing"],
        "the load control is load-bearing: it contained harm the mechanisms cannot see",
        "the load control changed nothing on this queue",
    ))
    print(dim("  The reviewer degradation curve is a declared parameter, not a measurement."))

    # Is the declared policy coherent with itself? An institution should learn
    # this from the tool rather than from a backlog.
    coherence = policy.declared_consistency()
    heading("Is this policy declaration self-consistent?")
    print(f"  quota permits            {coherence['quota_per_window']} per window")
    if coherence["floor_permits_per_window"] is not None:
        print(f"  deliberation floor permits {coherence['floor_permits_per_window']:g} per window")
    print("  " + verdict(coherence["consistent"],
                         f"coherent — the {coherence['binds_first'].replace('_', ' ')} binds first",
                         "INCOHERENT"))
    if not coherence["consistent"]:
        print(yellow(f"  {coherence['note']}"))

    if args.sweep:
        sweep = sweep_oversight(profile, arrivals=args.arrivals)
        totals = sweep["summary"]
        heading(f"Sensitivity sweep — {totals['cells_total']} parameter combinations")
        print(f"  cells where harm was possible          {totals['cells_where_harm_was_possible']}")
        print(f"  ... the control was load-bearing in    "
              f"{green(str(totals['cells_where_the_control_was_load_bearing']))}")
        print(f"  ... harm reached zero in               "
              f"{green(str(totals['cells_where_harm_reached_zero']))}")
        print(f"  ... the control did not bind in        "
              f"{red(str(totals['cells_where_the_control_did_not_bind']))}"
              + dim("  (no deliberation floor configured)"))
        print(f"  cells with no harm to contain          {totals['cells_with_no_harm_to_contain']}"
              + dim("  (an attentive reviewer; the control correctly does nothing)"))
        print(f"  deferrals where nothing was at stake   "
              f"{totals['deferrals_where_there_was_no_harm_to_contain']}"
              + dim("  (the false-positive cost)"))
        floor = totals["smallest_floor_that_fully_contains_everywhere"]
        print(f"  smallest floor that fully contains     "
              f"{'none in this grid' if floor is None else f'{floor:g}s'}")
        print("\n  " + verdict(totals["control_never_created_harm"],
                               "the control never increased harm in any cell",
                               "a cell showed more harm with the control than without"))
        report["sensitivity_sweep"] = sweep

    emit(report, args.output)
    return 0 if summary["harmful_executed_with_load_control"] == 0 else 1


def cmd_challenge(args) -> int:
    """Score the open adversary corpus against all three architectures."""
    from .challenge import ChallengeError, run_corpus

    try:
        report = run_corpus(args.dir)
    except ChallengeError as exc:
        print(red(f"  challenge corpus error: {exc}"))
        return 2

    heading(f"Open adversary corpus — {report['corpus_size']} contributed attacks")
    for item in report["challenges"]:
        print(f"  {bold(item['challenge_id'])}  {item['title']}")
        print(dim(f"    contributed by {item['submitted_by']} ({item['license']})"))
        for arm, result in item["arms"].items():
            mark = green("contained") if result["contained"] else red("HARM")
            codes = ", ".join(result.get("denial_codes", []))
            print(f"    {arm:22} {mark:<22}"
                  + (dim(f"  {codes}") if codes else ""))
        if not item["is_live"]:
            print(yellow("    inert: no harm lands even unguarded; not scored"))
        if not item["expectation_met"]:
            print(yellow(f"    expected {item['expected_harms']}, "
                         f"observed {item['harms_observed_unguarded']}"))

    heading("Containment by architecture")
    live = report["live_challenges"]
    for arm, count in report["contained_by_arm"].items():
        rate = report["containment_rate_by_arm"][arm]
        print(f"  {arm:22} {count}/{live}   {rate:.0%}")

    external = report["externally_contributed"]
    heading("Provenance")
    print(f"  contributors            {len(report['contributors'])}")
    print(f"  externally contributed  {len(external)}"
          + (dim("   — the figure that matters") if not external else ""))
    if not external:
        print(yellow("  Every attack here was written by the maintainers. Until that "
                     "changes,"))
        print(yellow("  this corpus samples the maintainers' imagination. "
                     "See challenges/README.md."))
    emit(report, args.output)
    return 0 if not report["mismatched_expectations"] else 1


def cmd_delegation(args) -> int:
    """Score delegated-authority chains against all three architectures."""
    from .delegation import DelegationPolicy, verify_delegation_space
    from .delegation_eval import ablate_delegation, run_delegation_suite

    policy = DelegationPolicy(max_depth=args.max_depth)
    report = run_delegation_suite(policy)

    heading(f"Delegated authority — {report.scenarios} chain scenarios, 3 architectures")
    by_scenario: dict = {}
    for outcome in report.outcomes:
        by_scenario.setdefault(outcome.scenario, {})[outcome.arm] = outcome
    for name, arms in by_scenario.items():
        benign = name == "benign_two_hop"
        print(f"  {bold(name)}" + (dim("   (control case: must complete)") if benign else ""))
        for arm in ("unguarded", "caller_checked", "this_architecture"):
            outcome = arms[arm]
            mark = green("contained") if outcome.contained else red("HARM")
            if benign:
                mark = green("completed") if outcome.contained else red("REFUSED")
            print(f"    {arm:20} {mark:<22}" + dim(f"  {outcome.code}"))

    heading("Containment by architecture")
    for arm in ("unguarded", "caller_checked", "this_architecture"):
        count = report.contained(arm)
        print(f"  {arm:20} {count}/{report.hostile_total}"
              f"   {count / report.hostile_total:.0%}")
    print(dim("  'caller_checked' validates each hop against its immediate delegator "
              "only —"))
    print(dim("  a real control, and not the same thing as verifying the chain."))

    heading("Is each invariant load-bearing?")
    ablations = ablate_delegation(policy)
    for row in ablations:
        mark = green("load-bearing") if row["load_bearing"] else yellow("did not bind")
        print(f"  {row['control']:34} {mark:<24}"
              + dim(f"  {row['with_control']} vs {row['without_control']}"))

    space = verify_delegation_space(policy)
    heading("Bounded model check over the declared chain space")
    print(f"  states explored   {space.states_explored:,}")
    print(f"  admitted          {space.admitted}")
    print(f"  violations        {space.violations and red(str(len(space.violations))) or green('0')}")
    for line in space.to_dict()["limits"]:
        print(dim(f"  - {line}"))

    payload = {**report.to_dict(), "ablations": ablations,
               "verification": space.to_dict()}
    emit(payload, args.output)
    return 0 if report.holds and space.holds else 1


def cmd_assisted_review(args) -> int:
    """Measure what a review assistant does to the oversight argument."""
    from .assisted_review import run_assisted_review_trial
    from .profiles import ApplicationProfile, ProfileError

    try:
        profile = ApplicationProfile.load(args.profile)
    except ProfileError as exc:
        print(red(f"  profile error: {exc}"))
        return 2

    report = run_assisted_review_trial(
        profile, arrivals=args.arrivals,
        unaided_floor=args.unaided_floor, lowered_floor=args.lowered_floor,
    )
    summary = report["summary"]

    heading(f"Assisted review — {report['arrivals']} arrivals, one reviewer")
    for arm, counters in report["arms"].items():
        if not counters.get("started"):
            print(f"  {bold(arm)}")
            print(f"    {red('refused at configuration')}  {counters['code']}")
            print(dim(f"    permitted floor {counters['permitted_floor_seconds']}s"))
            continue
        harm = counters["harmful_executed"]
        mark = green("0 merit failures") if harm == 0 else red(f"{harm} merit failures")
        print(f"  {bold(arm)}")
        print(f"    {mark:<30} benign completed {counters['benign_executed']}"
              f"   deferred {counters['deferred_to_manual_fallback']}")
        print(dim(f"    floor {counters['deliberation_floor_seconds']}s  "
                  f"independence {counters['assistance']['independence_score']}/3  "
                  f"oversight refusals {counters['oversight']['refusals_by_code'] or 'none'}"))

    heading("What the arms show")
    print(f"  merit failures   unaided {summary['merit_failures_unaided']}"
          f"  ·  dependent {summary['merit_failures_assisted_dependent']}"
          f"  ·  independent {summary['merit_failures_assisted_independent']}")
    print(f"  benign completed unaided {summary['benign_completed_unaided']}"
          f"  ·  assisted {summary['benign_completed_assisted_independent']}"
          f"   ({summary['benign_completion_gain_from_assistance']}x)")
    if summary["every_mechanism_passed_in_the_harmful_arm"]:
        print(yellow("  Every runtime mechanism passed in the harmful arm: chain intact,"))
        print(yellow("  reviewer inside quota, every approval above the configured floor,"))
        print(yellow("  no oversight refusal. There is no runtime signal to alert on."))
    for line in report["limits"]:
        print(dim(f"  - {line}"))

    emit(report, args.output)
    return 0 if summary["configuration_gate_refused_the_harmful_arm"] else 1


def cmd_coverage(args) -> int:
    """Is each contract requirement enforced, or only written down?"""
    from .coverage import measure_coverage

    try:
        report = measure_coverage(args.dir)
    except ValueError as exc:
        print(red(f"  coverage error: {exc}"))
        return 2

    heading(f"Control-contract coverage — {report.total} requirements")
    for row in report.requirements:
        if row.status == "machine_verified":
            mark = green("machine-verified")
            detail = ", ".join(sorted({b.mechanism for b in row.bindings}))
        elif row.status == "organizationally_attested":
            mark = yellow("attested")
            detail = f"{row.attested_by}, {row.attestation_cadence}"
        else:
            mark = red("UNVERIFIED")
            detail = "a test described in prose and bound to nothing"
        print(f"  {row.requirement_id:6} {row.domain:22} {mark:<26}" + dim(f"  {detail}"))

    heading("Totals")
    print(f"  machine-verified            {report.machine_verified}")
    print(f"  organizationally attested   {report.organizationally_attested}")
    unverified = report.unverified
    print("  unverified                  "
          + (green("0") if unverified == 0 else red(str(unverified))))
    if unverified:
        print(red("  These requirements describe a failure test and bind it to nothing."))
        print(red("  A control that exists in review and not at runtime is the exact"))
        print(red("  failure this project exists to eliminate."))
    if report.unknown_bindings:
        print(red(f"  bindings naming unknown requirements: {report.unknown_bindings}"))
    for line in report.to_dict()["limits"]:
        print(dim(f"  - {line}"))

    emit(report.to_dict(), args.output)
    return 0 if report.holds else 1


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


def cmd_packet_check(args) -> int:
    from .packet_verifier import main as inspect_main

    arguments = [str(args.path)]
    if args.expected_sha256 is not None:
        arguments += ["--expected-sha256", args.expected_sha256]
    return inspect_main(arguments)


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


def cmd_scale_advise(args) -> int:
    from .scale import Workload, recommend

    report = recommend(Workload(
        peak_writes_per_second=args.peak_writes_per_second,
        records_per_day=args.records_per_day,
        archive_gb=args.archive_gb,
        independent_consumers=args.consumers,
        writer_hosts=args.writer_hosts,
        high_availability=args.high_availability,
    ))
    heading(f"Data tier — {report['tier']}")
    for reason in report["reasons"]:
        mark = red("✗ exceeds") if reason["exceeded"] else green("✓ within ")
        print(f"  {mark} {reason['criterion']:<24} {reason['workload']!s:>10}  "
              f"(small-tier limit {reason['small_tier_limit']})")
        if reason["exceeded"]:
            print(dim(f"      {reason['why_big_data_helps']}"))
    print(f"\n  run: {report['run']}")
    print(dim(f"  {report['note']}"))
    emit(report, args.output)
    return 0


def cmd_scale_measure(args) -> int:
    from .scale import measure_sqlite

    report = measure_sqlite(args.records)
    heading("SQLite evidence-append throughput on this host")
    print(f"  {report['appends_per_second']} durable appends/s "
          f"({report['records']} in {report['seconds']} s)")
    print(f"  {report['headroom_over_default_limit']}x the small tier's default peak limit")
    print("  " + verdict(report["chain_intact"], "chain intact", "chain broken"))
    if report["platform_caveat"]:
        print(yellow(f"  {report['platform_caveat']}"))
    emit(report, args.output)
    return 0 if report["chain_intact"] else 2


def _small_archive(args):
    from .small_data import SqliteArchiveStore

    return SqliteArchiveStore(args.archive)


def _small_ingest(args) -> dict:
    from .envelope_mac import key_from_env
    from .small_data import SqliteImportLog, ingest_imports

    log = SqliteImportLog(args.log)
    archive = _small_archive(args)
    try:
        return ingest_imports(log, archive, mac_key=key_from_env("FSSAI_IMPORT_ENVELOPE_KEY"),
                              allow_unsigned=args.allow_unsigned)
    finally:
        log.close()
        archive.close()


def _small_archive_ledger(args) -> dict:
    from .small_data import archive_ledger

    archive = _small_archive(args)
    try:
        return archive_ledger(args.database or os.environ["FSSAI_DATABASE_URL"], archive,
                              ledger_id=args.ledger_id)
    finally:
        archive.close()


def _small_verify(args) -> dict:
    from .small_data import verify_archive

    if (args.checkpoint is None) != (args.public_keys is None):
        raise SystemExit("--checkpoint and --public-keys must be given together")
    archive = _small_archive(args)
    try:
        return verify_archive(
            archive, ledger_id=args.ledger_id, since_seq=args.since_seq,
            checkpoint=json.loads(args.checkpoint.read_text()) if args.checkpoint else None,
            public_keys=json.loads(args.public_keys.read_text()) if args.public_keys else None,
            mode=args.mode)
    finally:
        archive.close()


def _print_verification(report: dict) -> bool:
    ok = report["verdict"] in {"INTACT", "EMPTY"}
    mode = report.get("mode", "full")
    scope = (f"{report['records']} record(s) from seq {report['verified_from_seq']}"
             if mode == "incremental" and "verified_from_seq" in report
             else f"{report['records']} record(s)")
    heading(f"Archived evidence chain — {mode}, {scope}")
    if report.get("code"):
        print(red(f"  {report['code']}: {report.get('detail', '')}"))
    for check in ("chain_valid", "links_intact", "sequence_complete", "no_duplicates"):
        if check in report:
            print("  " + verdict(report[check], check, check))
    if "checkpoint" in report:
        print("  " + verdict(report["checkpoint"]["valid"], "signed checkpoint holds",
                             f"checkpoint: {report['checkpoint']['code']}"))
    print("  " + verdict(ok, report["verdict"], report["verdict"]))
    return ok


def cmd_small_ingest(args) -> int:
    report = _small_ingest(args)
    heading("Imports: log → archive")
    print(f"  imported {report['imported']}, quarantined {report['quarantined']}")
    emit(report, args.output)
    return 0


def cmd_small_archive(args) -> int:
    report = _small_archive_ledger(args)
    heading("Evidence: ledger → archive")
    print(f"  archived {report['records']} new record(s) for {report['ledger_id']!r}")
    emit(report, args.output)
    return 0


def cmd_small_verify(args) -> int:
    report = _small_verify(args)
    ok = _print_verification(report)
    emit(report, args.output)
    return 0 if ok else 2


def cmd_small_run(args) -> int:
    """One pass of the small-data evidence plane: ingest, archive, verify."""
    report: dict = {}
    if args.log:
        report["ingest"] = _small_ingest(args)
    if args.database or os.getenv("FSSAI_DATABASE_URL"):
        report["archive"] = _small_archive_ledger(args)
    report["verify"] = _small_verify(args)
    ok = _print_verification(report["verify"])
    if "ingest" in report:
        print(f"  imports: {report['ingest']['imported']} imported, "
              f"{report['ingest']['quarantined']} quarantined")
    if "archive" in report:
        print(f"  ledger: {report['archive']['records']} new record(s) archived")
    emit(report, args.output)
    return 0 if ok else 2


def cmd_witness_cosign(args) -> int:
    """Co-sign one notary checkpoint, in this separate process, under the witness's own key."""
    from .evidence_notary import Checkpoint
    from .witness import CheckpointWitness, WitnessRefused

    keys = {k: bytes.fromhex(v) for k, v in json.loads(args.notary_keys.read_text()).items()}
    witness = CheckpointWitness.from_key_file(args.key_file, args.dir, notary_keys=keys,
                                              key_id=args.key_id)
    checkpoint = Checkpoint(**json.loads(args.checkpoint.read_text()))
    extension = None
    if args.archive is not None:
        from .small_data import SqliteArchiveStore

        start = (witness.state() or {"count": 0})["count"]
        archive = SqliteArchiveStore(args.archive)
        try:
            extension = [row for row in archive.evidence_rows(args.ledger_id, start)
                         if row["seq"] < checkpoint.count]
        finally:
            archive.close()
    try:
        cosignature = witness.cosign(checkpoint, extension)
    except WitnessRefused as refused:
        print(red(f"refused: {refused.code}: {refused.detail}"))
        emit({"cosigned": False, "code": refused.code, "detail": refused.detail}, args.output)
        return 2
    print(green(f"co-signed {cosignature.count} record(s) ({cosignature.first_seen})"))
    emit({"cosigned": True, "cosignature": cosignature.to_dict(),
          "witness_public_keys": {k: v.hex() for k, v in witness.public_keys.items()}},
         args.output)
    return 0


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
    print(dim(f"    fssaira coverage --dir {args.directory}"))
    print(dim("\n  The contract entry is scaffolded with a binding to the test"))
    print(dim("  file. Delete that test and coverage will name the governance"))
    print(dim("  claim you just removed, which is the whole point of the file."))
    return 0


def cmd_profiles(args) -> int:
    """Validate and inventory the reusable domain packs."""
    from .evaluation import EvaluationRunner
    from .profiles import ApplicationProfile, discover_profiles
    from .verification import verify_profile

    profiles = discover_profiles(args.directory)
    if args.verify:
        for summary in profiles:
            profile = ApplicationProfile.load(summary["path"])
            verification = verify_profile(profile)
            evaluation = EvaluationRunner(profile).run()
            summary["assurance"] = {
                "states_explored": verification.states_explored,
                "invariants_hold": verification.holds,
                "scenarios_contained": evaluation.passed,
                "scenarios_total": evaluation.total,
                "unauthorized_mutations": evaluation.unauthorized_mutations,
                "benign_completed": evaluation.benign_completed,
                "benign_total": len(evaluation.utility),
            }
            if profile.disclosure is not None:
                from .disclosure_eval import run_disclosure_suite

                disclosure = run_disclosure_suite(
                    profile.disclosure, profile_id=profile.profile_id
                ).to_dict()["summary"]
                summary["assurance"]["disclosure"] = disclosure
    payload = {"profiles": profiles, "count": len(profiles)}
    if args.output:
        emit(payload, args.output)
        return 0
    heading(f"Domain packs — {len(profiles)} validated profiles")
    for profile in profiles:
        print(f"  {profile['profile_id']:<34} {profile['domain']}")
        print(dim(
            f"    {profile['transitions']} transitions · "
            f"{profile['consequential_transitions']} consequential · "
            f"roles: {', '.join(profile['approval_roles'])}"
        ))
        print(dim(f"    purpose: {profile['purpose']}"))
        if "assurance" in profile:
            assurance = profile["assurance"]
            print(dim(
                f"    checked: {assurance['states_explored']} states · "
                f"{assurance['scenarios_contained']}/{assurance['scenarios_total']} hostile · "
                f"{assurance['benign_completed']}/{assurance['benign_total']} benign"
            ))
    print(dim("\n  External frameworks are applicability declarations, not compliance claims."))
    return 0


def cmd_disclosure(args) -> int:
    """Govern what a model may read and what may leave: containment, ablation, model check."""
    from .disclosure_eval import run_disclosure_suite
    from .profiles import ApplicationProfile, ProfileError

    try:
        profile = ApplicationProfile.load(args.profile)
    except ProfileError as exc:
        print(red(f"  profile error: {exc}"))
        return 2
    if profile.disclosure is None:
        print(red(f"  {profile.profile_id} declares no disclosure section; "
                  "nothing governs what its model may read or release"))
        return 2

    report = run_disclosure_suite(profile.disclosure, profile_id=profile.profile_id)
    payload = report.to_dict()
    heading(f"Governed disclosure — {profile.profile_id}: "
            f"{report.hostile_total} hostile flows, 3 architectures")
    arms = tuple(report.arms)
    print(dim("  " + " " * 42 + "  ".join(f"{arm:>18}" for arm in arms)))
    for name in report.arms["this_architecture"]:
        cells = []
        for arm in arms:
            row = report.arms[arm][name]
            cells.append(f"{(red('LEAKED') if row['reached'] else green('contained')):>27}")
        print(f"  {name:42}" + "".join(cells))
    heading("Containment by architecture")
    for arm in arms:
        count = report.contained(arm)
        print(f"  {arm:20} {count}/{report.hostile_total}   {count / report.hostile_total:.0%}")
    print(dim("  'access_controlled' is signed, expiring, class-cleared grants plus an output"))
    print(dim("  check on the label the model claims: a conscientious conventional design."))

    heading("Legitimate work still completes")
    for name, row in report.benign.items():
        print(f"  {name:48} " + (green("completed") if row["reached"] else red("REFUSED")))
    for name in report.not_applicable:
        print(dim(f"  {name:48} not applicable to this pack"))

    heading("Is each check load-bearing?")
    for row in report.ablations:
        mark = green("load-bearing") if row["load_bearing"] else yellow("did not bind")
        print(f"  {row['check']:32} {mark:<24}" + dim(f"  {len(row['harms_restored'])} harm(s) return"))

    summary = payload["verification"]["summary"]
    heading("Bounded model check over reads and releases")
    print(f"  states explored   {summary['states_explored']:,}")
    print(f"  violations        {summary['violations'] and red(str(summary['violations'])) or green('0')}")
    print("  evidence holds no protected values   "
          + (green("yes") if report.evidence_minimized else red("NO")))
    for line in payload["limits"]:
        print(dim(f"  - {line}"))
    emit(payload, args.output)
    return 0 if report.holds else 1


def cmd_threats(args) -> int:
    """Alignment failures and AI threats: what contains each, and what remains."""
    from .threats import STATUSES, ThreatCatalogueError, check_catalogue

    try:
        report = check_catalogue(args.catalogue)
    except ThreatCatalogueError as exc:
        print(red(f"  catalogue error: {exc}"))
        return 2
    payload = report.to_dict()
    heading(f"Threat and alignment catalogue — {len(report.threats)} failure classes")
    marks = {"contained": green, "bounded": yellow, "residual": red}
    for family in ("alignment", "security", "data", "systemic"):
        print(bold(f"  {family}"))
        for threat in (t for t in report.threats if t.family == family):
            print(f"    {threat.id:6} {marks[threat.status](f'{threat.status:9}')}  {threat.title}")
    heading("Totals")
    for status in STATUSES:
        print(f"  {status:10} {report.count(status)}")
    if report.missing_locators:
        heading("Evidence that does not exist")
        for line in report.missing_locators:
            print(red(f"  {line}"))
    print(dim("\n  contained: the governed harm did not occur through a governed interface in"))
    print(dim("  tested fixtures, whatever the model intended. It is not a probability."))
    emit(payload, args.output)
    return 0 if report.holds else 1


def cmd_conference_pack_check(args) -> int:
    """Refuse a domain pack that weakens the kernel, naming every attempt."""
    from .pack_floor import check_pack, read_pack

    findings = check_pack(read_pack(args.path))
    heading(f"Kernel floor — {args.path}")
    for finding in findings:
        print(f"  {red(finding.code)}  {finding.where}")
        print(dim(f"      {finding.detail}"))
    print(green("  at or above the kernel floor") if not findings else red(f"  {len(findings)} finding(s): rejected"))
    return 0 if not findings else 1


def cmd_conference_falsify(args) -> int:
    """Attack the architecture; judge by what happened, not by denial codes."""
    import json as _json

    from .falsification import run_falsifiers

    results = run_falsifiers([args.falsifier] if args.falsifier else None)
    if args.json:
        print(_json.dumps([r.to_dict() for r in results], indent=2))
        return 0 if all(r.held for r in results) else 1
    heading("Falsification — a model trying to break the institution")
    for result in results:
        mark = green("HELD") if result.held else red("VIOLATED")
        print(f"  {result.id} {result.name:28} {mark}  {dim(result.property)}")
        for item in result.attempts:
            print(dim(f"      {'✕ ' + item.code if not item.violated else 'VIOLATION'}  {item.name}"))
    held = sum(r.held for r in results)
    print(f"\n  {held} of {len(results)} falsifiers held")
    return 0 if held == len(results) else 1


def cmd_conference_ablation(args) -> int:
    """Remove exactly one control, rerun the attack, restore it, rerun."""
    import json as _json

    from .falsification import run_ablation

    rows = run_ablation([args.falsifier] if args.falsifier else None)
    if args.json:
        print(_json.dumps([r.to_dict() for r in rows], indent=2))
        return 0
    heading("Ablation — are the controls load-bearing?")
    print(dim(f"  {'falsifier':<5} {'control':<44} {'enabled':<9} {'disabled':<10} {'restored':<9} load-bearing"))
    for row in rows:
        body = row.to_dict()
        verdict = green("YES") if row.load_bearing else dim(body["load_bearing"])
        print(f"  {row.falsifier:<5} {row.control:<44} {body['enabled']:<9} {body['disabled']:<10} "
              f"{body['restored']:<9} {verdict}")
    return 0


def cmd_conference_trace(args) -> int:
    """One request through the ten governed steps, with the system-literacy view."""
    import json as _json

    from .education_models import HonestAssistant, MaliciousAssistant, OllamaAssistant
    from .governed_request import explain, run_governed_request

    if args.model == "ollama":
        model = OllamaAssistant()
        if not model.available():
            print(red("  no local Ollama runtime is reachable; nothing was run"))
            return 2
    else:
        model = HonestAssistant() if args.model == "honest" else MaliciousAssistant()
    trace = run_governed_request(model=model)
    if args.json:
        print(_json.dumps({**trace.to_dict(), "system_literacy": explain(trace)}, indent=2, default=str))
        return 0
    print(trace.render())
    heading("System literacy")
    for key, value in explain(trace).items():
        print(f"  {key:<9} {str(value)[:160]}")
    return 0


def cmd_conference_adaptive(args) -> int:
    """An offline adaptive attacker vs static and random, scored by an independent oracle."""
    import json as _json

    from .adaptive_attack import run_adaptive

    report = run_adaptive(budget=args.budget, seed=args.seed, remove=args.remove,
                          split=args.split, include_live=args.live,
                          prove_attacker=args.prove_attacker)
    payload = report.to_dict()
    if args.json:
        print(_json.dumps(payload, indent=2, default=str))
        return 0
    heading(f"Adaptive attack — {args.budget} queries/track, split={args.split}"
            + (f", removed: {', '.join(report.controls_removed)}" if report.controls_removed else ""))
    for track in payload["tracks"]:
        if not track["ran"]:
            print(dim(f"  {track['attacker']:8} {track['note']}"))
            continue
        mark = green("0 forbidden") if not track["forbidden_outcomes"] else red(
            f"{track['forbidden_outcomes']} forbidden {dict(track['by_class'])}")
        print(f"  {track['attacker']:8} {track['queries']:>4} queries  {mark}")
    if payload["positive_control"] is not None:
        pc = payload["positive_control"]
        print(dim(f"  positive control (−{pc['control_removed']}): "
                  f"{pc['forbidden_outcomes']} forbidden {dict(pc['by_class'])} "
                  "— the attacker and oracle work"))
    print(dim("  oracle: forbidden effects judged from world observations, not denial logs"))
    # With all controls on and no controls removed, any forbidden outcome is a real
    # finding and must fail the command.
    return 1 if (report.total_forbidden and not report.controls_removed) else 0


def cmd_conference_stateful(args) -> int:
    """Seeded random authority sequences, eight properties checked after every step."""
    from .authority_stateful import run_stateful

    report = run_stateful(sequences=args.sequences, remove=args.remove).to_dict()
    heading(f"Stateful testing — {report['steps']:,} steps"
            + (f", removed: {', '.join(report['controls_removed'])}" if report["controls_removed"] else ""))
    for key, item in report["properties"].items():
        mark = green("0") if not item["violations"] else red(str(item["violations"]))
        print(f"  {key} {item['property']:<66} {mark}")
    print(f"  false denials: {report['false_denials']}")
    for line in report["first_counterexample"]:
        print(dim(f"    {line}"))
    return 0 if report["holds"] or report["controls_removed"] else 1


def cmd_conference_lab(args) -> int:
    """Serve the attack lab locally. Ablation is a lab-only capability."""
    import runpy

    script = Path(__file__).resolve().parents[2] / "scripts" / "conference_lab.py"
    sys.argv = [str(script), "--port", str(args.port)]
    runpy.run_path(str(script), run_name="__main__")
    return 0


def cmd_thesis(args) -> int:
    """Try to refute the Mediation Thesis across every declared domain pack."""
    from .thesis import COMMITMENTS, RULES, THESIS, TRUSTED_BASE, run_thesis

    report = run_thesis()
    payload = report.to_dict()
    heading(f"The Mediation Thesis — {THESIS}")
    for index, line in enumerate(COMMITMENTS, start=1):
        print(dim(f"  {index}. {line}"))
    for index, line in enumerate(RULES, start=1):
        print(f"  R{index}  {line}")
    heading("Falsification attempts")
    for falsifier in report.falsifiers:
        mark = red("REFUTED") if falsifier.refuted else green("not refuted")
        print(f"  {falsifier.id} {falsifier.name:22} {falsifier.attempts:>9,} attempts  "
              f"{falsifier.counterexamples:>3} counterexamples  {mark}")
        print(dim(f"      refuted by: {falsifier.refuted_by}"))
    heading("Verdict")
    summary = payload["summary"]
    print(f"  {summary['attempts']:,} bounded attempts, {summary['counterexamples']} counterexamples: "
          + (green(summary["verdict"]) if report.holds else red(summary["verdict"])))
    heading("Outside every falsifier: the trusted base")
    for item in TRUSTED_BASE:
        print(dim(f"  - {item}"))
    heading("Residuals the thesis does not address")
    for item in payload["residuals"]:
        print(f"  {item['id']:6} {item['title']}")
    emit(payload, args.output)
    return 0 if report.holds else 1


def cmd_pilot_report(args) -> int:
    """Field indicators for a governed-disclosure pilot, from exported evidence."""
    from .disclosure_metrics import disclosure_metrics

    raw = json.loads(Path(args.path).read_text(encoding="utf-8"))
    records = raw.get("records", []) if isinstance(raw, dict) else raw
    report = disclosure_metrics(records)
    heading(f"Pilot indicators — {report['evidence']['records']} evidence records")
    intact = report["evidence"]["intact"]
    print("  evidence chain   " + (green("intact") if intact else
                                   yellow("not verifiable") if intact is None else red("BROKEN")))
    for name in ("reads", "releases", "declassifications"):
        row = report[name]
        print(f"  {name:17} {row['attempts']:>6} attempts  {row['released']:>6} released  "
              f"{row['refused']:>6} refused")
        for code, count in row["refusals_by_code"].items():
            print(dim(f"      {code:40} {count}"))
    glass = report["break_glass"]
    print(f"  break-glass       {glass['opened']} opened, {glass['reviewed']} reviewed, "
          f"{glass['awaiting_review']} awaiting; median review "
          f"{glass['review_latency_seconds']['median']} s")
    outputs = report["outputs"]
    print(f"  outputs           {outputs['labelled']} labelled; "
          f"{outputs['claimed_downgrade_attempts']} claimed downgrades; "
          f"{outputs['value_label_fell_back_to_session']} value labels fell back to session")
    heading("What these indicators cannot tell you")
    for line in report["cannot_measure"]:
        print(dim(f"  - {line}"))
    emit(report, args.output)
    return 2 if intact is False else 0


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def cmd_assure_chaos(args) -> int:
    from .revocation_chaos import run_campaign

    report = run_campaign(seeds=args.seeds)
    heading(f"Revocation under chaos — {args.seeds} seeded runs per discipline")
    for name, arm in report["arms"].items():
        clean = arm["stale_effects"] == 0 and arm["duplicate_applications"] == 0
        label = "design" if name == "fenced" else "ablation"
        print(f"  {verdict(clean, name, name):<28} {label:<9} stale={arm['stale_effects']:<5} "
              f"duplicates={arm['duplicate_applications']:<6} refused={arm['refused_stale']}")
    print("  " + verdict(report["design_holds"], "fenced commit holds every invariant",
                         "fenced commit violated an invariant"))
    emit(report, args.output)
    return 0 if report["design_holds"] and all(report["ablations_detected"].values()) else 2


def cmd_framework_catalogue(args) -> int:
    from .framework import load, validate

    catalogue = load()
    problems = validate(catalogue)
    heading(f"Framework catalogue {catalogue.version} — {len(catalogue.patterns)} patterns, "
            f"{len(catalogue.controls)} controls")
    for code, name in catalogue.domains.items():
        controls = [c for c in catalogue.controls if c.domain == code]
        print(f"  {code}  {name:<40} {len(controls):>3} controls")
    for level, name in sorted(catalogue.levels.items()):
        print(dim(f"  level {level} {name}: "
                  f"{sum(c.level == level for c in catalogue.controls)} controls become required"))
    print("  " + verdict(not problems, "every module, test and refusal code it cites exists",
                         f"{len(problems)} broken reference(s)"))
    for problem in problems:
        print(red(f"    {problem}"))
    emit({"patterns": len(catalogue.patterns), "controls": len(catalogue.controls),
          "problems": problems}, args.output)
    return 0 if not problems else 2


def cmd_framework_assess(args) -> int:
    from .framework import assess, load_answers, roadmap

    answers = load_answers(args.answers)
    result = assess(answers)
    heading(f"Maturity — evidenced level {result['evidenced_level']} "
            f"({result['evidenced_level_name']}), claimed level {result['claimed_level']}")
    for code, domain in result["domains"].items():
        print(f"  {code}  {domain['name']:<40} evidenced L{domain['evidenced_level']}  "
              f"claimed L{domain['claimed_level']}  "
              f"({domain['evidenced']}/{domain['applicable']} evidenced)")
    if result["claim_gap"]:
        print(yellow(f"  claim gap: {result['claim_gap']} level(s) implemented but not evidenced"))
    for warning in result["warnings"]:
        print(yellow(f"  ! {warning}"))
    payload = {"assessment": result}
    if args.roadmap:
        plan = roadmap(answers)
        payload["roadmap"] = plan
        for wave in plan["waves"]:
            title = "Wave to level {} — {}".format(wave["to_level"], wave["name"])
            print(f"\n  {bold(title)}")
            for item in wave["controls"]:
                blocked = f"  after {', '.join(item['blocked_by'])}" if item["blocked_by"] else ""
                tag = "prove" if item["evidence_only"] else "build"
                print(f"    {item['id']:<7} {tag:<5} {item['name']}  [{item['owner']}]{dim(blocked)}")
    emit(payload, args.output)
    if args.min_level is not None and result["evidenced_level"] < args.min_level:
        print(red(f"\n  evidenced level {result['evidenced_level']} is below the required "
                  f"{args.min_level}"))
        return 2
    return 0


def cmd_framework_init(args) -> int:
    from .framework import init_workspace

    written = init_workspace(args.directory, org=args.org, sector=args.sector,
                             target_level=args.target_level)
    heading(f"Starter workspace for {args.org} ({args.sector}) — {len(written)} files")
    for path in written:
        print(f"  {path}")
    print(f"\n  next: fssaira framework assess {args.directory / 'assessment.yaml'} --roadmap")
    return 0


def cmd_framework_render(args) -> int:
    from .framework import render_markdown, render_patterns, validate

    problems = validate()
    if problems:
        for problem in problems:
            print(red(problem))
        return 2
    ok = True
    for target, text in ((args.path, render_markdown()), (args.patterns_path, render_patterns())):
        if args.check:
            current = target.read_text(encoding="utf-8") if target.exists() else ""
            matches = current == text
            ok = ok and matches
            print(verdict(matches, f"{target} matches the catalogue", f"{target} is stale; run render"))
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
            print(f"wrote {target}")
    return 0 if ok else 2


def cmd_framework_patterns(args) -> int:
    from .framework import pattern_manifest, validate

    problems = validate()
    if problems:
        for problem in problems:
            print(red(problem))
        emit({"problems": problems}, args.output)
        return 2
    manifest = pattern_manifest()
    if args.output is None:
        print(json.dumps(manifest, indent=2))
    else:
        emit(manifest, args.output)
    return 0


def cmd_assure_report(args) -> int:
    from .assurance_report import build_report

    report = build_report(seeds=args.seeds, qualification_seeds=args.qualification_seeds)
    heading(f"Master-guide assurance report — {report['verdict']}")
    for name, section in report["deterministic"]["sections"].items():
        print("  " + verdict(section["passed"], name, name))
    print(f"  digest sha256:{report['digest']}")
    print(dim(f"  {report['host']['seconds']} s on Python {report['host']['python']}; compare "
              "digests across hosts to confirm the same result"))
    emit(report, args.output)
    return 0 if report["verdict"] == "PASS" else 2


def cmd_assure_trusted_base(args) -> int:
    from .refusal_registry import scan
    from .trusted_base import report as trusted_report

    report = {**trusted_report(), "refusal_codes": len(scan())}
    size = report["size"]
    heading("Trusted base — measured, not asserted")
    for name, component in size["components"].items():
        print(f"  {name:<16} {component['files']:>3} files  {component['sloc']:>6} SLOC")
    print(f"  trusted {size['trusted_sloc']} of {size['package_sloc']} SLOC "
          f"({size['trusted_fraction']:.1%}); native code in package: "
          f"{len(size['native_code_in_package'])}")
    print(f"  build measurement sha256:{report['build']['measurement']}")
    print(f"  SBOM: CycloneDX {report['sbom']['specVersion']}, "
          f"{len(report['sbom']['components'])} dependencies; "
          f"{report['refusal_codes']} registered refusal codes")
    emit(report, args.output)
    return 0


def cmd_assure_staffing(args) -> int:
    from .oversight_staffing import ReviewDemand, staffing

    report = staffing(ReviewDemand(
        arrivals_per_hour=args.arrivals_per_hour, mean_review_seconds=args.mean_review_seconds,
        floor_seconds=args.floor_seconds, low_risk_per_hour=args.low_risk_per_hour,
        audit_rate=args.audit_rate, target_wait_seconds=args.target_wait_seconds,
        service_level=args.service_level), on_shift=args.on_shift)
    heading("Review staffing for the declared floor")
    print(f"  effective review time {report['effective_review_seconds']} s"
          + (" (the floor binds)" if report["floor_binds"] else ""))
    print(f"  reviewers needed: {report['reviewers_needed']}  "
          f"(utilisation {report['at_needed']['utilisation']}, "
          f"service level {report['at_needed']['service_level']})")
    if args.on_shift is not None:
        print("  " + verdict(report["verdict"] == "STAFFED", "staffed",
                             f"understaffed: {report['deferred_per_hour']} items/h go to the "
                             "manual route; do not lower the floor"))
    emit(report, args.output)
    return 0


def cmd_mcp_scan(args) -> int:
    """List what each MCP server would show a model, and flag instruction-like text."""
    from .integration.mcp_gate import GateConfig, scan

    report = scan(GateConfig.load(args.config))
    for server in report["servers"]:
        print(f"{server['name']}  ({server['server_info'].get('name', '?')} "
              f"{server['server_info'].get('version', '')}, operator {server['operator'] or 'UNDECLARED'})")
        for tool in server["tools"]:
            flags = ", ".join(f["finding"] for f in tool["findings"])
            mark = red("✗") if flags else green("✓")
            role = "privileged" if tool["privileged"] else "ordinary"
            declared = "" if tool["policy"]["declared"] else yellow(" [no policy: treated as privileged]")
            print(f"  {mark} {tool['wire_name']:<32} {role}{declared}" + (f"  {red(flags)}" if flags else ""))
    print(f"\n{report['tools']} tool(s), {report['flagged_tools']} flagged. "
          "A clean scan is a review aid, not approval.")
    emit(report, args.output)
    return 1 if report["flagged_tools"] else 0


def cmd_mcp_lock(args) -> int:
    """Record a named human's approval of exactly what the servers list now."""
    from .integration.mcp_gate import GateConfig, lock, write_json

    data = lock(GateConfig.load(args.config), approved_by=args.approved_by,
                accept_findings=args.accept_findings or ())
    write_json(data, args.lock)
    approved = sum(len(s["tools"]) for s in data["servers"])
    print(green(f"locked {approved} tool(s) for {len(data['servers'])} server(s), "
                f"approved by {data['approved_by']}") + f"  -> {args.lock}")
    for item in data["excluded"]:
        print(red(f"  excluded {item['tool']}: " + ", ".join(f["finding"] for f in item["findings"])))
    if data["excluded"]:
        print("  review the text, then pass --accept-findings server/tool to approve it knowingly")
    return 0


def cmd_mcp_serve(args) -> int:
    """Run the gate on stdio. Protocol on stdout; everything else on stderr."""
    from .integration.mcp_gate import Gate, GateConfig, ReceiptLog, load_lock, serve

    gate = Gate(GateConfig.load(args.config), load_lock(args.lock), receipts=ReceiptLog(args.receipts))
    gate.start()
    status = gate.status()
    print(f"fssaira mcp gate: {len(status['tools'])} tool(s) offered, {len(status['hidden'])} hidden; "
          f"receipts -> {args.receipts or 'memory only'}", file=sys.stderr)
    try:
        serve(gate)
    finally:
        gate.close()
    return 0



def cmd_mcp_verify(args) -> int:
    """Recompute a receipt log's hash chain."""
    from .integration.mcp_gate import verify_receipts

    report = verify_receipts(args.receipts)
    print(verdict(report["verified"], f"{report['receipts']} receipt(s) chain to {report['head'][:16]}",
                  "receipt log does not verify"))
    for key, count in report["decisions"].items():
        print(f"  {key:<28} {count}")
    for problem in report["problems"]:
        print(red(f"  seq {problem['seq']}: {problem['problem']}"))
    emit(report, args.output)
    return 0 if report["verified"] else 2


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

    contract = add_output(sub.add_parser(
        "contract", help="show the seven-field control contract; with --gate, run lifecycle stage 2"))
    contract.add_argument("contract_directory", type=Path, nargs="?", default=Path("contract"))
    from .lifecycle.cli import add_contract_gate
    add_contract_gate(contract, show=cmd_contract_show)

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
    conformance.add_argument("--record-out", type=Path, default=None,
                             help="also write a fssaira.kernel.assurance conformance record here, "
                                  "for `fssaira promote --records` / FSSAI_CONFORMANCE_RECORDS")
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

    oversight = add_output(sub.add_parser(
        "oversight", help="measure review capacity and run the queue-pressure trial"))
    oversight.add_argument("profile", type=Path)
    oversight.add_argument("--arrivals", type=int, default=40,
                           help="consequential actions arriving in the queue")
    oversight.add_argument("--reviewers", type=int, default=11,
                           help="roster size, for the published capacity arithmetic")
    oversight.add_argument("--max-approvals", type=int, default=60,
                           help="declared per-reviewer ceiling per window")
    oversight.add_argument("--deliberation-floor", type=float, default=45.0,
                           help="minimum seconds between presentation and approval")
    oversight.add_argument("--escalate-after", type=int, default=40,
                           help="approvals in a window after which a second reviewer is required")
    oversight.add_argument("--attentive-until", type=int, default=8,
                           help="declared reviewer attention budget (a parameter, not a measurement)")
    oversight.add_argument("--sweep", action="store_true",
                           help="also sweep the declared parameters and report every cell")
    oversight.set_defaults(func=cmd_oversight)

    challenge = add_output(sub.add_parser(
        "challenge", help="score the open adversary corpus against all three architectures"))
    challenge.add_argument("--dir", default="challenges",
                           help="directory of contributed challenge YAML files")
    challenge.set_defaults(func=cmd_challenge)

    delegation = add_output(sub.add_parser(
        "delegation",
        help="score delegated-authority chains against all three architectures"))
    delegation.add_argument("--max-depth", type=int, default=3,
                            help="declared maximum delegation depth (default 3)")
    delegation.set_defaults(func=cmd_delegation)

    assisted = add_output(sub.add_parser(
        "assisted-review",
        help="what a review assistant does to the oversight argument"))
    assisted.add_argument("profile", nargs="?", default="profiles/student_support.yaml")
    assisted.add_argument("--arrivals", type=int, default=40)
    assisted.add_argument("--unaided-floor", type=float, default=45.0,
                          help="deliberation floor for an unaided reader, in seconds")
    assisted.add_argument("--lowered-floor", type=float, default=10.0,
                          help="floor the deployment wants to run with once assisted")
    assisted.set_defaults(func=cmd_assisted_review)

    coverage = add_output(sub.add_parser(
        "coverage", help="is each contract requirement enforced, or only written down?"))
    coverage.add_argument("--dir", default="contract",
                          help="directory holding the control contract")
    coverage.set_defaults(func=cmd_coverage)

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

    scale = sub.add_parser("scale", help="choose the small-data or big-data tier")
    scale_sub = scale.add_subparsers(dest="scale_command", required=True)
    advise = add_output(scale_sub.add_parser(
        "advise", help="recommend a tier from the expected workload"))
    advise.add_argument("--peak-writes-per-second", type=float, default=1.0)
    advise.add_argument("--records-per-day", type=int, default=1_000)
    advise.add_argument("--archive-gb", type=float, default=1.0)
    advise.add_argument("--consumers", type=int, default=1,
                        help="systems that must read the event stream independently")
    advise.add_argument("--writer-hosts", type=int, default=1)
    advise.add_argument("--high-availability", action="store_true",
                        help="the evidence plane must survive losing one host")
    advise.set_defaults(func=cmd_scale_advise)
    measure = add_output(scale_sub.add_parser(
        "measure", help="measure durable SQLite evidence appends on this host"))
    measure.add_argument("--records", type=int, default=500)
    measure.set_defaults(func=cmd_scale_measure)

    mcp = sub.add_parser("mcp", help="gate Model Context Protocol tool servers (scan, lock, serve)")
    mcp_sub = mcp.add_subparsers(dest="mcp_command", required=True)
    mcp_scan = add_output(mcp_sub.add_parser(
        "scan", help="show what each server would tell a model; flags instruction-like text"))
    mcp_scan.add_argument("--config", type=Path, required=True, help="gate policy YAML")
    mcp_scan.set_defaults(func=cmd_mcp_scan)
    mcp_lock = mcp_sub.add_parser("lock", help="approve the current listing, by name, into a lock file")
    mcp_lock.add_argument("--config", type=Path, required=True, help="gate policy YAML")
    mcp_lock.add_argument("--lock", type=Path, required=True, help="lock file to write")
    mcp_lock.add_argument("--approved-by", required=True, help="the named human approving")
    mcp_lock.add_argument("--accept-findings", action="append", metavar="SERVER/TOOL",
                          help="approve one flagged tool knowingly (repeatable)")
    mcp_lock.set_defaults(func=cmd_mcp_lock)
    mcp_serve = mcp_sub.add_parser("serve", help="run the gate as an MCP server on stdio")
    mcp_serve.add_argument("--config", type=Path, required=True, help="gate policy YAML")
    mcp_serve.add_argument("--lock", type=Path, required=True, help="lock file from `mcp lock`")
    mcp_serve.add_argument("--receipts", type=Path, help="append-only receipt log (JSON lines)")
    mcp_serve.set_defaults(func=cmd_mcp_serve)
    mcp_verify = add_output(mcp_sub.add_parser("verify", help="verify a receipt log's hash chain"))
    mcp_verify.add_argument("receipts", type=Path)
    mcp_verify.set_defaults(func=cmd_mcp_verify)

    witness = sub.add_parser("witness", help="out-of-process witness for evidence checkpoints")
    witness_sub = witness.add_subparsers(dest="witness_command", required=True)
    cosign = add_output(witness_sub.add_parser(
        "cosign", help="co-sign a checkpoint that extends everything already witnessed"))
    cosign.add_argument("--dir", type=Path, required=True, help="the witness's own state directory")
    cosign.add_argument("--key-file", type=Path, required=True, help="the witness's owner-only key")
    cosign.add_argument("--key-id", default="evidence-witness-1")
    cosign.add_argument("--notary-keys", type=Path, required=True,
                        help="trusted notary public keys, {key_id: hex}")
    cosign.add_argument("--checkpoint", type=Path, required=True, help="notary checkpoint JSON")
    cosign.add_argument("--archive", type=Path,
                        help="archive holding the new records (proves the head extends)")
    cosign.add_argument("--ledger-id", default="primary")
    cosign.set_defaults(func=cmd_witness_cosign)

    small = sub.add_parser(
        "small", help="small-data evidence plane: SQLite log, archive and verifier, no cluster")
    small_sub = small.add_subparsers(dest="small_command", required=True)

    def small_parser(name: str, help_text: str, *, log: bool, database: bool, verify: bool):
        target = add_output(small_sub.add_parser(name, help=help_text))
        target.add_argument("--archive", type=Path, required=True,
                            help="archive SQLite file; keep it on separate storage")
        if log:
            target.add_argument("--log", type=Path, required=(name == "ingest"),
                                help="the gateway's FSSAI_IMPORT_LOG_PATH")
            target.add_argument("--allow-unsigned", action="store_true",
                                help="accept envelopes without a MAC (no FSSAI_IMPORT_ENVELOPE_KEY)")
        if database:
            target.add_argument("--database", help="ledger URL (default FSSAI_DATABASE_URL)")
        if database or verify:
            target.add_argument("--ledger-id", default="primary")
        if verify:
            target.add_argument("--since-seq", type=int, default=0)
            target.add_argument("--checkpoint", type=Path,
                                help="signed checkpoint JSON retained outside the archive")
            target.add_argument("--public-keys", type=Path,
                                help="trusted notary public keys, {key_id: hex}")
            target.add_argument("--mode", choices=["auto", "full", "incremental"],
                                default="auto",
                                help="auto: full while the archive is small or once a day, "
                                     "otherwise from the last verified head")
        return target

    small_parser("ingest", "move gateway imports from the log into the archive",
                 log=True, database=False, verify=False).set_defaults(func=cmd_small_ingest)
    small_parser("archive", "append new ledger records to the archive",
                 log=False, database=True, verify=False).set_defaults(func=cmd_small_archive)
    small_parser("verify", "independently recompute the archived chain",
                 log=False, database=False, verify=True).set_defaults(func=cmd_small_verify)
    small_parser("run", "ingest, archive and verify in one pass (for cron or a loop)",
                 log=True, database=True, verify=True).set_defaults(func=cmd_small_run)

    packet = sub.add_parser("packet-check", help="inspect a private decision packet offline; missing anchor exits 2")
    packet.add_argument("path", type=Path)
    packet.add_argument("--expected-sha256", default=None)
    packet.set_defaults(func=cmd_packet_check)

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

    profiles = add_output(sub.add_parser(
        "profiles", help="validate and inventory reusable domain packs"
    ))
    profiles.add_argument("--directory", type=Path, default=Path("profiles"))
    profiles.add_argument(
        "--verify", action="store_true",
        help="also run bounded verification, adversarial scenarios, and benign tasks",
    )
    profiles.set_defaults(func=cmd_profiles)

    disclosure = add_output(sub.add_parser(
        "disclosure",
        help="what may a model read, and what may leave? containment, ablation, model check",
    ))
    disclosure.add_argument("profile", type=Path)
    disclosure.set_defaults(func=cmd_disclosure)

    threats = add_output(sub.add_parser(
        "threats", help="alignment failures and AI threats: what contains each, what remains",
    ))
    threats.add_argument("--catalogue", type=Path, default=Path("threats/catalogue.yaml"))
    threats.set_defaults(func=cmd_threats)

    thesis = add_output(sub.add_parser(
        "thesis", help="try to refute the Mediation Thesis: six falsifiers, every domain pack",
    ))
    thesis.set_defaults(func=cmd_thesis)

    # The seven-stage lifecycle: frame, contract, pack, bind, falsify, promote, operate.
    from .lifecycle.cli import register as register_lifecycle
    register_lifecycle(sub)

    pilot = add_output(sub.add_parser(
        "pilot-report", help="field indicators for a governed-disclosure pilot, from exported evidence",
    ))
    pilot.add_argument("path", type=Path)
    pilot.set_defaults(func=cmd_pilot_report)

    conference = sub.add_parser(
        "conference", help="the UNU Macau demonstration layer: falsify, ablate, trace, lab")
    conference_sub = conference.add_subparsers(dest="conference_command", required=True)
    pack_check = conference_sub.add_parser("pack-check", help="check a domain pack against the kernel floor")
    pack_check.add_argument("path", type=Path)
    pack_check.set_defaults(func=cmd_conference_pack_check)
    falsify = conference_sub.add_parser("falsify", help="run every falsifier, or one (e.g. F19)")
    falsify.add_argument("falsifier", nargs="?")
    falsify.add_argument("--json", action="store_true")
    falsify.set_defaults(func=cmd_conference_falsify)
    ablation = conference_sub.add_parser("ablation", help="enabled / disabled / restored per control")
    ablation.add_argument("falsifier", nargs="?")
    ablation.add_argument("--json", action="store_true")
    ablation.set_defaults(func=cmd_conference_ablation)
    trace = conference_sub.add_parser("trace", help="one governed request in ten steps")
    trace.add_argument("--model", choices=("honest", "malicious", "ollama"), default="honest")
    trace.add_argument("--json", action="store_true")
    trace.set_defaults(func=cmd_conference_trace)
    adaptive = conference_sub.add_parser(
        "adaptive", help="an offline adaptive attacker vs static/random, independent oracle")
    adaptive.add_argument("--budget", type=int, default=200, help="queries per attacker track")
    adaptive.add_argument("--seed", type=int, default=20260921)
    adaptive.add_argument("--split", choices=("dev", "held-out", "all"), default="all")
    adaptive.add_argument("--remove", action="append", default=[], help="ablate a control")
    adaptive.add_argument("--live", action="store_true", help="also run the local-model track if reachable")
    adaptive.add_argument("--prove-attacker", action="store_true",
                          help="positive control: remove a mediator and show the attacker wins")
    adaptive.add_argument("--json", action="store_true")
    adaptive.set_defaults(func=cmd_conference_adaptive)
    stateful = conference_sub.add_parser("stateful", help="random authority sequences checked after every step")
    stateful.add_argument("--sequences", type=int, default=120)
    stateful.add_argument("--remove", action="append", default=[])
    stateful.set_defaults(func=cmd_conference_stateful)
    lab = conference_sub.add_parser("lab", help="serve the educational attack lab on 127.0.0.1")
    lab.add_argument("--port", type=int, default=8765)
    lab.set_defaults(func=cmd_conference_lab)

    assure = sub.add_parser(
        "assure", help="master-guide assurance: revocation chaos, trusted base, review staffing")
    assure_sub = assure.add_subparsers(dest="assure_command", required=True)
    chaos = add_output(assure_sub.add_parser(
        "chaos", help="revocation under partitions, duplicates, delay and clock skew"))
    chaos.add_argument("--seeds", type=int, default=200)
    chaos.set_defaults(func=cmd_assure_chaos)
    tbase = add_output(assure_sub.add_parser(
        "trusted-base", help="SLOC per trusted component, build measurement and SBOM"))
    tbase.set_defaults(func=cmd_assure_trusted_base)
    staff = add_output(assure_sub.add_parser(
        "staffing", help="reviewers a declared review floor needs (Erlang C)"))
    staff.add_argument("--arrivals-per-hour", type=float, required=True)
    staff.add_argument("--mean-review-seconds", type=float, required=True)
    staff.add_argument("--floor-seconds", type=float, default=45.0)
    staff.add_argument("--low-risk-per-hour", type=float, default=0.0)
    staff.add_argument("--audit-rate", type=float, default=0.0)
    staff.add_argument("--target-wait-seconds", type=float, default=3600.0)
    staff.add_argument("--service-level", type=float, default=0.8)
    staff.add_argument("--on-shift", type=int)
    staff.set_defaults(func=cmd_assure_staffing)
    areport = add_output(assure_sub.add_parser(
        "report", help="every master-guide engineering check in one digest-stamped report"))
    areport.add_argument("--seeds", type=int, default=100)
    areport.add_argument("--qualification-seeds", type=int, default=20)
    areport.set_defaults(func=cmd_assure_report)

    framework = sub.add_parser(
        "framework", help="the adoption framework: catalogue, self-assessment, roadmap, starter kit")
    framework_sub = framework.add_subparsers(dest="framework_command", required=True)
    fcat = add_output(framework_sub.add_parser(
        "catalogue", help="summarise and validate the control catalogue"))
    fcat.set_defaults(func=cmd_framework_catalogue)
    fassess = add_output(framework_sub.add_parser(
        "assess", help="score a self-assessment; --roadmap for the build order"))
    fassess.add_argument("answers", type=Path, help="assessment.yaml from `framework init`")
    fassess.add_argument("--roadmap", action="store_true")
    fassess.add_argument("--min-level", type=int,
                         help="exit non-zero if the evidenced level is below this (CI gate)")
    fassess.set_defaults(func=cmd_framework_assess)
    finit = framework_sub.add_parser("init", help="write a starter workspace for an organisation")
    finit.add_argument("directory", type=Path)
    finit.add_argument("--org", required=True)
    finit.add_argument("--sector", required=True,
                       choices=["education", "healthcare", "finance", "corporate", "government",
                                "benefits"])
    finit.add_argument("--target-level", type=int, default=4)
    finit.set_defaults(func=cmd_framework_init)
    fpatterns = add_output(framework_sub.add_parser(
        "patterns", help="export canonical P1-P34 bindings and the assessment scale"))
    fpatterns.set_defaults(func=cmd_framework_patterns)
    frender = framework_sub.add_parser("render", help="regenerate canonical pattern and control guides")
    frender.add_argument("--path", type=Path, default=Path("docs/framework/CONTROLS.md"))
    frender.add_argument("--patterns-path", type=Path, default=Path("docs/framework/PATTERNS.md"))
    frender.add_argument("--check", action="store_true")
    frender.set_defaults(func=cmd_framework_render)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not hasattr(args, "verbose"):
        args.verbose = False
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
