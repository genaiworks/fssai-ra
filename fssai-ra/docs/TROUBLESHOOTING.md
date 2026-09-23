# Troubleshooting

> **Documentation navigation:** [Documentation map](README.md) · [Start here](START_HERE.md) · [Glossary](GLOSSARY.md)
>
> **Recommended next:** Follow the [user guide](USER_GUIDE.md) for a walkthrough or the [research guide](RESEARCH_GUIDE.md) to record an experiment.

## First establish where you are

The repository root contains `.git/`, the main README, and a `fssai-ra/` subdirectory. The inner application directory contains `pyproject.toml`, `src/`, `profiles/`, and `scripts/`.

Root command: `make setup`. Application command: `fssaira verify profiles/student_support.yaml` after activation. Most missing-file errors come from mixing these locations.

| Symptom | Likely cause | What to do |
|---|---|---|
| `python: command not found` | System exposes only `python3` | Use `python3` to create the environment; then activate it |
| `make: command not found` | Make is not installed | Use the direct Python installation steps in [User guide](USER_GUIDE.md#3-install-the-python-tools) |
| `fssaira: command not found` | Wrong/unactivated environment | In APP use `.venv/bin/python -m fssaira.cli --help`; Windows: `.venv\Scripts\python.exe -m fssaira.cli --help` |
| `No module named fssaira` | Package not installed into that interpreter | In APP run `python -m pip install -e '.[dev,privacy,api]'` using the intended environment |
| Missing `profiles/...` or `contract/...` | Command was run from ROOT | Enter the inner `fssai-ra/` directory |
| Demo says output contains a prior database | It is protecting an earlier run | Use a new `--output work/demo-02`; retain the old evidence |
| Missing YAML/crypto/test package | Wrong or incomplete installation | Run `python -m pip check`; install the documented extras in the same environment |
| Missing Uvicorn when serving API | Development extras do not include the server runner | Install `python -m pip install -e '.[api]'` |
| API port already in use | Another local process owns it | Stop your earlier server or select another `--port` and update the console proxy |
| Console cannot reach API | API stopped or proxy points elsewhere | Start API on 8080; inspect terminal errors and [Console guide](../console/README.md) |
| Console token rejected | Teaching selector used against generated credentials | Use the credentials for that deployment; keep them out of issues and logs |
| `doctor` reports blockers or exits nonzero | Reference defaults or missing deployment controls | Read the findings; a working install can still be unqualified |
| New domain scaffold test fails | Placeholder attack test is intentionally failing | Replace it with a real forbidden-effect test; do not just delete the assertion |
| `packet-check` exits 2 without anchor | No independent expected digest was supplied | Obtain a retained trusted digest; do not derive trust from the packet itself |
| PostgreSQL/Kafka/Redis connection failure | Optional service not configured/running | Use [Platform](PLATFORM.md) or return to memory/SQLite examples |
| Result-drift check fails | Code, environment, or snapshot differs | Keep raw outputs and inspect the diff before regenerating evidence |
| Historical paper or manifest missing | That archive is not tracked in this checkout | Run `make test` for public checks; only `make manuscript-check` requires the private archive |
| Broad suite works locally but fails after cloning | Local ignored inputs mask missing distribution files | Inspect `git ls-files` and record required paper/input archives in the publication entry |

## Save a useful issue report

Include the full commit (`git rev-parse HEAD`), OS, Python version, working directory (ROOT or APP), exact command, complete error, whether the environment is fresh, and whether optional services are running. State the expected effect and actual state, not only that a refusal appeared.

Exclude credentials, tokens, real personal records, and private data. For security defects, follow [Security reporting](../../SECURITY.md).

## Reset without losing evidence

For demos, use a fresh output directory instead of overwriting databases. Stop local API/console processes with Ctrl+C. `make stack-down` stops the configured Compose stack; do not add volume-deletion options unless you intend to discard its data. `make clean` removes caches/build output, not the meaning of your research results.

If an execution reply was lost, inspect reconciliation before retrying. Local committed outcomes and remote uncertain outcomes are different cases; read [Operations](OPERATIONS.md) and the [developer guide](../DEVELOPER_GUIDE.md).
