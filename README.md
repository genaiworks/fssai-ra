# Trust by Construction — consolidated framework

**Trust by Construction (TBC)** is the single framework for governing AI agents and swarms in this repository. **FSSAI-RA** is its reference implementation. The reviewed V27 core and the full V28 extensions are consolidated into **34 canonical patterns and 59 operational controls**, maintained together in one executable catalogue.

**Start with the [consolidated framework](fssai-ra/docs/FRAMEWORK.md).** Read its [P1–P34 pattern catalogue](fssai-ra/docs/framework/PATTERNS.md), [operational controls](fssai-ra/docs/framework/CONTROLS.md), and [consolidation record](publications/CONSOLIDATION.md). Manuscript versions are historical publication views of this framework, not competing definitions.

> A model may propose an action. It cannot manufacture the authority to execute it.
> A model may request data. Independent controls decide what it may see and release.

The repository supports experiments, teaching, integration work, and multiple research papers across sectors. It includes six synthetic domain profiles covering education, corporate data, healthcare, consumer finance, and government benefits. Publication packages are supporting records; no conference defines the scope of the platform.

[Learn the implementation](fssai-ra/docs/START_HERE.md) · [Complete user guide](fssai-ra/docs/USER_GUIDE.md) · [All features](fssai-ra/docs/FEATURES.md) · [Documentation index](fssai-ra/docs/README.md)

**Technical builders:** [Full data-pipeline walkthrough](fssai-ra/docs/PIPELINE_WALKTHROUGH.md) — sample records, cryptography, PostgreSQL rows, Redis keys, Kafka/Spark/Iceberg, runnable lab and verification.

## What you can do

| Goal | What to use |
|---|---|
| See an authorized action and a rejected attack | Offline joined workflow with a browser evidence viewer |
| Define who may do what | Domain profiles, seven-field control contracts, exact-action approvals |
| Control sensitive information | Purpose-bound disclosure, consent, inherited labels, recipient and release checks |
| Gate the MCP tools your agent already uses | [`fssaira mcp`](fssai-ra/docs/MCP_GATE.md): named tool approval, rug-pull quarantine, injection-to-privileged-tool blocking, digest-only receipts |
| Govern cooperating agents | Delegation checks; SDK task, memory, population, messaging, and Guardian controls |
| Test a security claim | Adversarial scenarios, ablations, bounded verification, conformance, race and recovery checks |
| Explore human oversight | Capacity and assisted-review simulations with explicit assumptions |
| Integrate services | Python modules, FastAPI interfaces, storage/event adapters, React operator console |
| Write another paper | [Publication workflow and citation guidance](publications/README.md) with versioned evidence |

These are reference implementations and synthetic experiments. Passing a test does not establish production security, policy correctness, human-review effectiveness, or physical isolation. Each feature has its own [scope and evidence limits](fssai-ra/docs/FEATURES.md).

## First run: no installation or model account

Requirements: Git and Python 3.10 or later with SQLite. Clone once, then run:

```bash
git clone https://github.com/genaiworks/fssai-ra.git
cd fssai-ra
python3 fssai-ra/scripts/joined_demo.py --output fssai-ra/work/first-demo
```

Open `fssai-ra/work/first-demo/viewer.html` in your browser. Expect a terminal summary with `"runs": 5` and `"verified": true`. The viewer contains the actual local records, denials, released bytes, and evidence receipts. All people, records, and model decisions are synthetic.

