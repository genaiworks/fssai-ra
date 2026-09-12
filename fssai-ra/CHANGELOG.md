# Changelog

## Unreleased — composition: delegated authority, assisted review, and a contract that measures itself

### The oversight control was not active in any real deployment

The worst finding in this release, and it was ours.

- **Fixed: `build_control_plane()` built its `ApprovalAuthority` with no
  oversight monitor.** `ControlPlane` had accepted one since the oversight work
  shipped, and the runtime factory — the thing that assembles every actual
  deployment, including the HTTP API and the console — never passed it. Review
  capacity was therefore enforced in the CLI trial and in the test suite, and
  **nowhere a real institution would run the platform.** Every test that
  exercised oversight constructed the monitor itself, which is exactly why three
  releases went by without noticing: the suite was green and the control was
  absent. This is the failure the control contract exists to eliminate, found in
  the headline contribution.
- **Fixed: none of the three declarable policies could be declared.**
  `ReviewLoadPolicy`, `DelegationPolicy` and `ReviewAssistance` existed as
  library objects with no path from a deployment's environment, so an
  institution could read the paper, agree with it, and have no way to state its
  own numbers. All three now have `from_env()`.
- The two policies return **`None` when nothing is declared**, and deliberately
  do not fall back to ours. A capacity figure inherited from a reference
  implementation is one nobody at that institution agreed to; publishing "2,640
  actions per day" on the strength of a number we chose would be worse than
  publishing nothing. `ReviewAssistance` always returns a value, because *not*
  declaring assistance is itself the strict declaration: reviewers are unaided
  and the full deliberation floor applies.
- `fssaira doctor` now reports the absences rather than letting them stay
  invisible: `NO_DECLARED_REVIEW_CAPACITY` (high), `NO_DECLARED_DELEGATION_BOUND`
  (info), `INCOHERENT_REVIEW_POLICY` (medium), `DEPENDENT_REVIEW_ASSISTANT`
  (high), and two blocking findings — `ASSISTANCE_NOT_DECLARED` and
  `FLOOR_BELOW_DECLARED_INDEPENDENCE`, the configuration gate surfaced where an
  operator actually looks.
- `/health` gained `declared_controls`. An unenforced ceiling is invisible from
  every other observable: a deployment with no declared capacity looks identical
  to one running inside its capacity, right up to the moment it is not.
- `deploy/.env.example` documents all thirteen variables with the reasoning
  inline, and `test_every_variable_the_example_documents_is_actually_read` fails
  the build if it ever describes a variable no code reads — the same drift that
  had `docs/REVIEWERS.md` promising `394 passed` against a suite of 477.

### Reachability, hygiene, and the checks that were missing

- Three assurance endpoints — `/v1/coverage`, `/v1/delegation`,
  `/v1/assisted-review` — published like `/v1/conformance`, operator-role gated,
  with the regenerated OpenAPI schema. The console's Assurance tab shows all
  three.
- **Fixed: `fssaira init` scaffolded new domains into this project's own worst
  finding** — a contract entry with a failure test bound to nothing. It now
  writes `bindings/core.yaml` pointing at the test file it also writes, so a new
  domain starts at `0 unverified`.
- CI's assurance job runs coverage, delegation and assisted review. Its comment
  says a failure there means a public claim has stopped being true; three public
  claims were not being checked.
- **Fixed: `console/tsconfig.tsbuildinfo` was tracked.** Untracked and ignored.
- **Fixed: the lab had quietly become 105 minutes** while every document still
  said ninety. Added a timetable-consistency test, which immediately found a
  second error — exercise 6 states 15 minutes and the timetable allotted 10. The
  lab is now honestly two hours with a documented ninety-minute cut path.
- **Fixed: `docs/REVIEWERS.md` told a sceptic to expect `394 passed`** against a
  suite of 477. It was the one front-door document outside the READMEs quoting a
  figure with nothing checking it; it is checked now.
