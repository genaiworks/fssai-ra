"""``fssaira init`` -- scaffold a new governed domain.

Adopting this architecture for health, courts, benefits, procurement, or
licensing should not begin with copying a directory and hoping. The scaffold
produces four files that already fit together, already fail closed, and already
have a test that will go red the moment a transition is declared without an
owner or an approval role.

What it will not do is inherit the demonstrator's assurance claims. The
generated ``ASSURANCE.md`` starts empty on purpose, with a note saying that the
student-support results describe the student-support profile and nothing else.
That refusal is the point: an institution that ships a new domain with a
borrowed evidence table has not adopted the method, only its vocabulary.
"""
from __future__ import annotations

from pathlib import Path

PROFILE = """\
# {title} — application profile
#
# Every transition below is enforced. Name only the transitions that exist in
# the real process, and give each one the role that is genuinely accountable
# for it. A transition with a role nobody holds is a transition that will be
# approved by whoever is available.
profile_id: {domain_id}
version: "0.1"
title: {title}
resource_name: {resource}
owner: {owner}
manual_fallback: >-
  Describe the safe service path used when automation is denied. This is not
  optional: fail-secure means a person can still be served when the machine
  refuses, and the person who owns that path must be named.
transitions:
  - operation: prepare_for_human_review
    from_status: draft
    to_status: ready_for_review
    consequential: true
    approval_role: authorized_reviewer
"""

CONTRACT = """\
# Control contract for {title}.
#
# One entry per consequential capability. If you cannot fill all seven fields,
# the capability is not ready to be automated -- that is the diagnostic, not an
# inconvenience.
domain: {domain_id}
requirements:
  - id: {prefix}-1
    protected_asset: Name the thing that is harmed if this goes wrong
    permitted_operation: The narrowest operation the agent may propose
    enforcement_point: >-
      The service that verifies the actual operation and current policy,
      independently of the model's explanation
    owner: {owner}
    test: >-
      The adversarial attempt that must fail, written so it can be executed
    evidence_artifact: The record a person could use to challenge the outcome
    failure_response: What happens instead, and who performs it
"""

TEST = '''\
"""Executable tests for the {title} domain.

The first two tests are structural and will pass immediately. The third is the
one that matters: replace it with the real adversarial attempt for your domain,
and make sure it fails before the control exists.
"""
from fssaira.evaluation import EvaluationRunner
from fssaira.profiles import ApplicationProfile
from fssaira.verification import verify_profile

PROFILE = "{directory}/profile.yaml"


def test_profile_is_valid_and_every_transition_names_an_approver():
    profile = ApplicationProfile.load(PROFILE)
    assert profile.transitions
    for rule in profile.transitions:
        assert rule.approval_role, f"{{rule.operation}} has no accountable approval role"


def test_authority_invariants_hold_under_bounded_model_checking():
    report = verify_profile(ApplicationProfile.load(PROFILE))
    assert report.holds, [vars(v) for v in report.violations]


def test_adversarial_suite_contains_every_declared_scenario():
    report = EvaluationRunner(ApplicationProfile.load(PROFILE)).run()
    assert report.all_contained
    assert report.unauthorized_mutations == 0
    # A containment rate with no utility denominator is not a result.
    assert report.false_denial_rate == 0.0


def test_replace_me_with_the_attack_that_matters_in_your_domain():
    """Write the failure you are actually afraid of, then make it fail closed."""
    raise AssertionError(
        "Replace this test with the adversarial case for {title}. "
        "A domain with no failing test has no evidence."
    )
'''

ASSURANCE = """\
# Assurance claims for {title}

This file is deliberately empty of claims.

The results published for the reference student-support profile describe that
profile, those fixtures, and that environment. They are not transferable. A
profile that reuses this architecture inherits its *structure* -- the seven
contract fields, the three-step protocol, the executable failure tests -- and
none of its evidence.

Fill the table below as you generate evidence, one row per public claim.

| Public claim | Enforcement or mechanism | Executable evidence | Limit |
|---|---|---|---|
| | | | |

## What is not yet evidenced

- everything.

## Reproduction record

For a result intended for citation, record the repository commit, Python and
dependency versions, operating system, command, test count, and complete
output. Retain raw outputs before writing a narrative summary.
"""

README = """\
# {title}

A governed domain built on the Fail-Secure Sovereign AI Reference Architecture.

```bash
fssaira validate-profile {directory}/profile.yaml
fssaira validate-contract {directory}
fssaira verify {directory}/profile.yaml        # bounded model check
fssaira evaluate {directory}/profile.yaml      # adversarial + utility + ablation
pytest {directory}
```

## Before this is more than a sketch

1. Replace every transition in `profile.yaml` with one that exists in the real
   process, and name the role that is genuinely accountable for it.
2. Fill all seven fields of every requirement in `contract.yaml`. A capability
   whose seven fields cannot be filled is not ready to be automated.
3. Replace the failing test in `test_{domain_id_snake}.py` with the adversarial
   attempt you are actually worried about.
4. Write `ASSURANCE.md` from results you generated, not results you inherited.
5. Name the manual fallback owner, and check that they know.
"""


def scaffold_domain(
    directory: Path,
    *,
    domain_id: str,
    title: str = "Replace Me",
    owner: str = "accountable_service_owner",
    resource: str = "governed_resource",
) -> list[Path]:
    """Create the starter files for a new domain. Never overwrites."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    snake = domain_id.replace("-", "_")
    prefix = "".join(part[0] for part in domain_id.replace("_", "-").split("-") if part).upper()[:3] or "XX"
    context = {
        "domain_id": domain_id,
        "domain_id_snake": snake,
        "title": title,
        "owner": owner,
        "resource": resource,
        "directory": directory.as_posix(),
        "prefix": prefix,
    }
    files = {
        "profile.yaml": PROFILE,
        "contract.yaml": CONTRACT,
        f"test_{snake}.py": TEST,
        "ASSURANCE.md": ASSURANCE,
        "README.md": README,
    }
    created = []
    for name, template in files.items():
        path = directory / name
        if path.exists():
            continue
        path.write_text(template.format(**context), encoding="utf-8")
        created.append(path)
    return created


__all__ = ["scaffold_domain"]