**Running again?** Change `first-demo` to a new directory name. The demo refuses to reuse a database. Follow the [walkthrough](fssai-ra/docs/USER_GUIDE.md#2-follow-one-complete-workflow) to understand each result.

## Install the research and development tools

Run these from the **repository root**, the directory containing this README:

```bash
make setup
make demo
make reproduce                                   # saves logs and evidence in a fresh work/ directory
make docs-check
```

Setup downloads Python dependencies and creates `fssai-ra/.venv`. The default demonstrations need no paid API, GPU, Docker, or downloaded model. For Windows, use the [PowerShell setup](fssai-ra/docs/USER_GUIDE.md#3-install-the-python-tools).

To run individual CLI commands, enter the inner application directory:

```bash
cd fssai-ra
source .venv/bin/activate
fssaira --help
fssaira profiles
fssaira verify profiles/student_support.yaml
fssaira evaluate profiles/student_support.yaml
fssaira conformance --backend sql
```

The repository folder is named `fssai-ra`; it also contains an application folder named `fssai-ra`. The Python import and command are spelled **`fssaira`**. See the [command reference](fssai-ra/docs/COMMANDS.md) for working directories, outputs, and optional dependencies.

## Verify in Docker or bring your own use case

```bash
make docker-setup
make docker-verify
```

Requires a running Docker Engine and Compose v2. The first build downloads pinned
Python dependencies; verification then runs without network access and saves a
fresh evidence bundle under `fssai-ra/work/`. See [Public verification and custom
use cases](fssai-ra/docs/PUBLIC_VERIFICATION.md) for outputs, integrity checks,
Windows commands, the live service stack, and testing your own profile and tools.
The [UNU submission record](publications/unu-submission/README.md) distinguishes
executable evidence from the submitted manuscript identification still needed.

## Choose a reading path

| You are here to… | Read in this order |
|---|---|
| Understand the project for the first time | [User guide](fssai-ra/docs/USER_GUIDE.md) → [Features](fssai-ra/docs/FEATURES.md) → [Glossary](fssai-ra/docs/GLOSSARY.md) |
| Build an integration | [Developer guide](fssai-ra/DEVELOPER_GUIDE.md) → [Architecture](fssai-ra/docs/REFERENCE_ARCHITECTURE.md) → [Extension guide](fssai-ra/docs/EXTENDING.md) |
| Reproduce or publish research | [Research guide](fssai-ra/docs/RESEARCH_GUIDE.md) → [Results](fssai-ra/evaluation/results/RESULTS.md) → [Publications](publications/README.md) |
| Govern or procure a system | [System literacy](fssai-ra/docs/SYSTEM_LITERACY.md) → [Procurement](fssai-ra/docs/PROCUREMENT.md) → [Adoption](fssai-ra/docs/ADOPTION.md) |
| Teach a workshop | [Lab](fssai-ra/docs/LAB.md) → [Worksheet](fssai-ra/docs/worksheet/index.html) → [Oversight calculator](fssai-ra/docs/oversight/index.html) |
| Evaluate a deployment | [Security](fssai-ra/docs/SECURITY.md) → [Operations](fssai-ra/docs/OPERATIONS.md) → [Evidence gaps](fssai-ra/docs/GAPS.md) |

## Repository layout

```text
README.md                   Project overview and first run
CITATION.cff                 Software citation metadata
publications/               Publication register and reusable paper template
security_systems/           Companion trustkernel package for coding-agent demonstrations
fssai-ra/
  src/fssaira/               Python implementation and CLI
  profiles/                 Domain policies and SDK example contracts
  contract/                 Control requirements and evidence bindings
  tests/                    Behavioral, adversarial, and artifact checks
  docs/                     Guides, reference material, browser learning tools
  scripts/                  Demonstrations, evaluations, verification utilities
  console/                  React operator interface
  deploy/                   Docker Compose and environment template
  adapters/, jobs/           Integration examples and data jobs
  evaluation/results/       Versioned experimental result snapshots
  challenges/, threats/     Adversary cases and threat catalogue
  conference/               Reusable education demonstrations; historical name
  paper/                    Local-only manuscripts and builds; ignored by Git
  audit/                    Historical run records and review evidence
  work/                     Ignored local outputs from your own experiments
```

The [repository map](fssai-ra/docs/REPOSITORY_MAP.md) explains how these pieces connect. Existing paths are retained to preserve code references and citations.

## Validation and evidence

Use `make reproduce` to run the beginner/research workflows and save an evidence bundle, `make docs-check` for links and navigation, `make test` for the public runtime suite, and `make lint` for Python linting. `make reviewer` and `make all` also work without private manuscripts. Historical paper validation is separate: `make manuscript-check` requires local-only archives and reports an error if they are absent. See [validation tiers](fssai-ra/docs/COMMANDS.md#validation-tiers).

Report results with the exact commit, command, configuration, environment, and raw output. Checked-in reports are snapshots of particular experiments, not a live guarantee about every configuration. The [research guide](fssai-ra/docs/RESEARCH_GUIDE.md) explains how to create a reproducible evidence bundle.

## Cite and contribute

Cite **the software snapshot you actually used**, using [CITATION.cff](CITATION.cff) and its full commit identifier. Cite individual papers separately when you use their arguments or findings. [Publication records](publications/README.md) provide a template and reproduction guidance for future papers; submission does not imply acceptance or publication.

See [Contributing](CONTRIBUTING.md), [Security reporting](SECURITY.md), and the [Apache-2.0 license](LICENSE). For setup problems, use [Troubleshooting](fssai-ra/docs/TROUBLESHOOTING.md).
