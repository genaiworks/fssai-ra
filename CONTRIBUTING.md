# Contributing to FSSAI-RA

The platform supports multiple sectors and research papers. Contributions should improve reusable controls, evidence, integrations, or explanations without tying the project to a single venue.

Start with the [implementation contribution guide](fssai-ra/CONTRIBUTING.md). For a new reader, use the [user guide](fssai-ra/docs/USER_GUIDE.md); for a paper, use the [research workflow](fssai-ra/docs/RESEARCH_GUIDE.md).

- Code and controls: include the forbidden-effect test, benign path, assumptions, and evidence boundary.
- Documentation: state prerequisites, working directory, exact commands, expected outcomes, and next steps. Update the [documentation index](fssai-ra/docs/README.md) and run `make docs-check`.
- Domain profiles: provide new evidence; do not inherit a different domain's result table.
- Research: add a [publication record](publications/TEMPLATE.md), preserve prior submissions, and cite the exact software snapshot.
- Security: use [private reporting guidance](SECURITY.md), not public issues containing exploit details or personal records.

Keep generated exploratory outputs in ignored `work/` directories. Do not include credentials, real personal records, or unpublished manuscripts unintentionally. See [validation tiers](fssai-ra/docs/COMMANDS.md#validation-tiers) for the distinction between runtime checks and historical paper-alignment checks.
