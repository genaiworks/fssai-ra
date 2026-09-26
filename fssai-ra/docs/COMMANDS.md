# Command reference

> **Documentation navigation:** [Documentation map](README.md) · [Start here](START_HERE.md) · [Glossary](GLOSSARY.md)
>
> **Recommended next:** Follow the [user guide](USER_GUIDE.md) for a walkthrough or the [research guide](RESEARCH_GUIDE.md) to record an experiment.

## Directory conventions

**ROOT** means the directory with the outer README and `.git/`. **APP** means its `fssai-ra/` subdirectory containing `pyproject.toml`. Run individual commands below in APP after activating `.venv`. Use `python -m fssaira.cli` instead of `fssaira` if the executable is not on PATH.

```bash
# From ROOT
make setup
cd fssai-ra
source .venv/bin/activate
# Now in APP
fssaira --help
```

Most experiments print a report and support `--output PATH` for JSON. Consult each command's `--help`; this option is not universal. Make output directories yourself before passing a file path.

## Every top-level CLI command

| Command (from APP) | Purpose / required inputs |
|---|---|
| `fssaira version` | Package version; pair with a Git commit when citing |
| `fssaira doctor` | Active backend/configuration findings; readiness failures may exit nonzero |
| `fssaira validate-profile profiles/student_support.yaml` | Validate a profile |
| `fssaira validate-contract contract` | Validate a contract directory |
| `fssaira contract` | Display the seven-field control contract |
| `fssaira profiles` | List domain profiles; add `--verify` for bounded verification |
| `fssaira evaluate profiles/student_support.yaml` | Adversarial, benign, and ablation experiments |
| `fssaira verify profiles/student_support.yaml` | Bounded state-space verification |
| `fssaira conformance --backend memory` | Port contracts; use `sql` for the SQL backend |
| `fssaira race-test profiles/student_support.yaml` | Concurrent caller experiment; `--callers` controls callers |
| `fssaira resilience profiles/student_support.yaml` | Process race and recovery checks; callers 2–32 |
| `fssaira oversight profiles/student_support.yaml --sweep` | Review-capacity simulation and parameter sweep |
| `fssaira assisted-review profiles/student_support.yaml` | Review-assistant simulation |
| `fssaira delegation` | Whole-chain authority experiment; optional `--max-depth` |
| `fssaira coverage` | Contract binding coverage; optional `--dir` |
| `fssaira challenge --dir challenges` | Score the adversary corpus |
| `fssaira disclosure profiles/healthcare_record_access.yaml` | Governed-read and release experiments |
| `fssaira threats` | Threat catalogue with evidence bindings |
| `fssaira thesis` | Specified mediation falsifiers across profiles |
| `fssaira pilot-check PATH` | Validate a pilot-protocol JSON record |
| `fssaira plugins` | Backend registry; optional `--port` filter |
| `fssaira model list` | Discover model backends |
| `fssaira model health NAME` | Probe a configured backend; may contact a service |
| `fssaira model propose "TASK" --name NAME` | Obtain proposals without execution; choose a configured backend |
| `fssaira mcp scan --config gate.yaml` | Show what each MCP server tells a model; flags instruction-like text; exits 1 if flagged ([guide](MCP_GATE.md)) |
| `fssaira mcp lock --config gate.yaml --lock mcp.lock.json --approved-by NAME` | Record a named approval of the exact current tool listing |
| `fssaira mcp serve --config gate.yaml --lock mcp.lock.json --receipts PATH` | Run the gate as an MCP server on stdio for a host to launch |
| `fssaira mcp approvals --config gate.yaml` | List calls held for exact-action approval, with their arguments |
| `fssaira mcp approve ID --config gate.yaml --by NAME` | Approve one held call; `deny` refuses it |
| `fssaira framework plan USE_CASE.yaml` | Target level, applicable controls, first sprint and stop conditions for one use case ([guide](ADOPT.md)) |
| `fssaira mcp verify PATH` | Verify a gate receipt log's hash chain |
| `fssaira evidence verify PATH` | Verify exported evidence JSON |
| `fssaira packet-check PATH --expected-sha256 DIGEST` | Inspect a private decision packet against an independent digest |
| `fssaira diode inventory` | Inspect one-way transport declarations |
| `fssaira diode send --help` | Inspect sender flags before supplying host/key/input |
| `fssaira diode receive --help` | Inspect receive-only listener flags before starting it |
| `fssaira db ddl` | Print schema for review; does not apply it |
| `fssaira db init --database-url URL` | Create schema on the configured database; mutates that database |
| `fssaira serve --host 127.0.0.1 --port 8080` | Run control API; requires the `api` extra |
| `fssaira serve --gateway --port 8081` | Run the import gateway |
| `fssaira init work/my-domain --domain-id my-domain` | Generate a domain scaffold; includes a deliberately failing placeholder test |
| `fssaira conference --help` | Historical namespace for education and adversarial experiments |

`PATH`, `DIGEST`, `NAME`, and `URL` above are placeholders, not literal runnable values. Supply your own artifact, independently recorded digest, configured backend name, or database address. Keep credentials out of publication bundles.

### Education/adversarial subcommands

The `conference` namespace is retained for compatibility. These tools can support teaching or research at any venue.

