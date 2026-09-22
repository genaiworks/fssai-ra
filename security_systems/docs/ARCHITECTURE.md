# Architecture

Agents are treated as untrusted code that happens to be good at reasoning. They can read what they're given, think, spawn workers, and propose. Deciding belongs to a small set of **independent mediators**. The agent process holds no credential that would let it act alone, so it can't call, patch, or talk its way past them.

```
           ┌──────────────── intelligence plane (untrusted) ────────────────┐
           │  coordinator ─spawns→ reader ─→ summarizer ─→ publisher         │
           │        proposals · data requests · claims about itself          │
           └───────┬──────────────────────┬──────────────────────┬──────────┘
                   │ propose              │ request              │ delegate
         ┌─────────▼────────┐   ┌─────────▼─────────┐   ┌────────▼──────────┐
         │ execution        │   │ context gate      │   │ delegation        │
         │ mediator         │   │ + release gate    │   │ verifier          │
         │ (R1)             │   │ (R2)              │   │ (root → leaf)     │
         └──┬───────────────┘   └──┬────────────────┘   └───────────────────┘
            │ register credential  │ custody credential
   ┌────────▼─────────┐   ┌────────▼─────────┐   ┌──────────────┐   ┌──────────────┐
   │ register         │   │ encrypted records│   │ model        │   │ evidence     │
   │ (what runs in    │   │ token vault      │   │ registry     │   │ ledger +     │
   │  prod, PR state) │   │ vector index     │   │ (attestation)│   │ signed notary│
   └──────────────────┘   └──────────────────┘   └──────────────┘   └──────────────┘
                 bounded human review queue ── signed, single-use approvals
```

## The mediators

| Mediator | Module | What it refuses |
|---|---|---|
| Execution mediator | `kernel/exact_action.py` | Any state change without a signed approval that is bound to this exact proposal digest, from the declared human role, unexpired and unused. It re-authorizes the read the proposal relied on at the moment of the write. |
| Register credential | `world.py` `CredentialedRegister` | Writes from anything that isn't the executor, which is the only holder of the write credential. That includes a tool server called directly. |
| Context gate | `kernel/disclosure.py`, `kernel/privacy_pipeline.py` | Reads with no grant, the wrong purpose, unnamed fields, other subjects, revoked or expired grants, withdrawn consent, or a zone the class may not enter. Identity reaches the model only as tokens. |
| Release gate | same | Output going to a recipient whose clearance doesn't dominate the output's label. The label is computed from what the session read, not from what the model claims. It also rechecks feeding grants at release time and restores identity only for recipients entitled to it. |
| Delegation verifier | `kernel/delegation.py`, `kernel/grant_delegation.py` | Chains that aren't rooted in an institutional grant, widen at any hop, outlive an ancestor, loop, exceed the depth bound, pass consequential authority machine-to-machine, carry a forged hop, or are presented by someone other than their holder. |
| Model registry | `kernel/model_registry.py` | Context for an endpoint whose served weights, model identity, manifest expiry, class clearance, or purpose don't match its signed manifest. |
| Review queue | `kernel/review_queue.py` | Self-review, the wrong role, and overload turning into approval. Overload defers to a staffed path, never to auto-approve. |
| Evidence notary | `kernel/evidence_notary.py` | Rewritten history. An insider who edits a record and recomputes the whole hash chain still fails the signed checkpoint. |
| Key custody | `kernel/key_custody.py` | Decryption without a custody credential. Erasure destroys per-subject keys, so backups, tokens, and indexes become unreadable. |
| Pack floor | `kernel/pack_floor.py` | Any domain pack that would weaken the kernel: model approvers, downgraded consequence, protected classes in external zones, fail-open responses, missing failure tests, unbounded delegation or break-glass access, or keys the kernel silently ignores. |

## Controls and ablation

`world.ALL_CONTROLS` names every check a world can switch off. By default everything is on. The ablation engine builds the same world with exactly one control removed and re-runs the falsifier that targets it:

- If a component has an `enforce` set (the gates), removing the control means the check isn't enabled.
- If it doesn't (the executor), the world applies an **ablation adapter**. The adapter hands the executor exactly what it would have accepted if that one check didn't exist, for example by re-signing a forged approval with the trusted key. Adapters live only in `world.py`, are named after their control, and raise if they're called while that control is on.

A row is **load-bearing** when the attack fails with the control on, succeeds with it off, and fails again once it's restored. There are 29 ablations: 27 single-control removals and 2 joint pairs. Four are not load-bearing in any shipped world, and the tests pin them:

- F11: `residency` and `model_attestation` each independently stop routing a credential to a weaker endpoint.
- F13: `proposal_digest_binding` and `approval_single_use` each independently stop replay.

Removing either pair together lets the attack through. That's defence in depth, and it's reported as a finding.

## The oracle never asks the mediator

Falsifiers and attackers judge success from `WorldObservations`, which is recorded outside every mediator. The oracle asks whether a protected plaintext reached a model input, what was released and to whom, and whether the register changed. Denial codes are reported alongside the verdict, never instead of it. A mediator that raised the right error but let the value through would fail.

## The guard: the same mediators at your tool dispatcher

`trustkernel.guard.Guard` exposes three of the mediators as a library for an agent stack you already have:

| Guard call | Kernel component | What it enforces |
|---|---|---|
| `root`, `spawn`, `authorize`, and every `@guard.tool` call | `DelegationAuthority.admit_strict` | Authority re-derived from the root on every call, with all nine delegation invariants. `spawn` clamps expiry to the parent's and inherits the parent's resources, so honest trees stay valid. |
| `propose`, `approve`, `@guard.tool(approver_role=...)` | `AsymmetricApprovalAuthority`, `AccountableExecutor` | Ed25519 approval bound to principal, tool, resource, and argument digest. Role, audience, and expiry are checked. The first execution's result is returned on replay, and the side effect never runs twice. |
| `observe`, `consume`, `release`, `@guard.tool(reads=...)` | the pack's `RecipientRule` policy | A per-agent label that only grows, flows to whoever consumes a worker's output, and must be covered by the recipient's clearance and purpose. |

The guard is the enforcement surface; the harness is how you know it works. Both use the same kernel code.

## Where a domain plugs in

The kernel knows nothing about services, patients, accounts, or claimants. A world supplies two files:

- **`pack.yaml`** is policy the kernel reads: data classes, fields, purposes, zones, recipients, declassification rules, transitions and their approver roles, control contracts, model manifests, review capacity, and delegation bounds. The pack floor checks it before anything loads.
- **`world.yaml`** is the cast: subjects and their records, principals and roles, agents, register resources, trusted document sources, plus the `scenario` block that binds the attack suites' roles (the routine field, the sensitive field, the victim resource, the uncleared recipient) to this world's objects.

See [WRITING_A_WORLD.md](WRITING_A_WORLD.md).
