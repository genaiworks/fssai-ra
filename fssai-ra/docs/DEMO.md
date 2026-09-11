# The demonstration

Two minutes, fully offline. No network, no model weights, no GPU, no Docker.

```bash
pip install -e ".[dev]"
python scripts/demo.py
```

Add `--fast` to drop the pauses, or `--act N` to jump to one act. The script runs
in CI ([`tests/test_demo.py`](../tests/test_demo.py)) and its narration is checked
against the behaviour it claims to show — including that it reaches for no
network client and no model backend.

## What the six acts show

| Act | Question | What you see |
|---|---|---|
| 1 | What crosses the boundary, and can anything cross back? | An unsigned artifact quarantined; a signed one accepted with its active content stripped and a content hash attached; the channel confirmed to expose no return path |
| 2 | The model is the adversary. What does it get? | A deliberately compromised backend, granted **every** tool, proposing exfiltration, self-escalation, evidence destruction and an unauthorized award. All denied, each with a stable code, each recorded on a path the agent cannot write to |
| 3 | Does legitimate work still happen? | Propose → approve by a named officer → execute. Then a retry that returns the same receipt without a second mutation |
| 4 | What if the proposal changes after review? | `APPROVAL_PAYLOAD_MISMATCH`, zero mutations, both resources untouched |
| 5 | What if someone edits the record? | An agent's write refused; an insider's direct edit detected by the chain — and the honest caveat that detection is not prevention |
| 6 | Compared to what? | The same seven attacks put to three architectures, with a bar for each |

## The one-minute version

If you have sixty seconds, run act 6 alone:

```bash
python scripts/demo.py --act 6 --fast
```

```
  A · unguarded        ··································   0.0%  0/7 contained
                       28 harmful actions reached the protected asset
  B · prompt-guarded   █████████·························  28.6%  2/7 contained
                       8 harmful actions reached the protected asset
  C · FSSAI-RA         ██████████████████████████████████ 100.0%  7/7 contained
                       0 harmful actions reached the protected asset
```

All three arms completed all the legitimate work. That last line is the one that
makes the first three worth reporting.

## Presenting it

See [`presentation/speaker-script.md`](presentation/speaker-script.md). In short:

- **Rehearse it, then assume the network will fail.** This script is the fallback
  for a live console demo as well as a demo in its own right. It takes no
  arguments that can fail and produces identical output every time.
- **Large font, one terminal window, no editor visible.**
- Pause on the red `APPROVAL_PAYLOAD_MISMATCH` in act 4. That is the moment a
  governance rule becomes observable behaviour.
- Act 3 matters as much as act 2. A demo that only shows refusals is an argument
  for not deploying anything.

## With the full stack

```bash
python scripts/bootstrap_dev_env.py
docker compose --env-file deploy/.env -f deploy/compose.yaml up -d
python scripts/smoke_stack.py
open http://localhost:8088          # the operator console
```

Add `--profile model` for a local model through Ollama, and `--profile analytics`
for MinIO, the Iceberg REST catalog, and Spark.

In the console: register a resource and run the three steps on the **Actions**
tab, tick *"Alter the destination state after review"* to see the denial, then
open the **Evidence** tab to see what the successful run left behind. The
**Assurance** tab runs the model checker and the conformance suite against the
backends that deployment actually has.

## What this demonstrates, and what it does not

It demonstrates specified properties on synthetic fixtures in a declared
environment. It is not a security certification, a penetration test, or evidence
of production readiness. Every claim maps to its test and its limit in
[`ASSURANCE.md`](ASSURANCE.md); reviewers wanting the short path to checking them
should start at [`REVIEWERS.md`](REVIEWERS.md).