| Command | Output / effect |
|---|---|
| `fssaira conference pack-check conference/education/governed-learning-pack.yaml` | Check the pack against the kernel floor |
| `fssaira conference falsify` | All falsifiers; append an ID such as `F19` to select one |
| `fssaira conference ablation F10` | Compare enabled / disabled / restored control |
| `fssaira conference trace --model honest` | Trace a governed request; `malicious` is another offline fixture |
| `fssaira conference adaptive --budget 200 --seed 20260921 --split held-out` | Adaptive search with declared budget and split |
| `fssaira conference stateful --sequences 120` | Stateful authority sequences |
| `fssaira conference lab --port 8765` | Local educational browser server |

`--live` on adaptive search and `--model ollama` on traces opt into a configured model service. Do not describe those runs as offline fixture-only runs.

## Make targets

| From | Target | Effect |
|---|---|---|
| ROOT | `make help` | List root targets |
| ROOT | `make setup` | Create environment and install development/privacy dependencies |
| ROOT | `make demo` | Guided component demonstration |
| ROOT | `make reproduce` | Run public workflows; save commands, results, environment and hashes in a unique `work/` bundle |
| ROOT | `make manuscript-check` | Explicit private manuscript validation; requires local archives |
| ROOT | `make docs-check` | Check maintained documentation, navigation, and software citation |
| ROOT | `make test`, `make lint` | Full local suite / Python lint |
| ROOT | `make reviewer`, `make check`, `make all` | Public checks; private paper inputs are not needed |
| ROOT | `make falsify F=F19`, `make ablation F=F10` | Forward selected adversarial experiments |
| ROOT | `make results` | **Regenerate** tracked evaluation and education evidence |
| APP | `make help` | Full application target list |
| APP | `make developer-demo` | Local artifact-integrity and remote-recovery example |
| APP | `make joined-test`, `make security-review` | Focused joined-path / integration security regressions |
| APP | `make tbc-demo OUTPUT=work/sdk-new` | SDK demo in a new directory |
| APP | `make tbc-test`, `make architecture-check` | Public SDK inventory or architecture contracts |
| APP | `make qualify` | Generate host qualification findings under `audit/qualification/` |
| APP | `make api`, `make gateway`, `make console` | Long-running local services |
| APP | `make stack-up`, `make stack-down` | Start/stop Docker reference services |
| APP | `make openapi` | Regenerate the tracked API schema |
| APP | `make conference`, `make results`, `make figures` | Regenerate tracked evidence or presentation assets |
| APP | `make conference-check` | Compare education evidence with a fresh run |
| APP | `make clean` | Remove Python caches and build products |

For APP targets, activate the environment first or pass `PYTHON=.venv/bin/python`. Existing target names remain available; the education demo is still named `conference-demo`.

## Validation tiers

### 1. Documentation and first-run checks

From ROOT: `make docs-check` and `make reproduce`. From APP:

```bash
python scripts/joined_demo.py --output work/validation-demo
python -m pytest tests/test_joined_workflow.py tests/test_joined_legacy_regressions.py
```

Use a new output directory. These checks do not require a manuscript archive.

### 2. Focused component checks

From APP:

```bash
python -m pytest tests/test_profiles_and_evaluation.py tests/test_domain_packs.py
python -m pytest tests/test_tbc_sdk.py tests/test_exact_action.py
python -m pytest tests/test_disclosure.py tests/test_disclosure_tokens_and_concurrency.py
python -m pytest tests/test_qualified_transport.py tests/test_remote_effects.py
```

Choose tests for the component you actually use. TLS and privacy checks require cryptography support, included in the recommended `[dev,privacy,api]` installation.

### 3. Whole local checkout and research snapshots

From APP:

```bash
python -m pytest
python -m ruff check src tests scripts jobs adapters
python scripts/generate_results.py --check
```

The default suite explicitly excludes private manuscript checks. It still runs
public runtime, result-snapshot, deck, README, and documentation checks. The test
summary states this scope and reports deselected manuscript cases. Fully private
modules are not collected, so they cannot fail import before runtime tests start.

To validate the historical archive deliberately, run `make manuscript-check`
from ROOT or APP. This uses `--include-manuscripts -m manuscript` and fails with
a missing-input list when local-only artifacts are absent. It never reports
missing private evidence as a passing manuscript check.

### 4. Deployment checks

Integration services, real credentials, host isolation, and independent evidence custody require a separate configured environment. Use [Platform](PLATFORM.md), [Operations](OPERATIONS.md), and [Gaps](GAPS.md). A local unit-test pass is not this tier.

## Extras and prerequisites

| Install in APP | Enables |
|---|---|
| `python -m pip install -e .` | Core Python/CLI with YAML |
| `python -m pip install -e '.[dev,privacy,api]'` | Tests, lint, encryption support, and the local API server |
| `python -m pip install -e '.[api]'` | FastAPI and Uvicorn serving |
| `python -m pip install -e '.[postgres]'` | PostgreSQL adapter; server remains separate |
| `python -m pip install -e '.[redis]'` | Redis client; server remains separate |
| `python -m pip install -e '.[kafka]'` | Kafka client; broker remains separate |
| `python -m pip install -e '.[iceberg]'` | Iceberg/Arrow data support |
| `python -m pip install -e '.[spark]'` | PySpark; verify the Java/runtime requirements of your installed version |
| `python -m pip install -e '.[auth,telemetry]'` | Token verification and OpenTelemetry integrations |
| `python -m pip install -e '.[platform]'` | Reference service dependencies |

See `pyproject.toml` for authoritative dependency declarations. The `all` extra does not mean that external services, deployment qualification, or every optional package is provisioned.
