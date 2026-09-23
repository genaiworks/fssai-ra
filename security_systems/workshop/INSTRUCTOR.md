# Instructor guide — 90-minute lab

Use `README.md` as the participant handout and `SOLUTIONS.md` for debrief. Prepare an editable source bundle and offline demo transcript. Project text at least 24 pt; read denial codes aloud. Do not require a paid model account or real credentials.

| Time | Activity | Checkpoint / recovery |
|---|---|---|
| 0–10 | Define sink and show the starter leak | Everyone identifies the synthetic value in `released` |
| 10–25 | Label the read before its exception | Use step1 if someone is stuck |
| 25–40 | Propagate across a handoff | Use step2; explain why output is still unsafe |
| 40–55 | Add the release gate | Seven checks pass; two useful outputs remain |
| 55–75 | Attack reset, exception, and two-hop paths | Use solution for recovery; show one removal and restoration |
| 75–90 | Map a participant tool and discuss limits | Complete adoption worksheet and exit check |

Preflight is assigned before arrival. Reserve a helper or pair participants if setup consumes the opening ten minutes. A 60-minute adaptation uses prepared checkpoints and drops the custom-tool mapping; a 120-minute adaptation adds participant-written negative cases. Do not claim this timing has been validated with a live audience: only machine execution has been rehearsed.

## Questions that test understanding

- Why does step 1 still leak? A label is metadata until all handoffs and sinks enforce it.
- Why retain a label when a read raises? The failure may happen after exposure.
- Why can the security team receive the secret? Policy has legitimate positive cases.
- What happens if the worker publishes directly? An unmediated output bypasses this architecture.
- Does possession of a valid context authenticate a user? No; the dispatcher must bind it to an authenticated caller.
- Does “7/7” prove the system secure? It proves seven declared cases on synthetic fixtures.

## Evidence to collect at a real pilot

Record installation success, time to each checkpoint, questions that blocked progress, final positive/negative case completion, and whether each attendee can identify an unmediated path. Use aggregate counts without collecting participant secrets or proprietary code. Revise the pacing after the pilot; do not invent attendance or satisfaction scores.