- `PROCUREMENT.md` gained §8 delegated authority and §9 review-assistant
  independence with blocking-finding rows, because the paper claims independence
  is procurement language and it was not in the questionnaire. `SECURITY.md`
  names the two assumptions the threat model had been making silently and adds
  six residual risks, including that **revocation is not pushed to already-issued
  descendants**. `OPERATIONS.md` documents the declarations and eight new denial
  codes. `GLOSSARY.md`, `RESPONSIBLE_AI.md`, `ADOPTION.md`, `EXTENDING.md`,
  `SYSTEM_LITERACY.md`, `LAB.md`, `CITATION.cff` and both paper indexes updated.
- Added a repository-root `Makefile` so a first-time user can run `make setup`,
  `make demo`, `make test`, and `make reviewer` without knowing the nested Python
  package layout. Every package recipe now uses configurable `PYTHON ?= python3`,
  fixing modern macOS installations where the `python` command is absent.
- Added a linked documentation map, a complete 90-minute source-reading route,
  and `docs/GAPS.md`, an open-evidence register that names the field, human,
  hardware, and independent-assurance work software tests cannot close.
- CI now covers Python 3.10–3.14, uses Node 24-based action releases, builds and
  installs the wheel, checks citation-title agreement, audits Python and console
  dependencies, and runs the complete 13-gate reviewer path locally. Replaced
  deprecated Starlette `httpx` test support with `httpx2`; upgraded Vite to the
  first patched 6.x release and verified a zero-vulnerability console audit.
- Modernized package licensing to an SPDX expression, removed the deprecated
  license classifier, and pointed package metadata at the audience-specific
  documentation map rather than the engineering README.


### The contract now checks whether it is enforced

Seven fields per capability is this project's central claim, and one of the seven
is an executable failure test. The loader validated that every requirement *had*
that field. It never checked that the test **existed**.

- **Found: 18 of 28 requirements described a failure test and bound it to
  nothing.** Most of them did have tests; nothing connected the two, so deleting
  a test would have removed a governance claim in silence. `profiles.py` already
  says what that is — *a control that existed in review and not at runtime is the
  exact failure this project exists to eliminate* — and it was in our own
  contract.
- Added `fssaira coverage` and `fssaira.coverage`: three-way coverage over the
  control contract. **machine_verified** (an executable check is bound to it),
  **organizationally_attested** (a named role on a declared cadence, for controls
  no program can prove — key custody, the signed interface inventory, retention
  policy), or **unverified**. Counting attestations as coverage would inflate the
  figure with promises; counting them as gaps would make it permanently
  uninformative. Publishing all three lets an adopter ask the only useful
  question: are the attested controls the genuinely unprovable ones, or the
  inconvenient ones?
- Added `contract/bindings/`, kept separate from the contract itself because the
  contract is the institution's document and the bindings are this
  implementation's claim about it.
- `test_every_binding_locator_actually_exists` resolves every binding against the
  real source. Without it the coverage report would be a YAML file asserting its
  own correctness — a more convincing version of the problem it was written to
  detect. It caught eight fabricated locators on its first run, all ours.
- `test_organizational_attestation_does_not_grow_silently` pins the attested
  count, so declaring a control unprovable is a visible edit rather than a quiet
  one.
- **Fixed: ET-2 had no check at all.** The dead-letter path and idempotent
  producer were implemented in `kafka_backend` and exercised by nothing reachable
  without a live broker. Added conformance check `CF-ET-03`: a redelivery must be
  distinguishable, so a projection can be idempotent. Conformance is now 26
  checks, not 25.
- Current figures: **33 machine-verified, 3 attested, 0 unverified.**

### Authority that travels: delegated authority between agents

Every control before this governs one agent under one grant. That was right for
the agent of 2023 and is not the shape institutions deploy, now that
orchestrators spawn sub-agents and sub-agents call tool servers they did not
write. `ToolCall` carried a single `agent_id`; the word "delegation" appeared in
the teaching docs and nowhere in the source.

