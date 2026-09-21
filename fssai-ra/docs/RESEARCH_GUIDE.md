# Use this repository in research and future papers

> **Documentation navigation:** [Documentation map](README.md) · [Start here](START_HERE.md) · [Glossary](GLOSSARY.md)
>
> **Recommended next:** Follow the [user guide](USER_GUIDE.md) for a walkthrough or the [research guide](RESEARCH_GUIDE.md) to record an experiment.

## Cite the platform independently

FSSAI-RA is the software; Trust by Construction is its design approach. A paper is one application or analysis of that platform. Cite the exact code snapshot and separately cite any paper whose argument or results you use. [CITATION.cff](../../CITATION.cff) describes the software, and the [publication register](../../publications/README.md) keeps venue-specific records out of the main onboarding route.

A version string alone is insufficient: this source tree may have changed since the release carrying that version. Record the full commit and whether there were local changes. Use a release tag or archived identifier only when it actually exists and matches your experiment. Do not invent a DOI or describe a submission as accepted.

## 1. Define a bounded question

Choose one mechanism and an observable outcome. Examples include delegated budget conservation, denial of release after consent withdrawal, approval payload binding, effects of a new domain profile, or the assumed throughput/quality tradeoff in assisted review.

Before running, write down:

- Claim, threat model, trusted components, and excluded paths.
- Profile, backend, model mode, and independent enforcement point.
- Forbidden effect and benign success criteria.
- Comparator, ablation, seed, budget, and stopping rule.
- Unit of analysis: test case, modeled state, request, episode, or participant.
- What result would refute the claim.

Use the [publication template](../../publications/TEMPLATE.md). Do not treat all passing tests as independent security trials.

## 2. Freeze inputs and capture provenance

From the inner application directory, with your environment active:

```bash
mkdir -p work/study-01
git rev-parse HEAD > work/study-01/commit.txt
git status --short > work/study-01/git-status.txt
git diff --binary > work/study-01/working-tree.patch
python --version > work/study-01/python-version.txt
python -m pip freeze > work/study-01/dependencies.txt
python -c "import json, platform, sqlite3; print(json.dumps({'platform': platform.platform(), 'sqlite': sqlite3.sqlite_version}, indent=2))" > work/study-01/environment.json
```

Inspect the status before proceeding. A patch does not capture untracked files, and `pip freeze` can contain machine-specific editable paths. Retain relevant new source/configuration files separately; prepare and verify a clean committed snapshot before publishing a citation.

Record exact command lines and retain profile, contract, and fixture hashes. The checked-in `audit/` records are prior runs; do not label them as your new environment.

## 3. Generate a small evidence bundle

From APP:

```bash
fssaira verify profiles/student_support.yaml --output work/study-01/verification.json
fssaira evaluate profiles/student_support.yaml --output work/study-01/evaluation.json
fssaira conformance --backend sql --output work/study-01/conformance.json
python -m pytest tests/test_exact_action.py tests/test_delegation.py --junitxml=work/study-01/tests.xml
```

Run commands individually, inspect their exit status, and record stdout/stderr. Add the tests relevant to your question; these examples are not a complete platform qualification.

For an end-to-end local trace:

```bash
python scripts/joined_demo.py --output work/study-01/joined
```

For a different domain, substitute its profile explicitly. Keep results from different fixtures and harnesses separate. For adaptive experiments, retain training/development versus held-out splits and disclose whether the attacker was tuned on a reported result.

## 4. Build the claim-to-evidence table

| Claim | Exact input/configuration | Command and artifact | Comparator / failure case | Limit |
|---|---|---|---|---|
| Example: changed approved payload is rejected | Named profile, backend, commit | Named test, JUnit output, receipt/state | Changed payload vs approved payload | Synthetic case; trusted executor |

Report both denied attacks and completed benign work. Include failed runs, false denials, exclusions, and any manual steps. Show that a control affects the forbidden effect by removing and restoring it where supported. Keep generated result snapshots distinct from narrative interpretation.

For oversight, label all behavioral parameters as declared assumptions unless measured in an actual study. For data privacy, distinguish tokenization, access control, anonymity, and physical erasure. For integrity, explain where the independent anchor is kept.

## 5. Reproduce from a clean checkout

Use a separate checkout of the cited commit and follow only the proposed reproduction instructions. Confirm every required profile, script, input, and evidence artifact is tracked or supplied through an accessible archive. Local ignored paper drafts can make an author's checkout pass while a reviewer’s checkout fails.

The default public suite runs without manuscripts. The optional `make manuscript-check` depends on local-only archives and fails clearly when they are missing. Keep a targeted reproduction command for the specific paper in its publication record. If you change code or data after the final run, rerun the affected experiment and refresh the record.

Before publishing an evidence bundle, review it for personal records, credentials, local filesystem paths, and copyrighted or restricted inputs. Use synthetic fixtures unless an authorized study explicitly permits other data.

## 6. Record and cite the paper

Copy [TEMPLATE.md](../../publications/TEMPLATE.md) to `publications/<paper-id>/README.md`, fill it, and add a row to the [register](../../publications/README.md). Use a descriptive paper identifier independent of manuscript revision numbers.

Each record should identify the title, authors, status, venue (if any), exact software commit, result bundle, reproduction commands, claims, limits, and relationship to earlier papers. Submitted artifacts should remain frozen; later corrections get a new version and an explanation.

Suggested software-reference structure:

> Srivastava, R. FSSAI-RA: Fail-Secure Sovereign AI Reference Architecture. Software, version [version], commit [full hash]. https://github.com/genaiworks/fssai-ra/tree/[full hash]. Accessed [date].

The bracketed fields are placeholders to replace with verified metadata. Use the author spelling required by the actual citation metadata or publication. A repository URL, package version, paper version, and DOI are different identifiers.

## 7. Preserve results across papers

Reuse the platform, but say when results are reused rather than new. Do not pool overlapping suites or reruns as independent observations. Keep prior paper artifacts and evidence stable; add new records for extensions, different populations, new domains, or stronger deployment evidence. The repository's broad scope does not itself establish novelty for a new paper.
