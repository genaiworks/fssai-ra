# Speaker package: three distinct audience outcomes

All stage claims must match [CLAIMS.md](CLAIMS.md). The offline reviewer page and transcript are under `evidence/rehearsal/`. They record actual command output, not a human delivery. This guide supplies a recording script and timed talk plans; it does not claim a completed speaker video or audience pilot.

## Two-minute speaker recording script

“My coding agent has approval to deploy version two. What happens when its next tool call asks for version nine?

I’m Rachna Srivastava. I built a Python reference dispatcher to make that boundary explicit: the human reviews one principal, one resource, and one set of arguments. A worker’s authority is checked from its delegation chain before the tool runs.

But testing the kernel was not enough. The original 203-test suite passed while its integration wrapper still had bypasses. One shortcut returned a cached receipt without validating the supplied approval. Another let a modified session identifier lose its data label.

Here is the cached-receipt demonstration. The deliberately unsafe cache returns the receipt. The guarded call refuses the forged approval. A valid replay still returns the original result, and the observed deployment count stays at one.

The take-home lesson is to test the effect where it happens. A separate example writes an unreviewed build and then says ‘denied.’ If your evaluator trusts the refusal, it misses the write.

I’m bringing the runnable examples, regression tests, and an experiment worksheet. For the workshop, attendees repair a worker-to-summarizer pipeline using starter code, checkpoints, and seven output checks. Legitimate metrics and security-team releases must still work.

These are synthetic, scripted demonstrations. The point is a reproducible way to expose a boundary failure and repair it, with clear requirements for authenticated callers, isolated credentials, and durable execution in a real deployment.”

Record a terminal inset using `python examples/replay_boundary.py`. Use the speaker's own delivery and confirm the biographical wording. Rehearse to 120 seconds rather than claiming the word count guarantees timing.

## Talk 1: deployment approval — 20 minutes

| Time | Visual / live action | What to say and establish |
|---|---|---|
| 0–2 | Approved v2 → requested v9 | Ask the audience which fields their approval actually binds |
| 2–5 | `python examples/guarded_agent_loop.py` | Follow the swapped build and successful authorized release |
| 5–8 | Show `Guard._proposal` and strict JSON binding | Name principal, tool, target, arguments, session, request identity |
| 8–12 | `python examples/replay_boundary.py` | Cache hits are authorization boundaries too; inspect receipt release |
| 12–15 | 32-caller regression | One instance, one callback; distinguish replay from crash recovery |
| 15–18 | Adoption worksheet, caller and target rows | Map authentication, credential ownership, and durable idempotency |
| 18–20 | Three concrete takeaways | Bind exact intent; revalidate replay; observe the actual target |

Keep the ablation table and data-flow workshop out of this talk. For a 15-minute slot, omit the broad dispatcher output and shorten the code walk to the replay example. Fallback: show the recorded terminal page and inspect the same output; disclose that it is a recording.

## Talk 2: evaluation failures — 20 minutes

| Time | Visual / live action | What to say and establish |
|---|---|---|
| 0–2 | “203 tests passed” beside two missing wrapper paths | Counts cannot establish whether the right boundary was exercised |
| 2–6 | `python examples/effect_oracle.py` | A write followed by a refusal is still harm |
| 6–10 | `python examples/replay_boundary.py` | Kernel coverage and integration coverage are different |
| 10–14 | One redundant-pair row from `evidence/devtools.json` | Removing one control may leave another blocking the same attack |
| 14–17 | `examples/effect_oracle.py` and worksheet | Observer is separate; unexpected errors fail the experiment |
| 17–20 | Apply to one audience tool | Define harm, legitimate work, and a positive control |

Do not walk through all 29 rows. Make the audience predict one result before showing it. The unsafe cache is a labeled model of the historical pattern, not an old production deployment or a full replay of a historical commit.

## Workshop: 90 minutes

Use `workshop/INSTRUCTOR.md`; distribute `workshop/README.md` and `workshop/SOLUTIONS.md`. The standalone source archive includes all runtime fixtures. The machine rehearsal verifies exercise execution, not room timing or learner completion.

## Questions to welcome

- Could you solve this with existing authorization tools? Yes; the reusable contribution is the integration failure analysis and evaluation method, not a novel authorization primitive.
- Did you compare against real agent frameworks? No. Do not call an authored baseline representative of a framework or all RBAC.
- Is the model real? Requests are scripted; containment after hostile action selection is the tested boundary.
- Do these results generalize? They establish the supplied cases. Independent attacks and realistic deployment measurements are still needed.
- Are replay semantics durable? Not in the in-memory guard. Show the adoption worksheet and failure/reconciliation boundary.
