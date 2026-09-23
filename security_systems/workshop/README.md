# Stop the summarizer from leaking secrets — participant lab

**Outcome:** get a useful metrics summary through, block a protected value in a public channel, and retain the protection across multiple handoffs and exception paths. You will edit three small functions and inspect an actual output sink. All data is synthetic; no model API is used.

## Setup before the room

Unpack the source bundle and open a terminal in `security_systems`. Use Python 3.10+; the recorded clean-install rehearsal uses Python 3.14. On Windows, use `.venv\Scripts\activate` in place of the activation command below.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -c requirements-conference.txt -e '.[dev]'
python -m workshop.check --implementation solution
```

Expect **7/7 checks passed**. This setup check does not complete the exercise: you will now edit `workshop/starter.py`. If installation fails, check `python --version` and `python -m pip --version` refer to the same environment. Install dependencies before the event; runtime exercises need no network. The source bundle is required because the lab uses its worlds and tests.

## 1. Observe the leak (10 minutes)

```bash
python -m workshop.check --implementation starter
python -m workshop.check --implementation starter --case secret_public --json
```

Expect **2/7**, exit status 1, and `SYNTHETIC-WORKSHOP-SECRET` in `released`. This is a deliberately broken starter. The two passes are useful work: a metrics release and a secret release to the authorized security team. Write down the harmful effect before you edit code.

## 2. Label the read (15 minutes)

Open `workshop/starter.py`. Complete TODO 1 using `guard.observe(ctx, {"secret-credentials"})`. Place it before the simulated failure. Run the `failed_read` case with `--json`: `label_retained` must become true even though the function raises.

Why not label only on successful return? A tool may read a value and expose it before losing its response. Conservatively retain the label. Recovery checkpoint: `workshop/checkpoints/step1.py`.

## 3. Carry the label (15 minutes)

Complete TODO 2 using `guard.consume(consumer, producer)`. Keep returning the text. It is the reader's actual label, not the summary's self-description, that flows to the next worker.

The sink tests still fail until a release gate checks those labels. That is intentional: metadata without enforcement does not prevent disclosure. Recovery checkpoint: `workshop/checkpoints/step2.py`.

## 4. Enforce at the output (15 minutes)

Complete TODO 3 by returning `guard.release(ctx, text, recipient=recipient, purpose=purpose)`. Run all starter checks again. Expect **7/7**. Do not “fix” this by blocking every output; the metrics and security-team cases must still release their contents.

## 5. Challenge your fix (20 minutes)

Run each of `reset_session`, `failed_read`, `two_handoffs`, and `unknown_recipient` using `--case`. For each, explain both the denial and the empty `released` list. Temporarily omit the handoff call, rerun `secret_public`, observe the leak, then restore it. Only mutate this synthetic exercise.

Read `tests/test_workshop.py`: a callback returning the text `DENIED` still publishes an output. A diagnostic string is not enforcement. Unexpected exceptions are allowed to fail the run; a broken attack is not a successful containment result.

## 6. Transfer and exit check (15 minutes)

Choose one synthetic tool in your own workflow. Write its data class, permitted recipient, and every worker handoff. Point to the trusted code that will enforce each boundary. If a field does not fit the current policy, describe the needed policy change before adding it.

You are done when:

- both legitimate releases work;
- public, unknown-recipient, and reset-session releases remain empty;
- failed reads retain their label;
- removing a handoff exposes a leak and restoring it blocks that leak;
- you can identify one unmediated path the decorator cannot protect.

Compare with `workshop/solution.py` and [the solution explanation](SOLUTIONS.md). Keep the [adoption worksheet](../docs/ADOPTION.md).
