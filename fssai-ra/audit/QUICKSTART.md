# Reproduce the joined workflow

Use Python 3.10 or newer with SQLite. The new default joined demonstration uses only the Python standard library. It performs no installation, download, model call, network request or browser telemetry. All records, tokens and reviewers are synthetic. Run from `fssai-ra/` inside the repository (the package directory, not its parent).

```sh
python3 -c 'import sqlite3, json, hashlib; print(sqlite3.sqlite_version)'
PYTHONPATH=src python3 scripts/joined_demo.py --output audit/my-demo
PYTHONPATH=src python3 scripts/adaptive_attacks.py --output audit/my-attacks.json
```

Open `audit/my-demo/viewer.html` locally. It contains escaped request/response records, backend state, actual sink bytes and hash-chain receipts. This viewer sends nothing and does not fabricate animations. A repeat demo uses a fresh output directory so it cannot accidentally reuse approvals or mutate prior evidence.

For a single request against the teaching database:

```sh
printf '%s' '{"op":"read"}' | FSSAI_DEMO_TOKEN=demo-advisor PYTHONPATH=src python3 scripts/joined_request.py --database audit/manual.db
```

Role tokens are published synthetic fixtures, not secrets or production authentication. They are supplied outside the JSON proposal. Operational profiles are rejected. Never place institutional records or credentials here. The broader repository's HTTP service and privacy-vault profile are separate integrations, not implicitly protected by this demo.

For the complete original test suite, from the repository root run `make setup`, then `make test`. Setup downloads packages. The original README's development dependencies are separate from the dependency-free joined demo. `audit/requirements-tested.txt` pins the installed audit environment; its editable project line is omitted. It is an environment record, not a cross-platform lock. Python, SQLite, OS and package versions are in `audit/environment.json`. Prepare offline execution by copying the source and a compatible Python runtime; the joined demo needs no wheels. For the broader suite, download platform-compatible wheels under their licenses before disconnecting and install from that wheelhouse with `pip --no-index --find-links`.

## Five-minute walkthrough

1. Run the demo, open the viewer and read the mode label: scripted model, simulated people, real local database effects.
2. Find the wrong-student denial; the returned response contains no protected context.
3. Follow read -> propose -> instructor confirmation -> registrar approval. The rationale is synthetic and supplies no authority.
4. Compare the rejected changed request with the accepted execution. Find the committed record version, reconciliation response, and recipient's actual bytes.
5. Find revocation followed by a denied release. Compare enabled/disabled/restored source confirmation. The unsupported A correction only executes with the control removed; correction on appeal retains history.

## Technical walkthrough

`Workflow.dispatch` authenticates and parses duplicate-free JSON, begins `BEGIN IMMEDIATE`, calls the typed handler, and commits only on success. `grant` traverses all ancestors and consumes each applicable budget in the same transaction. Context objects bind subject, actor, grant, purpose, source/record/policy/recipient versions and expiry. Confirmation and approval refer to server-stored immutable objects; arbitrary model fields cannot replace them. Execution and evidence share a transaction. Release uses fixed server-rendered bytes and current consent, grant, versions and authenticated recipient. External effects, network tools, streaming and arbitrary memory ingestion are deliberately absent and denied through the JSON interface.

The SQLite file, token map, Python process and host are trusted. A same-user subprocess can read the database; there is no hostile-code sandbox. A real deployment must protect them with separate service identities, filesystem permissions and network policy and then rerun direct probes from actual model and worker identities. The default demo demonstrates neither encrypted storage nor anonymity. The separate existing privacy modules have their own tests and limitations.

## Teaching lab

Predict before execution, then inspect state and sink bytes rather than the word DENIED:

- Would changing `subject` to s2 pass because the caller is still the advisor? Explain assignment versus identity.
- Would a confident synthetic rationale or a fake registrar citation approve A? Locate the independent instructor source check.
- If the source itself is wrong and both authorized reviewers agree, which security property failed? Run `test_authorized_bad_source_and_appeal_are_not_unauthorized_effect` and distinguish semantic harm from unauthorized execution.
- Can a read-only delegated child propose an action? Can siblings multiply root budget? Read the persisted remaining budget.
- What survives a lost response? What remains unknown about a real external service? The demo loses a local response after commit and reconciles; it does not qualify remote idempotency.
- Can revocation recall bytes already received? Identify the transaction ordering and why subsequent releases deny.
- Why is a retained checkpoint stronger than a self-recomputed hash chain? Explain what happens if the host replaces the checkpoint too.

Transfer: the benefits pack changes the operation and status vocabulary and runs the same joined path. This is a narrow second-domain example, not evidence of public-benefits policy correctness. No educational effectiveness or institutional-readiness study has run.

## Maintenance, reset and recovery

Keep the original receipts and database for review. Reset by selecting a new output directory. Cleanup only a known generated demo directory after retaining its receipts; no command deletes shared author files. On an uncertain local response use `reconcile` before retrying. A source, policy, recipient or record change requires fresh context and approval. Release after appeal needs a new workflow because the old result is stale. After revocation, reconciliation requires a recovery role (registrar or appeal); it does not authorize another effect or disclose arbitrary record content.

Run `make joined-test` after mediator changes and `make adaptive-search` after changing the attack grammar. Recheck held-out results without training on their outcomes. Preserve raw failures and versioned configurations; never replace an expected forbidden effect with an accepted one to make a test pass. Existing CONTRIBUTING, SECURITY and Apache-2.0 license apply. All new fixtures and prose were created for this audit; no outside datasets or media assets were imported. Upgrade gates include independent review, environment locks, CI and target-host isolation. A teaching profile cannot be promoted by merely renaming it operational.
