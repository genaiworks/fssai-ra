# The framework: secure agent swarms, from first assessment to proof

> **Documentation navigation:** [Documentation map](README.md) · [Control catalogue](framework/CONTROLS.md) · [Master guide](MASTER_GUIDE.md) · [Specification](SPECIFICATION.md) · [Glossary and acronyms](GLOSSARY.md#acronyms-in-plain-language)
>
> **Recommended next:** Run `fssaira framework init my-programme --org "<your org>" --sector <sector>`, then `fssaira framework assess my-programme/assessment.yaml --roadmap`.

**Use this page as the front door.** An organisation that handles sensitive data and wants
to adopt agents, including swarms of cooperating agents, uses this framework to do four things:

1. find out where it stands;
2. get an ordered plan;
3. build on a reference implementation that already enforces the controls;
4. prove the result to its board, its auditors, its regulators and its buyers.

Every step uses a command you can run. Every claim links to a test that fails if it becomes
untrue.

> **The rule it all rests on.** The model proposes. Separate trusted software decides. A named
> person answers for the decision. Evidence that anyone can recompute shows what happened.
> Adding agents must never silently add authority.

---

## 1. Start in five minutes

```bash
pip install "fssai-ra[privacy]"            # or: pip install -e ".[dev]" from this repository

fssaira framework init acme-agents --org "Acme" --sector finance --target-level 4
fssaira framework assess acme-agents/assessment.yaml --roadmap
fssaira assure report                      # what the reference implementation proves on your host
```

`init` writes a workspace that belongs to **your** programme. The framework itself stays here.

| File | What it is for |
|---|---|
| `assessment.yaml` | one plain-language question per control. You answer each with `evidenced`, `implemented`, `partial`, `planned`, `no` or `n/a` |
| `policy/<sector>.pack.yaml` | the sector domain pack: roles, transitions, manual fallback, disclosure rules |
| `policy/example-passport.json`, `example-task.json` | the workload passport and a task contract to adapt |
| `deploy/k8s/agent-cell.yaml` | a hardened agent cell: no service-account token, default-deny network, non-root, read-only file system |
| `deploy/witnesses.yaml`, `time-servers.yaml` | the witness quorum (organisations are counted, not keys) and the independent time sources |
| `.github/workflows/agentic-assurance.yml` | CI that runs the assurance report and fails if maturity regresses |
| `runbooks/` | policy change, revocation, incident, appeal |
| `evidence/BUNDLE.md` | the go-live evidence checklist |

---

## 2. What the framework contains

| Layer | Where | What it gives you |
|---|---|---|
| **Principles** | [`THESIS.md`](THESIS.md), [`MASTER_GUIDE.md`](MASTER_GUIDE.md) §3 | five commitments and the falsifiers that would disprove them |
| **Control catalogue** | [`framework/CONTROLS.md`](framework/CONTROLS.md), generated from `src/fssaira/framework_catalogue.yaml` | 50 controls in 9 domains. Each has an objective, the failure it prevents, a self-assessment question, an owner, dependencies, its implementation, its proof, refusal codes and standards |
| **Normative requirements** | [`SPECIFICATION.md`](SPECIFICATION.md), [`SPECIFICATION_SWARM_PROFILE.md`](SPECIFICATION_SWARM_PROFILE.md) | MUST, SHOULD and MAY statements, each tied to a test |
| **Reference architecture** | [`REFERENCE_ARCHITECTURE.md`](REFERENCE_ARCHITECTURE.md), [`ARCHITECTURE.md`](ARCHITECTURE.md), [`MASTER_GUIDE.md`](MASTER_GUIDE.md) §4 | the planes: untrusted agent cells, the decision plane, adapters, the evidence plane, the observation lane |
| **Reference implementation** | `src/fssaira/` and the SDK in [`TBC_SDK.md`](TBC_SDK.md) | a working gate, evidence plane and assurance tooling to build on, not just a specification |
| **Sector packs** | [`DOMAIN_PACKS.md`](DOMAIN_PACKS.md), `packs/`, `src/fssaira/ferpa.py` | education, healthcare, finance, corporate, government benefits; [`PACK_AUTHORING.md`](PACK_AUTHORING.md) for new ones |
| **Operations** | [`OPERATIONS.md`](OPERATIONS.md), [`MASTER_GUIDE.md`](MASTER_GUIDE.md) §10, starter-kit runbooks | owners, KPIs, verifier cadence, policy migration, staffing |
| **Assurance** | [`ASSURANCE.md`](ASSURANCE.md), `fssaira assure report` | a digest-stamped report that a buyer reproduces on their own host |
| **Procurement** | [`PROCUREMENT.md`](PROCUREMENT.md), [`MASTER_GUIDE.md`](MASTER_GUIDE.md) §11 | contract clauses citing real refusal codes, and a live vendor demonstration |
| **Open evidence** | [`GAPS.md`](GAPS.md), [`PILOT_PROTOCOL.md`](PILOT_PROTOCOL.md) | the evidence only your deployment can produce, and how to produce it |

### The nine domains

| Domain | Question it answers | Controls |
|---|---|---|
| [GOV](framework/CONTROLS.md#gov--governance-and-accountability) Governance | Who answers for it, and under which rules? | 4 |
| [IDN](framework/CONTROLS.md#idn--identity-credentials-and-containment) Identity and containment | What can a fully compromised agent reach? | 4 |
| [AUT](framework/CONTROLS.md#aut--authority-over-actions) Authority | Who decides that an action happens? | 5 |
| [DAT](framework/CONTROLS.md#dat--data-and-disclosure) Data and disclosure | What may an agent read, and where may results go? | 6 |
| [SWM](framework/CONTROLS.md#swm--swarm-composition) Swarm composition | Does adding agents add authority, spend or leaks? | 8 |
| [EFF](framework/CONTROLS.md#eff--effects-and-adapters) Effects and adapters | Does each real-world action happen once, and never after revocation? | 3 |
| [EVD](framework/CONTROLS.md#evd--evidence) Evidence | Can anyone outside confirm what happened? | 8 |
| [OVS](framework/CONTROLS.md#ovs--human-oversight) Human oversight | Is the human check real, or a rubber stamp? | 5 |
| [ASR](framework/CONTROLS.md#asr--assurance-and-verification) Assurance | Has anyone tried to break it, and can others rerun the proof? | 7 |

### The five maturity levels

These use the same scale as [`PATTERNS.md`](PATTERNS.md#maturity-levels). You reach a level when
every applicable control at that level and below is **evidenced**.

| Level | Name | You can show | Typical first use |
|---|---|---|---|
| 1 | Access-controlled | agents without credentials, declared interfaces, a tamper-evident log, named owners | internal copilots on non-sensitive data |
| 2 | Authority-bound | proposals rather than actions, exact and independent approval, receipts, a deliberation floor | agents that draft changes a person approves |
| 3 | Disclosure-governed | purpose-bound reads, live consent, sealed release, sector tables, witnessed evidence | agents over personal or regulated data |
| 4 | Composition-safe | shared swarm budgets, whole-chain delegation, task graphs, revocation epochs, fenced effects, staffed review | **swarms**: many agents cooperating on consequential work |
| 5 | Evidenced | cross-organisation witnesses, forward-secure keys, qualified adapters, measured trusted base, reproducible report, independent review | production at scale, regulated procurement |

The assessment reports two numbers. The **evidenced** level counts only controls whose proof
has been run in this deployment. The **claimed** level also counts controls that are
implemented but not yet proven. The difference between them is the claim gap, and closing it
is usually the fastest progress available.

---

## 3. The journey

| Step | Outcome | Command or document | Owner |
|---|---|---|---|
| **1. Assess** | an honest evidenced level and claimed level, per domain | `fssaira framework assess assessment.yaml` | executive sponsor with each owner |
| **2. Plan** | waves to the target level, dependencies first, with owner, what to build and how to prove it | `… --roadmap` | programme lead |
| **3. Start** | keys out, contracts in: agent cells, declared interfaces, task contracts | `deploy/k8s/agent-cell.yaml`, [`TBC_SDK.md`](TBC_SDK.md) | enforcer operations |
| **4. Build** | the controls in each wave, on the reference implementation or your own | [`framework/CONTROLS.md`](framework/CONTROLS.md), [`EXTENDING.md`](EXTENDING.md) | per control |
| **5. Qualify** | your own store, connectors and cells pass | `adapter_qualification.qualify`, `agent_cell.probe_cell` | enforcer operations |
| **6. Operate** | runbooks, verifier cadence, staffing, policy migration | `fssaira assure staffing`, [`OPERATIONS.md`](OPERATIONS.md) | operations, evidence auditor |
| **7. Prove** | CI produces a PASS report and a maturity gate on every change | `fssaira assure report`, `… assess --min-level N` | evidence auditor |
| **8. Procure and pilot** | vendors reproduce the digest; a bounded pilot with stop criteria | [`MASTER_GUIDE.md`](MASTER_GUIDE.md) §11, [`PILOT_PROTOCOL.md`](PILOT_PROTOCOL.md) | procurement, sponsor |

---

## 4. Routes by role

| You are | Read first | Then | Your commands |
|---|---|---|---|
| Executive sponsor | this page §2–§3 | [`MASTER_GUIDE.md`](MASTER_GUIDE.md) §12 (what you can claim) | `framework assess` output, `assure report` digest |
| CISO or architect | [`MASTER_GUIDE.md`](MASTER_GUIDE.md) §4–§8 | [`THREAT_MODEL_2026.md`](THREAT_MODEL_2026.md), [`SECURITY.md`](SECURITY.md) | `assure report`, `assure trusted-base`, `assure chaos` |
| Risk, legal or DPO | [`GOVERNED_DISCLOSURE.md`](GOVERNED_DISCLOSURE.md) | your sector pack, [`RESPONSIBLE_AI.md`](RESPONSIBLE_AI.md) | `pack-check`, the sector pack tests |
| Engineer | [`TBC_SDK.md`](TBC_SDK.md), [`ARCHITECTURE.md`](ARCHITECTURE.md) | [`EXTENDING.md`](EXTENDING.md), [`PLATFORM.md`](PLATFORM.md) | `make test`, `framework catalogue` |
| Operations | [`OPERATIONS.md`](OPERATIONS.md) | starter-kit runbooks, [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) | `small verify`, `assure staffing`, `doctor` |
| Auditor | [`ASSURANCE.md`](ASSURANCE.md), [`PUBLIC_VERIFICATION.md`](PUBLIC_VERIFICATION.md) | [`refusal_registry.json`](refusal_registry.json) | reproduce `assure report`; `framework catalogue` |
| Procurement | [`PROCUREMENT.md`](PROCUREMENT.md) | [`MASTER_GUIDE.md`](MASTER_GUIDE.md) §11 | vendor runs `assure report`; compare digests |

---

## 5. Command reference

| Command | Answers |
|---|---|
| `fssaira framework init DIR --org O --sector S` | "Give us a workspace to start from." |
| `fssaira framework assess FILE [--roadmap] [--min-level N]` | "Where are we, what next, and has anything regressed?" |
| `fssaira framework catalogue` | "Is the framework's own catalogue intact?" |
| `fssaira framework render [--check]` | regenerates [`framework/CONTROLS.md`](framework/CONTROLS.md) |
| `fssaira assure report` | "What does the reference implementation prove on this host?" (one digest) |
| `fssaira assure chaos` | "Does revocation hold under partitions, loss, duplicates and clock skew?" |
| `fssaira assure trusted-base` | "How large is the trusted code, and is production running it?" |
| `fssaira assure staffing …` | "How many reviewers does our review floor need?" |
| `fssaira small verify --mode full` | "Does the evidence archive still recompute?" |
| `fssaira scale advise …` | "Small tier or big tier?" |
| `fssaira pack-check FILE` | "Does our sector pack meet the kernel floor?" |
| `fssaira doctor` | "What is this deployment, really?" |

---

## 6. Extending the framework

- **A new sector.** Author a pack with [`PACK_AUTHORING.md`](PACK_AUTHORING.md). Where law
  defines the recipients, add a decision table like `ferpa.py`, in which every answer cites its
  section and unmodelled paths are refused (control GOV-4).
- **A new control.** Add it to `framework_catalogue.yaml` with an implementation, a test, and
  its refusal codes, then run `fssaira framework render`. `tests/test_framework.py` refuses a
  control whose module, test or code does not exist, one that depends on a higher-level
  control, and any dependency cycle.
- **Your own implementation.** The catalogue does not require this codebase. A control is
  evidenced when *your* equivalent of the named proof passes in *your* deployment. The
  reference tests show what that proof has to demonstrate.

## 7. What the framework will not do for you

It will not make an unjust rule just, make a model accurate, or turn a synthetic test into a
field result. Those belong to governance, review and the pilot. The framework makes them
visible and names the evidence each one needs ([`GAPS.md`](GAPS.md)). A level is a statement
about controls **evidenced in your deployment**. It is not a certificate, and it does not
transfer to anyone else's deployment.
