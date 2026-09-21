# Publications using FSSAI-RA

FSSAI-RA is a reusable software reference for multiple research papers. This register separates a paper's venue, status, claims, and reproduction record from the platform's general documentation.

[Project overview](../README.md) · [Research guide](../fssai-ra/docs/RESEARCH_GUIDE.md) · [Software citation](../CITATION.cff) · [New-paper template](TEMPLATE.md)

## Software citation

Use the metadata in `CITATION.cff`, the full commit used for your experiments, and an immutable snapshot URL. The package version alone does not distinguish changes made after a release. Cite papers separately when relying on their arguments or findings; the software citation does not automatically select a conference paper.

Do not add a DOI, publication date, acceptance status, or archival guarantee until it has been verified. Submission and publication are different states.

## Register

| Paper / record | Status | Available materials | Reproduction status |
|---|---|---|---|
| Trust by Construction — prior submission | Submitted, as reported by the repository owner; acceptance/publication not asserted | Local-only V27 reviewed manuscript, review notes, and V24 package under `fssai-ra/paper/`; not included in Git | The exact uploaded file/version and cited software snapshot have not been confirmed in this register. Retained files must not be assumed to be the submitted bytes. |

Older conference demos and presentations remain in their existing directories for stable references. Their presence does not make the platform specific to one sector or venue. Historical submission instructions are records of preparation, not instructions to submit again.

## Add another paper

1. Copy [TEMPLATE.md](TEMPLATE.md) into `publications/<paper-id>/README.md`.
2. Record the research question, authors, status, venue if applicable, and relationship to previous work.
3. Pin the software commit and preserve the exact profiles, fixtures, commands, seeds, and environment.
4. Link a claim-to-evidence table and raw outputs that a reviewer can obtain.
5. Reproduce from a clean checkout and document any required external archive.
6. Add a row here. Freeze submitted artifacts; add a new version for later corrections.

Store working outputs under ignored `work/`. Put only deliberately reviewed, shareable research artifacts in version control. The entire `fssai-ra/paper/` directory is ignored and untracked, including previously tracked manuscripts and build artifacts. Local files are retained. Prefer new publication records here rather than changing that rule to expose all drafts.

## Historical archive availability

Some paper-alignment scripts refer to local manuscripts such as `paper/extended-abstract.md`, `paper/form-ready-abstract.md`, and `paper/tbc-v11/implementation.json`. The entire paper directory is local-only and absent from new checkouts after this change. Previously committed files remain in Git history; ignoring them does not erase history. The current broad test/release targets include these dependencies.

The [command reference](../fssai-ra/docs/COMMANDS.md#validation-tiers) provides manuscript-independent runtime checks. A future paper must supply its required artifacts or explicitly mark unavailable checks; a missing archive must not be reported as a completed reproduction.
