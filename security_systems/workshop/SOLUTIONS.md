# Why the three-line repair works

The complete reference is `solution.py`.

1. `guard.observe(ctx, {"secret-credentials"})` records the read before the exception path. This is conservative data-flow tracking, not inspection of the secret's spelling.
2. `guard.consume(consumer, producer)` unions the reader's label into the receiving context. The same operation must happen at every subsequent handoff.
3. `guard.release(...)` compares the accumulated label and declared purpose with the recipient policy before the harness appends to its sink.

Expected results: starter, step 1, and step 2 each pass **2/7** output checks; the solution passes **7/7**. The intermediate stages improve metadata but do not yet enforce at the sink. In `--json`, the failed-read label changes after step 1. Output containment changes only when the full path is connected.

| Case | Expected output | Reason |
|---|---|---|
| metrics | One telemetry summary | Legitimate public-channel work remains useful |
| secret_public | Empty | Public channel lacks secret clearance |
| secret_security | One synthetic secret | Correct recipient and purpose |
| reset_session | Empty | Caller cannot substitute a fresh context handle |
| failed_read | Empty; reader label retained | Exception does not erase a read |
| two_handoffs | Empty | Transitive label propagation |
| unknown_recipient | Empty | Undeclared recipient has no release entitlement |

Common incorrect solutions: return an empty string instead of denying (still a sink write); erase the producer label after handoff (breaks later consumers); scan for the literal word “secret” (misses transformed output); wrap all exceptions and call it a pass (hides an unexecuted attack); deny all outputs (fails the two useful cases).

A real deployment must resolve caller identities server-side, protect issuer APIs, preserve labels across serialization and queues, and mediate every egress path. This lab does not implement those network or process boundaries. Authorized secret release is intentionally allowed; the exercise is policy enforcement, not a claim that every secret must always be blocked.
