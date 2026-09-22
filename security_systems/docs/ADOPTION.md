# Take the method back to your agent stack

Complete this worksheet for one tool and one harmful outcome before expanding the integration.

| Boundary | Write down your answer | Evidence to collect |
|---|---|---|
| Caller | Which authenticated service identity selects the context? | A forged caller field cannot select another context |
| Authority | Which tools and resources does the worker need? | A narrow worker completes its task and cannot invoke a sibling's tool |
| Approval | Which principal, target, arguments, and request identity did the human review? | Swap the build after review; observe unchanged target state |
| Replay | Where are idempotency keys and receipts durable? | Race and restart around the external effect; reconcile uncertain outcomes |
| Read | Which trusted source supplies the data class? | A tool exception retains the read label |
| Handoff | Which queues, summaries, files, and caches carry the data? | Remove one propagation step and observe the resulting leak in a fixture |
| Release | Which component owns every outbound credential? | An unknown recipient gets no output |
| Oracle | Where can you independently observe the effect? | “Denied after write” is recorded as harm |
| Utility | Which authorized workflows must continue to work? | Report benign completion separately from attack containment |

## Copyable experiment record

```text
Case ID / version:
Asset and observable harmful outcome:
Attacker capability and entry point:
Trusted components and excluded paths:
Initial state and legitimate comparison:
Protected run: observation before / after:
Control removed: observation before / after:
Control restored: observation before / after:
Unexpected errors (never count as containment):
Result, denominator, and untested cases:
Reproduction command, environment, artifact digest:
```

Start with [the standard-library effect oracle](../examples/effect_oracle.py). Supply a snapshot reader for your actual system of record or recipient sink. Do not derive the observation from the guard's denial counter. Keep exceptions that indicate a broken test distinct from expected authorization denials.

The reference guard is not a production isolation layer. Finish caller authentication, control-plane separation, durable target-side idempotency, recovery, and full egress mediation in your own deployment before relying on those properties.

## Contribute a useful counterexample

Include a minimal synthetic reproduction, the harmful observable effect, expected legitimate behavior, the exact environment, and the smallest change that restores containment. Run `make community` and `make test`. Avoid real credentials or personal data. Report an exploitable issue privately through the repository's [security policy](../SECURITY.md) rather than posting sensitive details publicly.
