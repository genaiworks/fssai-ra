# Reviewer assessment and implemented improvements

> **Documentation navigation:** [Documentation map](README.md) · [Start here](START_HERE.md) · [Policy route](README.md#policy-leader-route) · [Engineering route](README.md#ai-engineer-route) · [Glossary](GLOSSARY.md)
>
> **Recommended next:** Return to current evidence → [`ASSURANCE.md`](ASSURANCE.md)

> **A record of one editorial review round, not a current status page.** The
> figures in the table below are the ones that round saw. The repository has
> moved since: see [`../README.md`](../README.md) for current counts and
> [`../evaluation/results/RESULTS.md`](../evaluation/results/RESULTS.md) for the
> generated figures. Nothing on this page is checked by
> `tests/test_paper_alignment.py`, which is why it is dated rather than updated.

## Assessment

I would support this as a conference contribution about a testable reference
framework, with its limitations stated prominently. I would not approve it as a
production-qualified system or as evidence of improved educational outcomes.
This is an editorial assessment, not a decision by UNU or Springer.

The strongest contribution is the connection between an institutional obligation,
an enforcement boundary, an executable failure test, and retained evidence. Keep
that connection as the paper's central argument. The technology stack makes the
artifact usable, but listing more technologies does not establish novelty.

## Implemented in this revision

| Reviewer question | Improvement | Verification |
|---|---|---|
| Does retry mean the same action? | Stored receipts now bind to the full proposal digest; conflicting request-ID reuse is denied | Changed target, requester, evidence and version tests across memory, SQLite and a Redis fixture |
| Does concurrency work beyond one shared connection? | Independent spawned-process replay and competing-version races | Eight processes return one mutation; competing requests produce seven version conflicts |
| What happens when the process dies? | Four abrupt-exit checkpoints around the transaction | Reopening and retrying preserves the expected all-or-nothing state |
| Can another institution reproduce the result? | A command-line resilience runner and source/profile fingerprints | CI reruns and compares the complete supplemental report |
| Does the framework really accept another domain? | Race fixtures derive operation, states and reviewer role from the profile | Generic-template and malformed-profile regression tests |
| Do the claims match the artifact? | Corrected source links, matching script, separate baseline and supplement | Full suite: 240 passing tests at that revision; abstract field constraints still pass |

The review also fixed a SQLite lock leak when creating a connection failed and
removed a PostgreSQL serialization-retry claim absent from the implementation.

## Results to say aloud

“Our original release reports 30 contained adversarial fixtures and six completed
benign tasks. The new supplement tests eight independent processes and four
abrupt-exit recovery cases on local SQLite. These observations support a bounded
authority and recovery claim. They do not establish deployment safety, educational
benefit, or a probability of resisting arbitrary attacks.”

Keep the original `v1.0.0` figures and tag separate from the enhanced source.
The current test count is an engineering statistic, not an additional scientific
result.

## Conditions before an institutional pilot

1. Qualify the actual backend. Exercise PostgreSQL multi-writer evidence appends,
   serialization failures and retry behavior against a real server. Test live
   Redis, Kafka, Spark and Iceberg failure modes separately. SQLite and fakeredis
   results do not establish those guarantees.
2. Test the full institutional workflow. Include authorized human correction,
   appeal, emergency continuity and reconciliation. Record who may use the manual
   route and how it avoids becoming an unlogged bypass.
3. Add independent reproduction and adversarial review. Include unseen attack
   design and, separately, attacks involving a real model. The current fixtures
   are author-designed synthetic tests.
4. Evaluate educational usefulness. Measure task completion, false denials,
   reviewer effort, accessibility and appeal-resolution quality under an approved
   study protocol. Do not infer learner benefit from a security test.
5. Validate the deployment boundary. Inventory every output path, separate
   administrative roles and key custody, and test a real hardware diode if the
   deployment claims physical directionality. Measure costs and energy before
   making comparative claims.

## Adoption warning

Enhanced receipts add a `proposal_digest` field. Historical receipts without it
deny automatic replay with `REPLAY_IDENTITY_UNVERIFIABLE`. Reconcile those cases
under authorized operational procedures. Do not delete their history or issue
new request IDs simply to bypass the check.

## Presentation and submission

Present from [`presentation/slides.html`](presentation/slides.html) with
[its script](presentation/speaker-script.md); the allocation paths live there.
The PowerPoint this section originally pointed to is superseded and predates the
oversight, second-domain and corpus results. The empirical supplement is
supporting material, not an extra field to paste into the abstract form.

Before submission, fill in author details, confirm the final source revision,
recheck the live form, and obtain an education-domain review. Shortlisting is not
final panel acceptance or publication acceptance. The supplied invitation gives
21 September 2026 as the abstract deadline.

The [public repository](https://github.com/genaiworks/fssai-ra) contains the
implementation, tests and evidence. The [recovery and upgrade guide](https://github.com/genaiworks/fssai-ra/blob/main/fssai-ra/docs/RESILIENCE.md)
states the operational limits, and the [empirical supplement](https://github.com/genaiworks/fssai-ra/blob/main/fssai-ra/paper/empirical-supplement.md)
provides methods, observations and threats to validity.
