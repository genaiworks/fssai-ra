# Trust by Construction — a reference architecture for governed agentic AI

**TBC v11 SDK:** [Engineering guide](docs/TBC_SDK.md). Persistent Passports, Task Contracts, capability envelopes, governed memory, population controls, labelled messages, exact release escrow and an authority-contracting Guardian are available in `fssaira.tbc`. Run `make tbc-test` and `make tbc-demo OUTPUT=/tmp/tbc-demo-new`. This is an opt-in local reference service with an HTTP adapter; deployment isolation remains a separate requirement.

<sub>Repository and Python package: `fssai-ra` / `fssaira`.</sub>

**2026-09-14 adversarial revision:** [Run the durable joined demo and inspect audit evidence](audit/QUICKSTART.md). Synthetic SQLite workflow, independent source confirmation, exact approval, release and appeal; no paid API or install required for this demo. Earlier component results do not establish deployment isolation.

[![Tests](https://github.com/genaiworks/fssai-ra/actions/workflows/tests.yml/badge.svg)](https://github.com/genaiworks/fssai-ra/actions/workflows/tests.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB.svg)](https://www.python.org/)
[![License Apache 2.0](https://img.shields.io/badge/license-Apache--2.0-0B7261.svg)](../LICENSE)
[![Release v1.0.0](https://img.shields.io/badge/release-v1.0.0-4C566A.svg)](https://github.com/genaiworks/fssai-ra/tree/v1.0.0)

> **A model may propose an action. It cannot manufacture the authority to execute it.**

A **sector-neutral, extensible, runnable security kernel** for specifying and
testing the authority and data boundaries of agentic AI. Education is one domain
pack, not the architecture's boundary: the repository also ships corporate
confidential-data and healthcare-record-access packs. It includes a
dependency-free teaching mode and
a distributed reference deployment built with FastAPI, PostgreSQL, Redis, Apache
Kafka, PySpark, Apache Iceberg, S3-compatible storage, a local model through
Ollama, and a React operator console. A low-side gateway and a working
unidirectional transport model the seam a certified one-way data diode occupies.

**Companion paper:** *Trust by Construction: A Cross-Sector Reference
Architecture for Governed Agentic AI* — extended abstract in
[`paper/extended-abstract.md`](paper/extended-abstract.md), prepared for the
**UNU Macau AI Conference 2026** (*AI × Education: AI for Learning, Learning for
AI*) and its UNU–Springer proceedings.

**Submission and presentation:** the form-safe paste fields are in
[`paper/form-ready-abstract.md`](paper/form-ready-abstract.md), validated by
`python scripts/check_submission.py` and checked against the generated figures by
`tests/test_paper_alignment.py`. The deck is
[`docs/presentation/slides.html`](docs/presentation/slides.html) with its
[timed script](docs/presentation/speaker-script.md). The PowerPoint under
`docs/` is a superseded v1.0.0-era deck, kept for provenance.

> **Bounded claim: testable containment in a declared environment.** The teaching
> profile demonstrates independent checks for specified failure paths. It is not a
> production deployment, a security certification, a hardware-isolation proof, or
> a claim that a single host can withstand its own administrator.

---

## Sixty seconds

```bash
git clone https://github.com/genaiworks/fssai-ra.git
cd fssai-ra
make setup                                        # invokes python3 and creates the venv
make demo                                         # guided walkthrough
make reviewer                                     # all assurance checks, one command

cd fssai-ra && source .venv/bin/activate          # optional: individual commands
pytest                                            # current suite; v1.0.0 had 187 deterministic tests
fssaira doctor                                    # what is this deployment, really?
fssaira verify   profiles/student_support.yaml    # bounded model check: 240 states, 0 violations
fssaira evaluate profiles/student_support.yaml    # adversarial + utility + ablation
fssaira conformance --backend sql                 # does it still hold on another backend?
fssaira race-test profiles/student_support.yaml   # 32 callers, 1 mutation, 1 receipt
fssaira resilience profiles/student_support.yaml  # process races and abrupt-exit recovery
fssaira oversight profiles/student_support.yaml --sweep   # how much review can you supply?
fssaira coverage                                  # is each contract requirement enforced, or just written down?
fssaira delegation                                # authority that travels: 10 chain risk classes, 3 architectures
fssaira assisted-review                           # what a review assistant does to the oversight argument
fssaira challenge                                 # the open adversary corpus, scored
fssaira profiles --verify                         # cross-domain authority and utility evidence
```

After installation, these checks need no network, model weights or GPU.
Execution time depends on the machine and worker count. A second institution can
reproduce the observations on a disconnected laptop.

## One kernel, multiple governed-data domains

[`docs/REFERENCE_ARCHITECTURE.md`](docs/REFERENCE_ARCHITECTURE.md) defines the
seven-plane cross-sector design pattern. [`docs/DOMAIN_PACKS.md`](docs/DOMAIN_PACKS.md)
explains its generalization model. Each pack combines an executable state-transition allowlist with purpose,
data classifications, prohibited uses, applicable obligations, separate
data/privacy/security owners, and a manual fallback. `fssaira profiles` validates
and inventories the shipped packs.

The healthcare pack governs record access and secondary-use authorization; it
explicitly excludes diagnosis, treatment, triage, prescribing, and clinical
record alteration. The corporate pack governs classification, internal use,
external release, revocation, and legal hold. Both are synthetic teaching
profiles—not compliance claims or production deployments.

## Current-source enhancements after v1.0.0

**Oversight is a finite resource, and now it is a measured one.** Every control
in `v1.0.0` routes a consequential action to a named human and then treats that
human as unlimited. Push a queue past a reviewer's attention and every mechanism
here still passes — digests bind, signatures verify, the chain is intact — while
the oversight it all funnels into becomes a signature service. A system can be
perfectly accountable and completely unreviewed.

So review now has a declared capacity, a deliberation floor, mandatory escalation
under load, and a published headroom figure. `fssaira oversight` computes what a
roster can genuinely sustain and runs a queue-pressure trial against it. On a
queue at five times declared capacity, 4 structurally valid but substantively
wrong actions execute without the control and 0 with it, at a reported cost of 32
deferrals to the manual fallback.

`--sweep` answers the obvious objection that three numbers were chosen to suit
the result: across 25 parameter combinations the control was load-bearing in 16
of the 20 where harm was possible, harm reached zero in 16, and it never
increased harm anywhere. The sweep also caught **our own shipped defaults**
pairing a quota with a deliberation floor that contradicted it, throttling
reviewers who were reading every case; repairing the declaration drove that
false-positive cost to 0. **The reviewer degradation curve is a declared
parameter, not a measurement of any human** — see [`docs/ASSURANCE.md`](docs/ASSURANCE.md) §7.

Two artifacts make this usable without installing anything: the
[oversight calculator](docs/oversight/) works out an institution's ceiling in a
browser, offline, sending nothing anywhere — and a test runs its JavaScript
against the Python to prove the two agree — and [`docs/LAB.md`](docs/LAB.md) is a
two-hour lab in which participants remove a control and watch the harm
return.

**The reviewer now has a model too, and that breaks the control above.** The
oversight argument models an *unaided* reader. No institution whose queue exceeds
its roster will staff review that way, and it should not: in our trial assistance
completes **5x** the legitimate work of the unaided arm, which contains
everything by deferring 32 of 40 cases. But the deliberation floor must then
fall — and the floor was never measuring seconds. It was a proxy for *a second
mind independently reaching the same conclusion*, which survives only if the
assistant is independent of the proposer.

Same model family, same evidence packet, and it is not a second mind: it is the
proposer's reasoning arriving again in a reviewer's badge, wrong the same way on
exactly the cases that matter. Identical queues, identical lowered floor,
differing only in declared independence: **5 merit failures with a dependent
assistant, 1 with an independent one** — and in the harmful arm the chain is
intact, the reviewer is inside quota, every approval clears the floor, and no
refusal fires. There is no runtime signal to alert on, because at runtime the two
deployments are indistinguishable.

So `fssaira assisted-review` enforces it as a **configuration gate**: a
deployment that lowers its floor while declaring a dependent assistant does not
start. Independence is three things an institution can answer about itself and a
procurement process can require in writing — a different model, a different
evidence path, an adversarial posture. The independent arm reaches 1, not 0:
assistance multiplies attention without making it unbounded, so an institution
that buys an assistant has bought a larger ceiling to compute, not permission to
stop computing one.

**Authority now travels between agents.** Everything in `v1.0.0` governs one
agent under one grant — the right model for 2023, and not the shape being
deployed now that orchestrators spawn sub-agents and sub-agents call tool servers
they did not write. The rule extends in one sentence: *no principal may pass on
authority it does not itself hold, and no chain may end with more authority than
its root was granted.* `fssaira delegation` enforces nine invariants —
attenuation, rooted authority, depth, temporal containment, acyclicity,
provenance, non-delegable consequence, holder binding, beneficiary attenuation —
all nine load-bearing under ablation, with 768 enumerated chain shapes and 0
violations.

The finding is the middle arm. An architecture that validates *each hop against
its immediate delegator* is a real control and is what a careful engineer builds;
it contains **2 of 10** risk classes where verifying the chain contains **10**.
Local validation at every hop is not verifying the chain, and the gap is exactly
the defects nobody finds by reviewing one service. This work also caught its own
defect on first run: the checker admitted the confused deputy, because the chain
presented — authentic, rooted, attenuated, acyclic, in-depth — simply was not the
requester's. An authority object bound to nobody is a bearer token.

**The contract now measures whether it is enforced.** Seven fields per capability
is this project's central claim, and one field is an executable failure test. The
loader validated that every requirement *had* one and never that the test
*existed*: `fssaira coverage` found **18 of 28 requirements describing a failure
test and binding it to nothing.** Most did have tests; nothing connected them, so
deleting one would have removed a governance claim in silence. Coverage is now
three-way — machine-verified, organizationally attested by a named role on a
declared cadence, or unverified — reading **34, 3, 0** today. A binding naming a
test that does not exist fails the build, because otherwise the report would be a
file asserting its own correctness.

**One kernel, six independently reported domain packs.**
The framework now exercises student support, academic-record correction,
corporate-confidential data, and healthcare-record access through the same
verifier and evaluator: 55,440 bounded configurations, 180/180 hostile scenarios
contained, 58/58 benign tasks completed, and zero unauthorized mutations. These
are synthetic executable specifications, not evidence of sector compliance,
privacy, fairness, clinical safety, or production readiness.

The first transfer remains important because it found a defect.
[`profiles/academic_record_correction.yaml`](profiles/academic_record_correction.yaml)
was added through the documented extension path and carries its own evidence: the
identical suite holds with no library change — 4,800 configurations, 0 violations,
30/30 contained, 9/9 benign, 26 conformance checks. It failed on its first run and
the defect was real: a declared approval role on a routine transition was silently
unenforced. One domain could not reach it; two did immediately.

**An adversary who is not the author.** [`challenges/`](challenges/) is an open
corpus of 10 entries — attacks, controls reached before harm lands, and one
negative control of ordinary legitimate work that must succeed. An attack is
seven fields of YAML, scored against all three architecture arms and attributed
to whoever contributed it. No student record, deployment detail, or vendor name
is needed, and no contributor code runs. `fssaira challenge` prints how many
attacks came from outside this project — **currently 0**, stated in the output
rather than buried in a limitation.

Plus: independent-process races and abrupt-exit recovery on SQLite, full
proposal-digest binding for replay receipts, strict profile validation, and
source-fingerprinted supplemental evidence with a CI reproduction check.

See [resilience and upgrade guidance](docs/RESILIENCE.md). Existing digest-less
receipts require reconciliation before automated replay. These additions are
on the current branch, not in the immutable `v1.0.0` tag. Baseline paper results
remain release-specific; the new evidence is published separately.

## What is new in v1.0.0

Release `v0.5.0` could specify authority boundaries and test the attacks its
authors thought of. This release adds the three things that make the assurance
argument survive contact with another institution.

| | Question it answers | Result |
|---|---|---|
| **Bounded model checking** | What about the combination nobody imagined? | 240 configurations, 5 invariants, 0 violations |
| **Ablation-measured coverage** | Is each control load-bearing, or decorative? | 8 of 8 controls restored their harm |
| **Portable conformance** | Does it still hold after you replace a component? | 26 checks, 2 independent backend profiles |
| **Concurrent replay race** | Can simultaneous retries duplicate an approved action? | 32 callers, 1 mutation, 1 receipt |

And on current source, three questions `v1.0.0` could not answer at all:

| | Question it answers | Result |
|---|---|---|
| **Oversight capacity** | How much review can this institution actually supply? | 11 reviewers sustain 2,640 actions/day; 4 → 0 merit failures under load |
| **A second domain** | Does the method work where it was not designed? | 4,800 states, 0 violations, no library change — and it found a real defect |
| **Cross-sector domain packs** | Does one kernel support distinct governed-data workflows? | 6 packs; 55,440 states; 180/180 hostile contained; 58/58 benign; 0 unauthorized mutations |
| **Open adversary corpus** | Is the adversary ever someone other than the author? | 10 entries across 3 arms; 0 contributed externally, and we say so |

Plus: **single-transaction execution** on PostgreSQL, which removes — rather than
merely detects — the one failure mode the previous release could only document;
**privilege invariance**, so a model cannot declare its own review level; real
**authentication** replacing spoofable headers; a **React console**; and a
**utility baseline** reported beside every containment figure.

See [`CHANGELOG.md`](CHANGELOG.md).

## The pipeline

```
 external sources / signed updates
              │
   ┌──────────▼───────────┐   validate type·size·schema·signature,
   │  1. IMPORT BOUNDARY   │   strip active content, protocol break
   │   (one-way diode)     │   →  NO ordinary path back out
   └──────────┬───────────┘
              │  inward only
   ┌──────────▼───────────┐   durable, ordered, replayable
   │  2. EVENT TRANSPORT   │   (Kafka: offsets, hash, trace)
   └──────────┬───────────┘
   ┌──────────▼───────────┐   clean/validate (Spark) + versioned
   │  3. REPRODUCIBLE DATA │   snapshots + rollback
   │   (Spark + Iceberg)   │   (Iceberg: manifests, time travel)
   └──────────┬───────────┘
   ┌──────────▼───────────┐   local model (Ollama) + least-privilege
   │ 4. BOUNDED INTELLIGENCE│  agents; retrieved text is DATA;
   │                       │   action class from the CATALOGUE
   └──────────┬───────────┘
   ┌──────────▼───────────┐   policy verifies the ACTUAL operation
   │ 5. ACCOUNTABLE ACTION │   (not the model's story); consequential
   │  policy + human + log │   needs a named human; append-only,
   └──────────────────────┘   hash-chained evidence, one transaction
```

## The control contract

The original contribution. For each consequential capability, seven fields:
**protected asset, permitted operation, enforcement point, accountable owner,
failure test, evidence artifact, failure response.** Twenty-five requirements
live in [`contract/*.yaml`](contract/) as machine-readable YAML, so the contract
doubles as a conformance checklist — and `pytest` fails if any field is empty.

Not a documentation convention. A **diagnostic**: a capability whose seven fields
cannot be filled is a capability nobody is ready to automate. It also works
unmodified as an RFP section.

```bash
fssaira contract --output contract.json     # the whole contract, human or machine readable
```

## Run the reference deployment

```bash
python scripts/bootstrap_dev_env.py
docker compose --env-file deploy/.env -f deploy/compose.yaml up -d          # core stack
docker compose --env-file deploy/.env -f deploy/compose.yaml --profile model up -d   # + Ollama
python scripts/smoke_stack.py
```

| Service | Where | What it is |
|---|---|---|
| Operator console | `http://localhost:8088` | React; deployment state, governance, actions, evidence, assurance |
| Control API | `http://localhost:8080/docs` | The only way to change a governed resource |
| Import gateway | `http://localhost:8081` | Low-side, inward only, no read-back route |

Add `--profile analytics` for MinIO, the Iceberg REST catalog, and Spark. See
[`docs/PLATFORM.md`](docs/PLATFORM.md).

## Extend it

Everything is a port with at least one reference adapter, discovered through
entry points, a dotted path, or in-process registration.

```bash
fssaira plugins                     # every backend this process can see
fssaira model list                  # ollama (default) · openai-compatible · deterministic · …
fssaira init my-domain              # scaffold a profile, a contract, and a failing test
```

```toml
# your own package — no fork required
[project.entry-points."fssaira.models"]
my-institution = "mypkg.models:InstitutionModel"
```

A replacement is acceptable when the **same conformance suite still passes**
against it — not because it inherits from a blessed base class.

```bash
fssaira conformance --backend sql --output conformance.json
```

The scaffold ships an **empty** assurance file on purpose. A new domain inherits
the structure and none of the evidence; borrowing another domain's results is how
a method decays into a vocabulary. Start at [`docs/EXTENDING.md`](docs/EXTENDING.md).

## How each failure is contained

| Adversarial case | Independent control | Where |
|---|---|---|
| Prompt injection in a retrieved document | markers stripped; retrieved text stays untrusted; egress denied; the inward channel exposes no outward method | `injection_specimen_stripped_at_import` |
| A fully compromised model | least-privilege grant plus default-deny policy; every hostile proposal denied | `compromised_model_against_least_privilege` |
| A model that understates its own action class | class re-derived from the capability catalogue; downgrade recorded | `model_declares_its_own_action_class` |
| Exfiltration hidden in a tool argument | argument inspection on non-egress tools | `exfiltration_hidden_in_arguments` |
| A proposal changed after review | canonical digest binding; zero mutations | `changed_target_after_approval` |
| A genuine approval for another executor, proposal, role, or past its expiry | audience, digest, role, and expiry checked independently of the signature | 4 model-check variants |
| Poisoned source data | lineage plus snapshot rollback to the last approved state | `poisoned_data_rolled_back_to_approved_snapshot` |
| Insider record tampering | append-only hash chain; independent Spark re-verification catches truncation too | `insider_record_tampering_detected` |
| Interrupted outcome evidence | single transaction where possible; otherwise reported uncertain and reconciled once | `outcome_evidence_interruption_and_recovery` |
| A reviewer approving faster than anyone can read | declared review capacity, deliberation floor, escalation to a second reviewer — refused at issue, not flagged after | `test_load_control_contains_a_harm_no_other_control_can_see` |

`fssaira evaluate` runs all 30, plus 6 benign tasks and 8 ablations.

## Results

| Measure | Result | What it does and does not mean |
|---|---|---|
| Adversarial scenarios contained | `30/30` | containment of sampled risk classes, not coverage of a threat catalogue |
| Unauthorized mutations | `0` | across every denial scenario |
| Benign tasks completed | `6/6` | the denominator that makes a containment rate meaningful |
| False-denial rate | `0.0` | a system that denies everything scores perfectly on containment |
| Authority coverage | `1.0` | 8/8 controls restored their harm when removed |
| States explored | `240` | 5 invariants, 0 violations |
| Conformance checks | `25` | on 2 independent backend profiles |

Full table and its limits: [`evaluation/results/RESULTS.md`](evaluation/results/RESULTS.md).
Regenerate with `python scripts/generate_results.py`.

**Every figure the paper and the deck quote comes from that generator**, and
[`tests/test_paper_alignment.py`](tests/test_paper_alignment.py) fails the build
if prose and code disagree. Alignment is a test here, not a promise.

## Read this first

**Documentation home:** [`docs/README.md`](docs/README.md) explains what this
repository means, separates the policy, engineering, educator, reviewer, and
conference routes, and links every maintained and historical document.

**If you are reviewing this**

- [`docs/REVIEWERS.md`](docs/REVIEWERS.md) — **check every claim in ten minutes**, offline
- [`docs/ASSURANCE.md`](docs/ASSURANCE.md) — every public claim, its mechanism, its test, and its limit
- [`docs/RESPONSIBLE_AI.md`](docs/RESPONSIBLE_AI.md) — risk → mitigation → test → result, with the open rows marked open
- [`docs/GAPS.md`](docs/GAPS.md) — open evidence obligations and what would actually close them
- [`docs/IMPACT.md`](docs/IMPACT.md) — who benefits, labelled *demonstrated*, *reasoned*, *hypothesis*, or *out of scope*

**If you are using it**

- [`docs/START_HERE.md`](docs/START_HERE.md) — **understand the repository step by step**, then teach it back
- [`docs/SYSTEM_LITERACY.md`](docs/SYSTEM_LITERACY.md) — the five-part learning framework and assessment rubric
- [`docs/DEMO.md`](docs/DEMO.md) — the two-minute demonstration
- [`docs/ADOPTION.md`](docs/ADOPTION.md) — a 30/60/90-day path to a pilot
- [`docs/PROCUREMENT.md`](docs/PROCUREMENT.md) — the seven fields as supplier questions
- [`docs/EXTENDING.md`](docs/EXTENDING.md) — adding a domain without inheriting unsupported claims
- [`docs/PLATFORM.md`](docs/PLATFORM.md) — the distributed deployment
- [`docs/OPERATIONS.md`](docs/OPERATIONS.md) — failure and recovery procedures
- [`docs/SECURITY.md`](docs/SECURITY.md) · [`docs/DIODE_DEPLOYMENT.md`](docs/DIODE_DEPLOYMENT.md) — threat model, and where the directionality claim stops

## Security and limitations

Read [`docs/SECURITY.md`](docs/SECURITY.md) first. In short: this contains
categories of catastrophic failure by structure, but it is **not** proof against
a compromised host administrator, a subverted signing authority, or colluding
control owners. A hardware diode governs one link; every other path needs its own
control. Tamper-evidence detects, it does not prevent.

Report vulnerabilities per [`SECURITY.md`](SECURITY.md).

## Standards alignment (not certification)

NIST SP 800-207 · NIST AI 600-1 · OWASP Top 10 for LLM Applications · OWASP
Agentic Security · MITRE ATLAS · ISO/IEC 42001 · UNESCO AI Competency Framework ·
UN Global Digital Compact.

## Citation

> R. Srivastava, *Trust by Construction: A Cross-Sector Reference Architecture
> for Governed Agentic AI* (UNU Macau AI Conference 2026). Reference implementation:
> this repository, release `v1.0.0`.

Machine-readable metadata in [`CITATION.cff`](CITATION.cff).

## License

Apache-2.0 — see [`LICENSE`](../LICENSE). Contributions that preserve explicit
assurance boundaries are welcome; see [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Revised architecture evidence

The current Word revision is `paper/tbc-v13/TBC_v13_Frontier_Threat_Revision.docx`, built from the preserved `paper/tbc-v12/` source by [`scripts/build_paper_revision.py`](scripts/build_paper_revision.py) and bound to executed tests by `paper/tbc-v13/implementation.json`. Earlier revisions (`paper/tbc-v11/`, `paper/tbc-v12/`) are kept unchanged for provenance. [The 2026 threat model](docs/THREAT_MODEL_2026.md) reads the public agent-intrusion disclosure and the covert-objective and monitorability literature against these controls, with a machine-checked disposition for every stage in `audit/incident-map.json`. [Architecture review](docs/ARCHITECTURE_REVIEW.md) explains the 109-control register and remaining qualification gaps. Run `make all` after installing development dependencies to execute regression, capability-contract, paper-drift and result-reproduction checks. This remains a local reference implementation, not a qualified production deployment.
