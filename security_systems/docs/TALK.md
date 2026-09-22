# Talk run sheet: AI Engineer CODE Summit, San Francisco, 10–12 November 2026

**Working title:** *Per-Hop Auth Caught 2 of 10 Agent Attacks. Whole-Chain Caught 10.*

Every number on a slide comes from `evidence/devtools.json`. Regenerate it with `make evidence` before the talk. `pytest` fails if the committed file drifts from the code.

## Before you go on

```bash
make test                      # all green, including reference equivalence
make evidence && git diff --stat evidence/   # expect no diff
python demo.py --no-color > /tmp/rehearsal.txt   # about 10 s; keep this as the offline fallback
```

Use `trustkernel demo --pause 0.8` on stage. It's the same output, paced for reading.

## The arc (about 25 minutes)

| # | Scene | Command | The point | Time |
|---|---|---|---|---|
| 0 | Open cold | none | "Your coding agent can read `prod-db-url`, spawn workers, and ask to deploy. Which of those checks look at the *chain*?" | 1:00 |
| 1 | Per-hop vs whole-chain | `--scene 1` | Three architectures, the same ten hostile chains: 0, 2 and 10 caught. The benign chain completes in all three, so blocking everything wasn't the trick. | 4:00 |
| 2 | The chain leaks a credential into `#general` | `--scene 2` | No agent misbehaves: the hop is attenuated and signed. The summarizer calls its output public. The label travelled with the data, so the post is denied. Remove `session_taint` and the password lands in `#general`. | 4:00 |
| 3 | A hijacked worker tries to ship | `--scene 3` | The injection *worked*. The model is fully compromised. It tries five ways to promote a build: none, forged text, a borrowed approval, a swapped target, calling the tool server directly. Production is unchanged. | 3:00 |
| 4 | Approval vs its own authority | `--scene 4` | A human approved, then the data grant behind it was revoked, so the write is refused. Then 32 callers race one valid approval: one deploy, 31 identical receipts. | 2:30 |
| 5 | The legit change ships | `--scene 5` | It ships with a signed receipt. An insider rewrites history and recomputes the hash chain; the signed checkpoint still catches it. | 2:00 |
| 6 | Remove one control at a time | `--scene 6` | 87 worlds in about a second. In 25 of 29 ablations the harm comes back. The other four are two named redundant pairs, and removing each pair together lets the attack through. | 2:00 |
| 7 | Every domain | `--scene 7` | The same suites against healthcare, finance, and government: a warfarin dose, a credit limit, a benefit termination. Identical verdicts, no new code. | 1:30 |
| 8 | Adopt it | `python examples/guarded_agent_loop.py` | One decorator per tool. A hijacked worker is refused, one deploy runs exactly once, and a credential can't reach `#general`. Clone, break, open an issue. | 2:00 |

## Lines worth keeping exact

- "Every hop was locally correct. The composition was not."
- "Per-hop checking caught the forged hop and the widened hop. It missed the eight attacks that live in the chain: laundering through a loop, reusing a sibling's chain, a confused deputy, depth, a machine passing on consequence, an orphaned delegation, an undisclosed beneficiary, and a chain rooted in nothing."
- "The oracle never asks the mediator whether it refused. It checks what reached the model, the channel, or production."
- "A control whose removal changes nothing was never doing anything."

## If something goes wrong

- **Projector or terminal trouble:** show `/tmp/rehearsal.txt`. It's the same run, and the output is deterministic apart from scene 6's timing line.
- **"Is the model real?"** The agents in the demo are scripted so the run is reproducible. `trustkernel redteam --live` and `OllamaAgent` swap in a local model, and with no runtime they report NOT RUN. The mediators, cryptography, and storage are real either way.
- **"Isn't this just RBAC?"** Scene 1's middle row *is* careful RBAC at every hop. It catches 2 of 10.
- **"Does it only work for this demo?"** Run `trustkernel matrix`. Four domains, the same suites and the same verdicts, and `trustkernel check` proves each world measures what it claims.
- **"How do I use this in my stack?"** `trustkernel.guard` wraps your tool functions. The integration point is your tool dispatcher, and nothing else in your framework changes.

## Audience challenges to invite

- Write a pack that weakens the kernel and gets past `trustkernel pack-check` (the malicious one fails 39 ways).
- Find a red-team move that produces a violation with every control on: `trustkernel redteam --attempts 5000`.
- Add a falsifier in `src/trustkernel/falsification.py` that fails. Open an issue with the output of `trustkernel falsify --json --only <yours>`.
