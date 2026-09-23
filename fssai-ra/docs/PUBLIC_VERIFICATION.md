# Public verification and custom use cases

> **Documentation navigation:** [Documentation map](README.md) · [Start here](START_HERE.md) · [Glossary](GLOSSARY.md)
>
> **Recommended next:** [Extend the architecture](EXTENDING.md)

## Run the public verification environment

From the repository root, install and start Docker Engine or Docker Desktop with
Compose v2, then run:

```bash
make docker-setup
make docker-verify
```

The equivalent commands, including Windows PowerShell, are:

```bash
docker compose build research
docker compose run --rm research python scripts/reproduce.py --full --timeout 1800
```

On Linux, use the Make targets or export `LOCAL_UID=$(id -u)` and
`LOCAL_GID=$(id -g)` before Compose so output belongs to your host user. On Docker
Desktop, the default numeric user can write through its shared-folder mapping.
Allow several minutes for dependency downloads and tests. Build requires internet;
the research container runs with `network_mode: none`, including no provider calls.
Local loopback sockets remain available to transport tests. No model, GPU, paid
account, or private manuscript is needed.

The image pins Python and the Python dependency versions in
`docker/research-requirements.txt`. This is a version lock, not a hash-locked
software supply-chain archive. Debian package revisions and image tags can change.
For an archival run, retain the image ID, exported image, source commit and
bundle together. To inspect the image:

```bash
docker image inspect fssaira-research:local --format '{{.Id}}'
```

The checkout is mounted read/write so users can develop and retain evidence.
Only toolchain files enter the research image build; manuscripts, credentials,
and `.git` are not baked into image layers. This is a development environment,
not an isolation boundary against untrusted user-supplied Python tests.

## Read and preserve the result

Each run creates a new `fssai-ra/work/reproduction-<timestamp>-<id>/` containing:

- `report.json`: exact commands, exit statuses, elapsed time, commit, dirty-tree
  status, interpreter, dependency versions, configuration and source hashes;
- individual command logs, JSON evidence, test JUnit XML, architecture results;
- joined workflow viewer and receipts under `joined/`;
- SHA-256 hashes of all generated files other than the report itself.

A successful full run exits zero and has `passed: true` and `full: true` in
`report.json`. The runner stops on the first failed check and retains the evidence.
It never silently rewrites a committed result to make a comparison pass.

Verify a saved bundle from the repository root, replacing `BUNDLE` with its name:

```bash
docker compose run --rm research python scripts/verify_bundle.py work/BUNDLE
```

Hash and archive `report.json` independently as well: the checker detects changed,
missing and additional artifacts relative to that report, but cannot authenticate
a report an attacker rewrites. Keep the entire bundle and exact checkout, including
any uncommitted inputs. A commit ID alone does not describe a dirty checkout.

Two failures are intentional **only in the onboarding reproduction**: the default
`doctor` must reject pilot readiness, and the generated domain's placeholder
attack test must fail. Both are checked explicitly. All other steps must succeed.
The separate custom-use-case runner accepts no expected failures.

## What the full run verifies

| Evidence family | Executed source | Interpretation |
|---|---|---|
| Public runtime and adversarial behavior | `python -m pytest`, JUnit report | All collected public tests pass; private manuscript tests are explicitly excluded |
| Six profiles, authority, utility, oversight and delegation | `scripts/reproduce.py` CLI steps | Current synthetic inputs and bounded state spaces |
| Committed main result figures | `scripts/generate_results.py --check` | Fresh scientific figures equal `evaluation/results/v1.0.0-summary.json`; timing and historical test count are excluded |
| Education falsification and ablation figures | `scripts/conference_evidence.py --check` | Fresh figures equal `conference/evidence/summary.json` |
| Covert release-channel experiment | `scripts/measure_covert_channels.py --check` | Exact match against its committed synthetic experiment |
| Concurrent processes and crash recovery | `scripts/check_resilience.py` | Two process races and four abrupt-exit cases match the committed evidence |
| Architecture and SDK | `scripts/verify_architecture.py`, inventory checker | Bound capabilities execute and their inventory is consistent |
| Documentation | `scripts/check_public_docs.py` | Public file links and section anchors resolve without manuscripts |

