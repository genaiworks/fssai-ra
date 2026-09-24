# Authoring a domain pack: frame, contract, pack, bind, falsify

> **Documentation navigation:** [Documentation map](README.md) · [Start here](START_HERE.md) · [Policy route](README.md#policy-leader-route) · [Engineering route](README.md#ai-engineer-route) · [Glossary](GLOSSARY.md)
>
> **Recommended next:** Copy [`../packs/template.pack.yaml`](../packs/template.pack.yaml), fill it for one capability, load it with `fssaira.kernel.packs.load_pack`, then compare your pack with the shipped ones in [`DOMAIN_PACKS.md`](DOMAIN_PACKS.md).

A new sector replaces the pack, not the kernel. This guide is the route from a policy
question ("which decision here could harm someone?") to a pack the kernel will load,
evaluate, and refuse to weaken. It takes five steps. Each ends in an artifact and a gate
you can run.

## What a pack is, and what it is not

A **pack manifest** (`packs/<sector>.pack.yaml`) is a declaration a policy leader can
read. It lists purposes, data classes and where each may be processed, recipients,
transitions and their approvers, declassification rules, emergency access, fallback,
the tests that falsify it, and its limits.

A manifest enforces nothing on its own. It **references** the configuration the runtime
already enforces: one or more action profiles (`profiles/*.yaml`), optionally a
governed-learning pack, and the kernel's seven-field capability contracts
(`contract/capabilities/*.yaml`). `load_pack` refuses a manifest that:

| Refusal | Finding code | Why it matters |
|---|---|---|
| has an unknown key or an empty required value | `PACK_MANIFEST_INVALID` | an ignored key suggests a control that does not exist; an empty value is an open governance decision |
| still contains a `REPLACE_ME` value | `PACK_PLACEHOLDER_UNFILLED` | a template is not a policy |
| names a test that is not an exact pytest node | `PACK_TEST_MISSING` | a failure test that never runs falsifies nothing |
| names an unknown capability, or drops a kernel one | `PACK_CAPABILITY_UNKNOWN`, `PACK_KERNEL_CAPABILITY_MISSING` | a pack may add guarantees, never remove them |
| disagrees with what its sources enforce | `PACK_MANIFEST_DRIFT` | the manifest may not claim more than the runtime enforces, and may not leave anything out |
| is below the kernel floor | `PACK_*` codes from `fssaira.pack_floor` and `fssaira.kernel.packs` | a consistent description of a weak policy is still a weak policy |

Every finding is reported at once, so a reviewer sees the whole problem in one pass.

## Step 1 — Frame

Name **one** consequential capability in the sector: the governed object, the harm a
wrong change or disclosure causes, and the person who owns it. Start with one
capability and a staffed manual fallback. Do not start with a model.

*Artifact:* a short paragraph naming the object, the harm, the owner, and the fallback.
*Gate:* the owner agrees the fallback is staffed. If it is not, stop. A pack cannot
make up for a missing service path.

## Step 2 — Contract

Write the action profile the runtime will enforce. Copy
[`../profiles/template.yaml`](../profiles/template.yaml) and fill in:

- `governance`: purpose, data classes, prohibited uses, basis, minimisation, retention,
  deletion, residency, incident response, and the data/privacy/security owners;
- `transitions`: every operation, with `from_status`, `to_status`, `consequential`, and
  the human `approval_role` the executor must see;
- optionally `disclosure`: purposes, fields and their classes, model endpoints and
  zones, `class_zones`, recipients, declassification rules, and `break_glass`.

Then decide which kernel capability contracts the sector relies on. Every pack binds
`CAP-ACT-1` (exact action), `CAP-ACT-2` (a requester never approves their own
proposal), `CAP-ACT-3` (single-use approval), and `CAP-EVI-1` (tamper-evident
evidence). A pack with a disclosure policy also binds `CAP-DIS-1` (no laundering
through a summary) and `CAP-DIS-2` (exact, independent declassification). Each contract
has seven filled fields and a failure test that exists.

*Artifact:* `profiles/<sector>.yaml` and a list of capability ids.
*Gate:* `ApplicationProfile.load` accepts the profile, and every transition's status
can be reached from the first.

## Step 3 — Pack

Copy [`../packs/template.pack.yaml`](../packs/template.pack.yaml) to
`packs/<sector>.pack.yaml`. Every key in the template has a comment explaining it.
Declare **exactly** what the profile enforces:

- `purposes`: the disclosure purposes (`[]` for an action-only pack);
- `data_classes`: each class mapped to its enforced zones, or `null` when a class has no
  enforced zone. Never invent a zone;
- `recipients`, `declassification`, `emergency_access`: copied from the disclosure
  policy (`{}` or `[]` when absent, so an absence is visible);
- `transitions`: each operation mapped to its approver roles and whether it is consequential;
- `fallback`, `tests`, `limits`: in your own words. Limits name what is synthetic,
  what is not measured, and which obligations this pack is not evidence of.

*Artifact:* `packs/<sector>.pack.yaml`.
*Gate:* no drift. Change one recipient zone in the manifest and loading must fail with
`PACK_MANIFEST_DRIFT`. Change it back.

## Step 4 — Bind

Load the pack through the kernel and let the floor examine it:

```python
from pathlib import Path
from fssaira.kernel.packs import load_pack, evaluate_pack

pack = load_pack(Path("packs/<sector>.pack.yaml"), root=Path("."))
result = evaluate_pack(pack)
print(pack.floor_exemptions)
print(result.to_dict())
```

The floor applies to every source, whatever the sector:

- no approver, reviewer, or escalation role is a model, agent, system, or wildcard;
- protected classes never reach an external zone, and **any** class reaches a public zone
  only as the output of an identity-removing declassification;
- the declassification approver holds a consequential transition and does not receive
  the class it declassifies;
- emergency access expires within the kernel bound, has a limited number of unreviewed
  uses, and is reviewed by a role that holds a consequential transition and cannot
  itself use the same emergency purpose;
- the manual fallback is a real staffed path.

`floor_exemptions` lists the `pack_floor` rules that are not applicable to an action
profile (per-operation controls and declared review capacity). They are reported, never
hidden. If your sector needs review-capacity guarantees, use the governed-learning
format, which the floor checks in full.

`evaluate_pack` runs the existing, unchanged evaluations: bounded verification and the
adversarial action suite for each profile, plus the generated disclosure suite for each
profile with a disclosure policy. It returns one entry per profile, and each number
names its unit (for example "hostile action scenarios contained" or "bounded disclosure
read and release states"). Do not add numbers with different units together, and do
not add one sector's numbers to another's.

*Artifact:* the evaluation dictionary, committed beside the pack's evidence.
*Gate:* every invariant holds, zero unauthorized mutations, every hostile scenario contained.

## Step 5 — Falsify

A pack is implemented when a test can fail it. List pytest nodes under `tests:` and
make at least one of them sector-specific: the misuse case the owner named in Step 1,
written as a test that must be refused. Then weaken a copy of your own pack on purpose,
in a temporary directory, and check that the loader refuses it:

- mark the consequential transition non-consequential in both the profile and the manifest;
- add `external` to a restricted class's zones in both files;
- raise the break-glass TTL beyond the kernel bound.

`tests/packs/test_kernel_packs.py` shows each of these mutations against real packs, and
`tests/packs/test_pack_transfer.py` builds a new sector only in `tmp_path` and proves the
kernel's source files did not change.

*Artifact:* the tests named in the manifest, passing, and a recorded refusal for each
deliberate weakening.
*Gate:* the tests exist as exact nodes (the loader checks this), and each fails when its
control is removed.

## The shipped packs

| Pack | Sources | Disclosure fixture |
|---|---|---|
| [`healthcare.pack.yaml`](../packs/healthcare.pack.yaml) | `healthcare_record_access.yaml` | yes |
| [`corporate.pack.yaml`](../packs/corporate.pack.yaml) | `corporate_confidential_data.yaml` | yes |
| [`finance.pack.yaml`](../packs/finance.pack.yaml) | `financial_consumer_data.yaml` | yes |
| [`benefits.pack.yaml`](../packs/benefits.pack.yaml) | `government_benefits.yaml` | yes |
| [`education.pack.yaml`](../packs/education.pack.yaml) | `student_support.yaml`, `academic_record_correction.yaml`, governed-learning pack | no; action fixtures only |

What a loaded pack does not tell you: whether the purposes are lawful, whether the
approvers have the capacity to review, whether de-identification resists
re-identification, or whether any real deployment behaves like the synthetic fixtures.
A pack carries its own evidence. It never inherits another sector's.
