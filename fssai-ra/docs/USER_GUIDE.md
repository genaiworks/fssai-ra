# User guide: from first run to your own experiment

> **Documentation navigation:** [Documentation map](README.md) · [Start here](START_HERE.md) · [Glossary](GLOSSARY.md)
>
> **Recommended next:** Use the [feature catalogue](FEATURES.md) to choose a workflow, then the [command reference](COMMANDS.md) to run it.

## Contents

1. [Understand the idea](#1-understand-the-idea)
2. [Follow one complete workflow](#2-follow-one-complete-workflow)
3. [Install the Python tools](#3-install-the-python-tools)
4. [Explore policies and experiments](#4-explore-policies-and-experiments)
5. [Try the SDK and integration examples](#5-try-the-sdk-and-integration-examples)
6. [Use the API and console](#6-use-the-api-and-console)
7. [Create your own domain](#7-create-your-own-domain)
8. [Know what you have demonstrated](#8-know-what-you-have-demonstrated)

## 1. Understand the idea

Imagine an agent helping correct a record. It can read information it is authorized to see and propose a correction. Its confidence is not permission. A trusted service checks the task, resource, role, current record version, independent evidence, and required approval before making the change. A separate release check decides which recipient may receive the result.

```text
Trusted policy + identity + task scope
                   ↓
Authorized context → model proposal → independent confirmation and approval
                                              ↓
                                  recheck → execute → evidence
                                              ↓
                                  recipient check → release
```

**Policy** states what is allowed. **Enforcement** prevents a forbidden effect. **Evidence** records what was checked and what happened. A log alone is not enforcement, and a valid log does not prove the underlying source is true.

The repository includes several implementations of parts of this idea. Start with the joined workflow, then explore individual experiments. The HTTP control plane, privacy profile, and SDK are separate entry points with separate configuration; running one does not enable all the others.

## 2. Follow one complete workflow

You need Python 3.10+ with SQLite. No dependencies or account are required for this example. From the repository root:

```bash
python3 --version
python3 -c "import sqlite3; print(sqlite3.sqlite_version)"
python3 fssai-ra/scripts/joined_demo.py --output fssai-ra/work/first-demo
```

On Windows, substitute `py -3` for `python3`. Open the resulting `viewer.html` by double-clicking it. A successful run prints `"runs": 5` and `"verified": true`.

The five runs are education, government benefits, and three source-confirmation ablation runs (control enabled, disabled, restored). Inspect `receipts.json` for machine-readable data and the `.db` files for persisted state. The HTML is a static view of those results.

### What to inspect

| Step in the transcript | Observation | What it teaches |
|---|---|---|
| Read for the wrong subject | Refusal without protected context | Identity alone does not authorize every record |
| Attempt an arbitrary tool | Refusal | The interface does not allow arbitrary network tools |
| Read → propose | Stored context and proposal identifiers | Proposing does not change the record |
| Instructor confirmation → registrar approval | Separate synthetic identities and stored objects | The model cannot invent its own approval |
| Execute with changed value | Refusal | Approval binds to an exact operation |
| Execute the approved proposal | Committed record and receipt | State and local evidence are checked together |
| Reopen and reconcile | Existing outcome is recovered | A lost local reply does not require a duplicate effect |
| Release as the intended recipient | Inspect actual sink bytes | Approval to act and permission to disclose are separate |
| Revoke, then release again | Refusal | Current authority is checked again |
| Appeal | Correction with retained history | Recovery is an accountable operation |

Compare the three ablation runs. The unsupported correction should execute only when the source-confirmation control is removed. That tests whether this control matters in the fixture.

**Repeat safely:** choose `work/second-demo` next time. Reusing a database is rejected. Keep your first receipts if you will compare runs. See the [joined workflow walkthrough](../audit/QUICKSTART.md) for the transaction model and exercises.

## 3. Install the Python tools

The rest of this guide uses the **inner application directory** containing `pyproject.toml`. Installation needs internet/package access unless you have prepared a compatible wheelhouse.

### macOS or Linux

From the repository root:

```bash
make setup
cd fssai-ra
source .venv/bin/activate
python -m pip check
fssaira --help
```

If Make is unavailable, enter the inner directory and use:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,privacy]'
```

### Windows PowerShell

From the repository root:

```powershell
cd fssai-ra
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,privacy]"
.\.venv\Scripts\python.exe -m fssaira.cli --help
.\.venv\Scripts\python.exe scripts/demo.py --fast
```

Activation is optional: use the full virtual-environment executable for every `python` command. In the commands below, replace `fssaira` with `.\.venv\Scripts\python.exe -m fssaira.cli` if the environment is not activated. Some process, TLS, and service checks are platform-dependent; record your OS when reporting results.

### Confirm the installation

```bash
python scripts/demo.py --fast
fssaira version
fssaira profiles
fssaira doctor
```

`doctor` may return a nonzero status for teaching defaults, missing isolation, or unconfigured services. Read its findings: it is a deployment diagnostic, not an installation-only test. The [troubleshooting guide](TROUBLESHOOTING.md) distinguishes these cases.

## 4. Explore policies and experiments

Run these commands from the inner directory with the virtual environment active:

```bash
fssaira validate-profile profiles/student_support.yaml
fssaira contract
fssaira verify profiles/student_support.yaml
fssaira evaluate profiles/student_support.yaml
fssaira conformance --backend memory
fssaira conformance --backend sql
```

Read a profile before changing it. Its transitions name allowed operations and reviewer roles. The contract adds the protected asset, enforcement point, owner, test, evidence, and failure response. `verify` explores a bounded declared state space; `evaluate` runs authored attacks, benign cases, and ablations; `conformance` checks a backend's observable behavior.

To explore another sector:

```bash
fssaira verify profiles/government_benefits.yaml
fssaira evaluate profiles/government_benefits.yaml
fssaira disclosure profiles/healthcare_record_access.yaml
```

Compare each result separately. Do not combine counts from different harnesses as though they were independent observations of one experiment.

For human oversight and delegation:

```bash
fssaira oversight profiles/student_support.yaml --sweep
fssaira assisted-review profiles/student_support.yaml
fssaira delegation
```

Oversight outputs use declared reviewer behavior. They are simulations, not observed human performance. The delegation experiment tests authority across a chain, including restrictions that must survive every hop. See [Features](FEATURES.md) for all remaining experiments.

## 5. Try the SDK and integration examples

Still in the inner directory:

```bash
python scripts/tbc_demo.py --output work/sdk-first-demo
python scripts/developer_security_demo.py
```

Use a new SDK output directory on every run. The SDK example covers tasks, context, governed memory, narrower child agents, labelled messages, exact effects, release escrow, and authority contraction. The developer example checks approved artifact bytes and remote-effect reconciliation using local fixtures.

Read [TBC SDK](TBC_SDK.md) before embedding these components. Trusted runtime objects, databases, and administrative credentials must remain outside model control. These examples do not install a sandbox.

## 6. Use the API and console

This is optional. The first workflow needs neither a server nor a browser development toolchain.

### Terminal 1: API

From the inner application directory with the virtual environment active:

```bash
python -m pip install -e '.[api]'
fssaira serve --host 127.0.0.1 --port 8080
```

Open `http://127.0.0.1:8080/docs` for interactive API documentation and `/health` for service health. The teaching configuration uses synthetic identities and local state. Read [Platform](PLATFORM.md) before changing authentication or storage.

### Terminal 2: console

Install Node.js/npm separately; the repository CI uses Node 22. From the inner application directory:

```bash
cd console
npm ci
npm run dev
```

Open the address printed by Vite, normally `http://localhost:5173`. The development proxy routes `/api` to the API on port 8080. Walk through Deployment → Governance → Actions → Evidence → Assurance. The Intelligence tab shows proposals; it does not give a model execution authority.

The identity selector uses published teaching tokens. A distributed configuration generated by `bootstrap_dev_env.py` uses different tokens; use that configuration's credentials. See the [console guide](../console/README.md). Stop both servers with Ctrl+C.

### Optional distributed services

Use [Platform](PLATFORM.md) and [Operations](OPERATIONS.md) for Docker Compose, PostgreSQL, Redis, Kafka, Spark, Iceberg, and object storage. These add service dependencies and persistent state. They are not prerequisites for learning the architecture and do not automatically establish isolation or durability for every backend.

## 7. Create your own domain

From the inner directory:

```bash
fssaira init work/my-domain --domain-id my-domain --title "My governed workflow"
fssaira validate-profile work/my-domain/profile.yaml
fssaira validate-contract work/my-domain
fssaira verify work/my-domain/profile.yaml
fssaira evaluate work/my-domain/profile.yaml
python -m pytest work/my-domain
```

The scaffold intentionally includes a failing placeholder adversarial test and an empty assurance document. This is expected: replace the placeholder with your domain's real failure case before claiming a result.

1. Replace the actors, purpose, resource, transitions, and accountable roles.
2. Specify data scope, retention, residency, incident response, and manual fallback.
3. Fill the seven fields for every consequential capability.
4. Write a forbidden-effect test and a legitimate-success test.
5. Remove and restore the relevant control to test whether it changes the outcome.
6. Bind requirements to executable checks and run `fssaira coverage --dir work/my-domain`.
7. Populate the generated `ASSURANCE.md` with your own results and limits.

Keep experiments in `work/`; move a completed contribution into the maintained profile/test structure through review. Follow [Extending](EXTENDING.md) for adapter contracts.

## 8. Know what you have demonstrated

After this guide, you should be able to explain which component may propose, which may authorize, which may execute, which may release, and where the receipts are stored. You should also be able to show a forbidden action failing and a legitimate action succeeding.

You have exercised synthetic local controls. You have not measured educational benefit, fairness, live-model detection accuracy, institutional review quality, or deployment-wide security. For a paper, record the exact experiment and its boundary using the [research guide](RESEARCH_GUIDE.md). For a pilot, use [Adoption](ADOPTION.md) and [Pilot protocol](PILOT_PROTOCOL.md).