- Added `fssaira.delegation` and `fssaira delegation`. The rule: **no principal
  may pass on authority it does not itself hold, and no chain may end with more
  authority than its root was granted.** Authority under delegation is
  monotonically non-increasing, so a chain is checkable in one pass without
  trusting any hop's account of itself, and what it confers at the leaf is the
  *intersection* of every grant along it.
- Nine invariants, each with a stable denial code and each independently
  ablatable: attenuation, rooted authority, depth bound, temporal containment,
  acyclicity, provenance, non-delegable consequence, holder binding, beneficiary
  attenuation. **All nine are load-bearing** — each removed in turn, each
  restoring its harm.
- Three arms over the same chains: unguarded contains **0/10**, per-hop
  validation contains **2/10**, chain verification contains **10/10**, and the
  benign two-hop chain completes in all three. The middle arm is the finding: it
  is a real control and what a careful engineer builds, and it cannot see the
  root, so lapsed ancestors, repeated principals and unrooted origins pass
  straight through. **Local validation at every hop is not verifying the chain.**
- Bounded model checking over the declared chain space: **768 configurations, 5
  invariants, 0 violations.**
- **Fixed, in this module's own first run: the checker admitted the confused
  deputy.** Every invariant held — the chain was authentic, rooted, attenuated,
  unexpired, acyclic and within depth. It simply was not the *requester's* chain.
  An authority object bound to nobody is a bearer token, which is the thing this
  architecture exists to refuse. Added D8a (holder binding) and D8b (beneficiary
  attenuation: work done *for* another principal runs under that principal's
  authority, intersected with the actor's), with regression tests.
- Added contract domain 7, `DL-1` to `DL-5`.

### Assisted review: what happens when the reviewer also has a model

The oversight contribution establishes that review is finite and that a queue
beyond the ceiling turns oversight into a signature service while every test
stays green. That argument models an **unaided** reader, and by 2026 that
assumption is false almost everywhere.

- Added `fssaira.assisted_review` and `fssaira assisted-review`. Assistance is
  not the mistake: it completes **5x** the legitimate work of the unaided arm,
  which contains every merit failure by deferring 32 of 40 cases. The mistake is
  what it does to the deliberation floor, which an assisted deployment must lower
  or else throttle reviewers doing their jobs.
- The floor was never measuring seconds. It was a proxy for *a second mind
  independently reaching the same conclusion*, and that survives only if the
  assistant is independent of the proposer. Same model family, same evidence
  packet, and it is the proposer's reasoning arriving again in a reviewer's
  badge — wrong the same way, fluently, on exactly the cases that matter.
- Measured: identical queues, identical lowered floor, differing only in declared
  independence — **5 merit failures with a dependent assistant, 1 with an
  independent one.** In the harmful arm the evidence chain is intact, the
  reviewer is inside quota, every approval clears the floor, and no oversight
  refusal fires. **There is no runtime signal to alert on.**
- So the enforcement point is a **configuration gate**, refusing at startup with
  `FLOOR_BELOW_DECLARED_INDEPENDENCE` and naming the floor the declaration would
  have to rise to. At runtime a dependent assistant and an independent one are
  indistinguishable; the difference exists only in the declaration, so that is
  where it is enforced.
- Independence is three things an institution can answer about itself and a
  procurement process can require in writing: a different model from the
  proposer, an evidence path that is not the proposer's assembled packet, and an
  adversarial posture tasked with finding grounds to refuse.
- **The independent arm reaches 1, not 0**, and that is the result rather than a
  tuning failure. Independence multiplies effective attention; it does not make
  attention unbounded. An institution that buys an assistant has bought a larger
  ceiling to compute, not permission to stop computing one.
- The proposer/assistant error correlation is a **declared parameter**, exactly
  like the reviewer degradation curve. No model was evaluated and no rate is
  claimed for any named system. Measuring it is named open work.
- Added contract domain 8, `AR-1` to `AR-3`.

### Paper, deck and docs

- `paper/composition-supplement.md`: the full method and results for both
  contributions, held to the same alignment standard as the abstract — its
  figures are checked against generated results and its limits against a required
  list.
- The extended abstract gains §4 and the assisted-review extension of §3, and its
  word bound moves from 1,650 to 1,900. That is recorded as a decision in
  `test_the_word_count_fits_the_submission_guidance`, with the cut order in
  `paper/SUBMISSION.md` naming what goes first if a hard cap applies. The limits
  section is never the thing that gets cut.
- Four new pinned claims in `tests/test_paper_alignment.py`. A new figure in the
  paper without an entry there is a number nothing checks — which would be an
  embarrassing thing to ship alongside the coverage work.
- Deck: two new slides (16, the assisted reviewer; 17, authority that travels).
  The speaker script's routing and timing tables are renumbered to match, and the
  presenter guide with them.
- `make reviewer` is now twelve steps, with coverage first: whether the contract
  is enforced should be established before any figure it produces is read.

## Earlier unreleased work — oversight capacity, a second domain, and an open adversary corpus

### Sensitivity, and two defects it found in our own work

A single queue-pressure trial with three chosen numbers invites one fair
objection: the parameters were picked to suit the result. So they are swept, and
the whole surface is published — including the cells where the control does
nothing.

- Added `fssaira oversight --sweep` and `sweep_oversight()`: 25 parameter
  combinations of reviewer attention budget against deliberation floor. The
  control was load-bearing in 16 of the 20 cells where harm was possible, harm
  reached zero in 16, it never increased harm in any cell, and the 4 non-binding
  cells (no deliberation floor configured) are reported rather than omitted.
- **Fixed: the shipped review policy contradicted itself.** A 20-per-hour quota
  paired with a 45-second deliberation floor bound four times earlier than the
  floor, so a reviewer reading every case was still deferred. The sweep surfaced
  it as 75 false-positive deferrals. Defaults are now 60 per hour with escalation
  at 40, and the false-positive cost across the sweep is **0**.
- **Fixed: the two capacity ceilings were not comparable quantities.** The quota
  ceiling was computed over 24 hours and the attention ceiling over a reviewer's
  actual availability, inflating the quota fourfold and naming the wrong binding
  constraint. Both now use the declared working day. The published capacity for a
  roster of 11 moves from 3,520 to **2,640 consequential actions per day**, now
  bound by the quota rather than by attention.
- Added `ReviewLoadPolicy.declared_consistency()`, which reports whether a quota
  and a deliberation floor contradict each other, and in which direction. It
  deliberately does not repair the declaration: choosing the number on an
  institution's behalf is the move this project exists to refuse.

### Two artifacts an institution can use without installing anything

- Added [`docs/oversight/`](docs/oversight/), a browser calculator that works out
  an institution's oversight ceiling from numbers it already has. One
  self-contained file: no build, no network call, no storage, no analytics —
  because working out that you are over capacity should not require telling
  anyone. `tests/test_oversight_calculator.py` extracts its JavaScript and runs
  it against the Python implementation over six input regimes, so the take-home
  tool cannot drift from the enforcement code.
- Added [`docs/LAB.md`](docs/LAB.md), a ninety-minute offline lab for people who
  will approve, procure, or govern one of these systems. Every command it prints
  is checked against the real parser by `tests/test_lab.py`, because a facilitator
  discovers a broken command in front of twenty people on conference wifi. It
  states plainly that no cohort has run it and no learning gain is claimed.
- Added `make reviewer`, which runs everything a reviewer should check in one
  command, and `make oversight`, `make challenge`, `make second-domain`, `make lab`.

### The corpus, widened

- Grew the adversary corpus from 4 entries to 10, covering egress through a
  granted tool, an out-of-scope operation on a granted tool, unbounded
  consumption, a non-URL exfiltration destination, an honestly-declared
  consequential action, and **one negative control**: ordinary legitimate work
  that must succeed. A corpus of attacks alone measures only refusal.
- `fssaira challenge` now reports coverage derived from the run — harms actually
  exercised, denial controls actually reached, risk classes referenced — rather
  than from a taxonomy asserted here, and distinguishes a negative control from
  an attack stopped before its harm could land.
- Added a GitHub issue template so an attack can be contributed without cloning
  anything.
- Writing the corpus caught a smaller thing worth recording: an entry built to
  test the per-agent call budget sent exactly the budgeted number of calls and
  saw nothing refused. A contributor would have concluded no budget existed.

### Also

- Wired the oversight monitor through `ControlPlane`, so the HTTP API and the
  console enforce review capacity on the same path the CLI does. `approve()` now
  takes `presented_at` and refuses to infer it from the proposal's creation time:
  a proposal that queued for an hour and was approved in two seconds has an hour
  of elapsed time and two seconds of deliberation.


### Human review is a finite resource, and now a bounded one

Every control this project shipped routed a consequential action to a named human
and then treated that human as unlimited. Push a queue past a reviewer's attention
and every mechanism here still passes its tests while the oversight it all funnels
into becomes a signature service. A system can be perfectly accountable and
completely unreviewed, and nothing in `v1.0.0` could tell the difference.

- Added `fssaira.oversight`: a declared review capacity per reviewer per window, a
  deliberation floor below which an approval is **refused at issue** rather than
  flagged afterwards, mandatory escalation to a second distinct reviewer under
  sustained load, and a publishable report of approvals, median deliberation,
  escalations, refusals, and remaining headroom.
- `ApprovalAuthority` takes an optional oversight monitor. With none configured
  its behaviour is unchanged, and a test asserts that rather than assuming it.
- Added `fssaira oversight`, which computes what a roster can genuinely sustain
  (11 reviewers → 2,640 consequential actions/day with the shipped defaults, bound
  by the deliberation floor) and runs a queue-pressure trial against it. At five
  times declared capacity: 4 structurally valid but substantively wrong actions
  execute without the control, 0 with it, at a reported cost of 32 deferrals.
- Added control-contract requirements `AA-8` and `AA-9` for the two new controls.
- **The reviewer degradation curve is a declared parameter, not a measurement of
  any human.** No reviewer was observed. `docs/ASSURANCE.md` §7 names reviewer
  behaviour under load as the largest open gap between this and a field claim.

### A second domain, because one proves nothing about a method

- Added `profiles/academic_record_correction.yaml`, structurally different from
  the reference profile: a multi-role chain, a rejection an appeal can reopen, and
  five transitions over six statuses.
- The identical verifier, evaluator, and conformance suite hold on it with **no
  change to library code**: 4,800 configurations, 0 violations, 30/30 contained,
  9/9 benign, 25 conformance checks. Each domain carries its own evidence.
- **Fixed a real defect the second domain exposed on its first run.**
  `ApplicationProfile.required_approval_roles` was built only from *consequential*
  transitions, so a routine transition that declared an `approval_role` had it
  silently ignored — a mandatory schema field that did nothing at runtime. The
  offline packet checker had the same gap and would have cleared a packet the
  executor refuses. Both now enforce the declared role on every transition. This
  was unreachable in the reference profile, where every transition is
  consequential. Regression: `tests/test_generalization.py`.

### An adversary who is not the author

- Added `challenges/`, an open corpus in which an attack is seven fields of YAML —
  the grant an agent holds and what a compromised model proposes — validated
  strictly, executing no contributor code, and scored against all three
  architecture arms with attribution.
- Added `fssaira challenge`. It prints the externally contributed count, which is
  **0**, in the output rather than in a limitations paragraph.
- **Fixed a defect the corpus found in our own measurement.** Harm was counted by
  tool name, so records leaving through a tool not classified as egress scored as
  no harm at all: the enforcement point refused the attack while the instrument
  measuring it reported the attack inert. Harm is now counted by effect. The
  published comparison figures are unchanged — that attack set never reaches the
  blind spot — and are pinned by
  `test_correcting_the_harm_counter_did_not_move_the_published_figures`.
- Added control-contract requirement `XC-5`.

### Alignment, results, and the paper

- `scripts/generate_results.py` now emits oversight, second-domain, and corpus
  figures, four new verdicts, and four new limits, so the new claims cannot drift
  from the code any more than the old ones could.
- Rewrote `paper/extended-abstract.md` as a panel contribution rather than a
  technical report: an explicit position, the oversight argument, the
  generalization evidence, and three propositions. Body is ~1,580 words.
- Rewrote `paper/form-ready-abstract.md` for the four capped submission fields and
  restored the punctuation that earlier form-safety stripping had removed.
- Added four slides to the conference deck and their speaker notes.
- **Extended alignment testing to the READMEs**, which were simultaneously
  claiming 180, 187, and 149 deterministic tests, none of them current. The paper
  was protected from that drift and the front door was not.

### Conference readiness: the submission surface, guarded

The alignment tests covered the proceedings-style abstract, the deck and the
READMEs. They did not cover the file that is actually pasted into the UNU form,
or the script that routes the deck on stage. Both had drifted.

- **Fixed: three of the four submission fields were over the form's character
  cap.** `scripts/check_submission.py` counted `len(body)`; a browser submits a
  textarea with CRLF line endings, so every paragraph break costs two characters
  rather than one. Introduction was 1,505 against a cap of 1,500, Development 1
  was 3,901 against 3,900, and Development 2 was 3,911 against 3,900 — while the
  checker reported all four valid. The checker now counts as the form receives,
  reports `headroom`, and the abstract was trimmed to fit with room to spare.
- **Extended alignment testing to `paper/form-ready-abstract.md`**, the version
  reviewers actually receive. It restates the same results in different prose, so
  it has its own templates — including a spelled-out-number guard, because
  regenerating figures and grepping for `25` will never find `Twenty-five`.
- **Fixed: the deck's speaker script routed a nineteen-slide deck that no longer
  exists.** Four slides were added and the paths table was not updated, so the
  printed "full" run was 1–19 on a page that also said slide 20 must never be cut,
  and every shortened path ended the talk on the limits slide with the close
  dropped. Rewrote the four paths; all of them now end on the close.
- Added tests binding the script to the deck: the stated slide count, that every
  routed slide exists, that every path ends on the close, and that no path cuts a
  slide the same page says is never cut.
- **The v1.0.0-era PowerPoint is marked superseded.** It contains no oversight
  ceiling, no second domain and no adversary corpus — none of the three
  contributions this submission leads with — and `paper/SUBMISSION.md` was
  telling an accepted author to present from it. `docs/presentation/slides.html`
  is now named as the deck everywhere.
- Fixed a broken `docs/ASSURANCE.md` link in `evaluation/results/RESULTS.md`, at
  its generator; dated `docs/REVIEWER_ASSESSMENT.md` as a record of one review
  round rather than a status page; synchronised the quoted test count (394).

## Unreleased — reviewer-driven resilience and identity checks

- Added `fssaira resilience` with independent spawned-process races and four
  abrupt-exit recovery checkpoints on synthetic local SQLite data.
- Added source- and profile-fingerprinted supplemental evidence and CI checks.
- Bound replay receipts to the complete proposal digest in memory, SQL and Redis.
  Conflicting request reuse now denies with `REQUEST_ID_CONFLICT`; legacy receipts
  without a digest require reconciliation (`REPLAY_IDENTITY_UNVERIFIABLE`).
- Fixed the SQLite transaction lock remaining held when connection creation fails.
- Added explicit SQLite connection cleanup and strict profile string validation.
- Removed hardcoded student-support transitions from the replay-race harness.
- Corrected the unimplemented PostgreSQL serialization-retry claim.
- Updated the PowerPoint recovery evidence, source links and matching speaker guide.

Upgrade note: read `docs/RESILIENCE.md` before retrying historical operations.
The new `proposal_digest` receipt field is additive. The published v1.0.0 tag and
its result files are unchanged.

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses
semantic versioning.

## [1.0.0] — 2026-09-11

The release that makes the assurance argument survive contact with another
institution. `v0.5.0` could specify authority boundaries and test the attacks its
authors thought of; this release adds the means to check the combination nobody
imagined, to show that each control is load-bearing, and to confirm the
properties still hold after a component is replaced.

### Added — machine-checked assurance

- **Bounded model checker** (`fssaira.verification`). Enumerates a profile's
  entire declared authority space — operations, transitions, approval variants,
  resource versions, identity pairings — executes the real enforcement code
  against every configuration, and checks five invariants. The reference profile
  explores 240 configurations with zero violations, and the report states its own
  bounds. `fssaira verify`.
- **Portable conformance suite** (`fssaira.conformance`). Twenty-five behavioural
  checks run against whatever backends a deployment has configured, each citing
  the control-contract requirement it defends. `fssaira conformance`.
- **Ablation-derived authority coverage.** Each declared control is removed in
  turn and the harm measured. A control whose removal changes nothing is reported
  as decorative. 8 of 8 are load-bearing.
- **Utility baseline.** Benign-task completion and a false-denial rate are
  reported beside every containment figure, because a containment rate with no
  denominator is unfalsifiable.
- **Paper/repository alignment tests** (`tests/test_paper_alignment.py`). Every
  figure the extended abstract and the conference deck quote is generated by
  `scripts/generate_results.py` and checked against the prose. Drift fails the
  build.
- **Bounded concurrent replay harness** (`fssaira race-test`). Thirty-two callers
  race one approved request; the check passes only with one mutation, one intent,
  one outcome, and one receipt. The report states that this is not a distributed
  linearizability proof.

### Added — durability

- **Single-transaction execution** (`fssaira.atomic_execution`, `fssaira.sql_backend`).
  Where the register and the evidence ledger share a database, the mutation, the
  execution receipt, the intent record, and the outcome record commit in one
  transaction. The state in which a resource moved with no record of who moved it
  becomes unreachable rather than merely detectable. Runs on PostgreSQL in a
  deployment and on SQLite in CI, so the property is tested on every commit.
- **PostgreSQL backend** (`fssaira.postgres_backend`), with reviewable DDL and
  append-only grants: `fssaira db ddl --role <role>`.
- The outbox and reconciliation protocol remain for the case no transaction can
  cover — a side effect in a foreign system. The active durability guarantee is
  reported on `/health`.

### Added — bounded intelligence

- **Privilege invariance.** The action class of any proposal is read from a
  capability catalogue, never from the proposal. A compromised agent that labels
  a consequential operation "reversible" is reclassified, still routed to a named
  human, and the attempted downgrade is recorded as evidence.
- **Pluggable model backends** with Ollama as the default: `openai-compatible`
  (vLLM, llama.cpp, LM Studio, TGI), `deterministic` (offline and reproducible),
  and adversarial fixtures (`compromised`, `class-downgrading`, `null`) used by
  the evaluation.
- **Plugin registry** (`fssaira.plugins`) across seven ports, discovered by entry
  point, dotted path, or in-process registration. `fssaira plugins`.
- **Task router** that selects a model without widening authority, held to that
  by test.
- Call budgets, argument-level egress inspection, and stable denial codes.

### Added — platform

- **React operator console** (`console/`): deployment state and its own
  shortcomings, governance configuration, the three-step protocol including its
  denials, the evidence chain, and on-demand assurance runs.
- **Real authentication** (`fssaira.security`): bearer tokens by default, OIDC
  available, and the v0.5.0 header adapter now refused unless an authenticating
  proxy is explicitly declared.
- **Working unidirectional transport** (`fssaira.diode_transport`): a UDP sender
  with the read side shut down, a receiver that never transmits, per-frame hash
  and HMAC, redundancy in place of retransmission. Plus `assert_no_return_path`,
  which turns "there is no method to read back" into a check.
- **Interface inventory**, because a diode governs one link and the directional
  claim is worthless without the list of everything else. `fssaira diode inventory`.
- **Kafka consumer, dead-letter path, and evidence projector**; **Iceberg**
  archive tables; an independent **Spark evidence-chain verification job** that
  detects truncation as well as alteration.
- **Prometheus metrics** and optional OpenTelemetry tracing.
- Docker Compose now includes PostgreSQL, Ollama, and the console, with
  `--profile analytics` for MinIO, the Iceberg REST catalog, and Spark.

### Added — for people adopting it

- **Authority Boundary Worksheet** (`docs/worksheet/`): one capability through
  the seven fields in a browser, flagging the answers a reviewer would reject and
  emitting runnable configuration.
- **Adoption playbook** (`docs/ADOPTION.md`): a 30/60/90-day path with what to
  produce and what not to promise.
- **Procurement questionnaire** (`docs/PROCUREMENT.md`): the seven fields as
  supplier questions, with strong, weak, and missing answer patterns.
- **Conference deck and speaker script** (`docs/presentation/`).
- `fssaira init` scaffolds a domain with a profile, a contract, a failing test to
  replace, and a deliberately empty assurance file.
- `fssaira doctor` grades the deployment's own configuration by severity.

### Changed

- Control contract grown from 8 to 25 requirements, adding a `cross_cutting`
  domain for identity, key custody, independent verification, and the manual
  fallback. Tests now fail on a thin or unactionable failure response.
- Adversarial evaluation grown from 8 scenarios to 30, mapped to external risk
  taxonomies, plus 6 benign tasks and 8 ablations.
- `EvaluationReport` schema 1.0 → 2.0: containment, utility, and attribution are
  separate sections, each with its denominator.
- Egress and impact are now independent axes on a capability. A notification can
  be reversible and still leave the boundary.
- Import boundary reports what it did, carries a content hash inward, and exposes
  `trust()` as an administrative act.

### Fixed

- **The SQL evidence ledger was not enforcing its write credential.** Caught by
  the conformance suite during development, which is what it is for.
- **Four adversarial variants were being caught one check too early.** Because
  the approval signature covers the expiry, audience, and role fields, every
  attack that tampered with them returned `APPROVAL_SIGNATURE_INVALID` and the
  checks behind it were never exercised. The suite now uses authentically signed
  approvals pointed at the wrong proposal, executor, role, or time. Found by the
  bounded model checker.
- The ablation for the approval-role requirement had the same defect and was
  measuring the signature check rather than the role check.

### Security

- Development bearer tokens, the teaching approval key, and the default evidence
  credential are now reported as **blocking** findings rather than notes.
- A non-local model endpoint produces an explicit sovereignty warning; fallback
  to a rule-based stand-in can be refused with `FSSAI_MODEL_FALLBACK=deny`.
- Containers run read-only, non-root, with capabilities dropped; the low-side
  gateway has no route to the control plane.

## [0.5.0] — 2026-09-10

- Exact-action approval with HMAC-authenticated fields, canonical proposal
  digests, operation allowlists, and profiled state transitions.
- Idempotent execution with pending-outcome reconciliation.
- FastAPI control plane, Redis state, Kafka publication, Spark-to-Iceberg job.
- Application profiles, eight-scenario evaluation, 42 tests.

## [0.4.0] — 2026-09

- Five-domain reference implementation, control contract, attack and ablation
  suites.
