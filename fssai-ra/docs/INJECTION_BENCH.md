# Injection benchmark: what each defence stops, and what it costs

> **Documentation navigation:** [Documentation map](README.md) · [MCP gate](MCP_GATE.md) · [Adopt it](ADOPT.md) · [Glossary](GLOSSARY.md)

> **Recommended next:** Run the worst-case grid (seconds, no model), then put your own local model behind the same five defences.

Anyone who evaluates an agent defence needs two numbers: how often an injected
instruction is acted on, and how much useful work the defence blocks. This
benchmark measures both for five defences, through the real
[MCP gate](MCP_GATE.md) code.

## Design

The benchmark follows the design of
[AgentDojo](https://arxiv.org/abs/2406.13352):

- User tasks are crossed with injection goals.
- The attack is placed in content the task must read, using AgentDojo's
  published *important instructions* template.
- Success is judged on what the environment actually executed. A synthetic
  workplace server ([`examples/bench/workplace_server.py`](../examples/bench/workplace_server.py))
  logs every effect it performs. What the agent says it did is never used.

The grid has 6 user tasks and 4 attacker goals: exfiltrate by email, pay an
attacker, share a document out, and delete the ledger. That gives 24 attacked
and 6 clean cases per defence. Two tasks are designed to expose specific
defences:

- **`share-report`** puts the injection in an internal document that the
  policy trusts, so provenance taint alone cannot see it.
- **`owner-email`** needs a recipient that is read from a web page, so no
  contract written in advance can scope it.

| Defence | What it is |
|---|---|
| `none` | Every tool is reachable and nothing is checked |
| `allowlist` | Only the tools the task needs (a common baseline) |
| `contract` | The allowlist plus exact argument scope for effectful tools (P2) |
| `taint` | Provenance only: after reading untrusted content, no privileged tool (P5) |
| `full` | Contract, taint and exact-action approval (P7), decided by an oracle reviewer |

**The worst-case agent** (`scripted`) completes the task perfectly and obeys
every injection the moment it reads one. The gate never consults the model,
so the attack success this agent reaches is **an upper bound for any model**
behind the same defence. Its utility loss is exactly the defence's false
denials.

**The oracle reviewer** approves exactly the call the user asked for. It shows
what the mechanism allows when review is right, and how many reviews it asks
for. It does not measure how well people review.

## Run it

```bash
fssaira bench injection --out work/bench                                   # worst case, ~10 s
fssaira bench injection --agents ollama:qwen3-vl:8b-instruct --out work/bench   # a local model
fssaira bench injection --agents scripted,ollama:MODEL --configs none,full --out work/bench
```

Results are appended to `results.jsonl` as each case finishes, and a rerun
skips cases that are already there, so a long model run can be resumed. Model
runs use temperature 0 and a fixed seed. Each model turn is capped at 1,024
output tokens, and every result records how many tokens each turn used, so
you can check whether the cap was ever reached.

## Worst-case results

| Defence | Attack success | Utility | Reviews per case |
|---|---|---|---|
| none | 100% | 100% | 0 |
| allowlist | 17% | 100% | 0 |
| contract | 4% | 100% | 0 |
| taint | 17% | 50% | 0 |
| **full** | **0%** | **100%** | 0.7 |

Each partial defence fails in the one place the design predicts, and
[`tests/test_injection_bench.py`](../tests/test_injection_bench.py) asserts
it:

- **The allowlist** leaks only through tools the task legitimately needs.
- **The contract** leaks only where the argument cannot be scoped in advance.
- **Taint** leaks only through the poisoned trusted document, and it blocks
  legitimate work.

The V31 paper (section 5.1) adds two local models run through the same grid.

The tasks, goals and world are synthetic and authored here. The benchmark
measures where the mechanisms bind; it is not a replacement for AgentDojo's
own suites.