A green run establishes these executable observations. It cannot validate every
sentence, citation, social claim, policy assumption, or deployment claim in a paper.
See the [UNU submission verification record](../../publications/unu-submission/README.md)
for the remaining manuscript-to-evidence identification step. Historical test counts
in a paper are snapshot counts and must not be replaced with today's collection size.

## Test your own use case

Open a container shell from the repository root:

```bash
make docker-shell
```

Inside it, the working directory is `/workspace/fssai-ra`:

```bash
python -m fssaira.cli init work/my-domain --domain-id my-domain --title 'My governed workflow'
python scripts/verify_usecase.py --profile work/my-domain/profile.yaml --contract work/my-domain --tests work/my-domain --output work/my-domain-first-check
```

The first run **must fail** at the generated placeholder test. Replace
`test_replace_me_with_the_attack_that_matters_in_your_domain` with a real misuse
case. Edit the profile and contract to describe your action, asset, roles, allowed
transitions, evidence, failure response, and responsible owner. Add benign cases
and assert actual effects, not just an authorization return value. The generated
contract's binding should reference your renamed test. Keep real personal data
and credentials out of examples.

Run again with a fresh output directory:

```bash
python scripts/verify_usecase.py --profile work/my-domain/profile.yaml --contract work/my-domain --tests work/my-domain --output work/my-domain-verified
python scripts/verify_bundle.py work/my-domain-verified
```

The runner validates your contract and profile, runs bounded verification,
adversarial/benign evaluation, memory and SQLite conformance, and your actual
pytest cases. Zero collected tests, a timeout, or any failure prevents a pass.
It records custom configuration and test hashes. Save those source files alongside
the bundle; hashes alone do not preserve the files. Inputs outside the repository
must be explicitly mounted before the container can access them.

The default evaluator checks generic exact-action scenarios. Add domain-specific
read/release, consent, revocation, delegation, retry, crash, appeal and false-denial
cases as relevant. For live tools, use a disposable target and measure its writes.
Follow the [extension guide](EXTENDING.md) for independent identities, transactional
state, durable evidence, and a staffed fallback. Passing a profile does not show
that arbitrary external tools enforce it.

## Run the actual service deployment

The root Compose file is the research environment. The separate
`deploy/compose.yaml` runs PostgreSQL, Redis, Kafka, API, gateway and console.
From the repository root:

```bash
make setup
cd fssai-ra
.venv/bin/python scripts/bootstrap_dev_env.py
docker compose --env-file deploy/.env -f deploy/compose.yaml up --build -d --wait
.venv/bin/python scripts/smoke_stack.py
docker compose --env-file deploy/.env -f deploy/compose.yaml down
```

On Windows use `.venv/Scripts/python.exe`. Bootstrap preserves an existing `.env`;
review its model and endpoint settings before use. A newly generated configuration
uses the deterministic model and randomized local credentials. Keep `.env` private.
`down` retains data volumes. Do not use `down -v` unless intentionally deleting data.

The default API is on localhost:8080, gateway:8081, console:8088. If those ports
are occupied, set `FSSAI_API_PORT`, `FSSAI_GATEWAY_PORT` and `FSSAI_CONSOLE_PORT`
in `deploy/.env` (for example 18080, 18081 and 18088), recreate the stack, and run:

```bash
.venv/bin/python scripts/smoke_stack.py --api-url http://127.0.0.1:18080 --gateway-url http://127.0.0.1:18081
```

The console proxies API requests through its own origin. See
[platform guide](PLATFORM.md) for deployment topology and optional analytics,
and [reviewer guide](REVIEWERS.md) for the local-model path. Optional
Ollama and analytics services require separate downloads and validation and are not
covered by the offline result. Logical networks on one Docker host do not establish
physical or administrative isolation.

## Troubleshooting and independent review

- Cannot connect to Docker: start the engine and check `docker info`.
- Permission denied writing evidence: check folder sharing or `LOCAL_UID`/`LOCAL_GID`.
- Existing output: choose a new directory; retaining prior runs is intentional.
- Drift: inspect the failing log and compare source/configuration with the cited
  snapshot before intentionally regenerating anything.
- Report a failure with commit, image ID, command and a sanitized failing log.
  Do not upload local credentials or institutional records.

CI runs the same full Docker verification from a public checkout and uploads its
bundle even on failure. A workflow added locally still needs a successful remote
run before it can be cited as CI evidence. Docker behavior follows its official
[build-context documentation](https://docs.docker.com/build/concepts/context/).
