# AI Engineer stage rehearsal — 20 minutes

Title: **Your Coding Agent Has Approval. Is It for This Deploy?**

Use one software-delivery story. The full seven-scene demo is a backup artifact, not the stage script. Run from `security_systems` in the installed environment.

| Minutes | Command / material | Point |
|---|---|---|
| 0–2 | Incident workflow and trust boundary | A hostile tool request must not become an unauthorized deploy |
| 2–6 | `trustkernel demo --scene 3 --no-color` | Inspect the resulting register, not only denial messages; actors are scripted |
| 6–9 | `trustkernel demo --scene 1 --no-color` | The 0/2/10 result belongs to three specified fixture implementations |
| 9–12 | `trustkernel demo --scene 2 --no-color` | Labels must flow through the summarizer; show the leak under ablation |
| 12–16 | `python examples/guarded_agent_loop.py` | Connect the checks to a dispatcher and exact deployment arguments |
| 16–18 | Wrapper regressions in `tests/test_guard_adversarial.py` | Tampered contexts and cached approvals can defeat integration assumptions |
| 18–20 | Boundaries and takeaways | Authenticated dispatcher, independent approval issuer, mediated egress, durable idempotency |

## Rehearsal

```bash
make test
make lint
mkdir -p ../work/security-review
python demo.py --no-color > ../work/security-review/rehearsal.txt
python examples/guarded_agent_loop.py
```

The test suite regenerates each evidence file into a temporary directory and compares it with the committed artifact. Keep a recording and the transcript available for terminal problems. Measure actual timing on the presentation laptop; no cold-install or runtime guarantee is implied.

## Answers to skeptical questions

**Isn't this capability security?** Yes. The engineering contribution is applying established controls to this dispatcher and making the failure claims executable. Cite the related work in `TECHNICAL_NOTE.md`.

**Did RBAC fail eight times?** No general RBAC implementation was benchmarked. The middle arm implements scope attenuation and HMAC verification. Its missing checks explain the results.

**Was a real model compromised?** No model is used in the scripted evidence. The attacker selects malicious actions directly. This tests containment after a hostile decision, not how often prompt injection induces it.

**Do four worlds prove portability?** They show the harness can be parameterized with four vocabularies and policies. The cases are correlated; they are not four field studies.

**Exactly once across a crash?** No. The guard caches successful callbacks in memory and suppresses repeat execution within that instance. An external effect and its receipt need durable coordination and reconciliation.

**Can an agent bypass the decorator?** Arbitrary Python in the guard process can bypass it. The deployment must isolate credentials and resolve caller contexts in a trusted dispatcher. Every data handoff must propagate labels.

**Did an ablation that changed nothing find a useless control?** Not necessarily. Another control can still block the same attack. Test paired removal and inspect the coverage of the attack.
