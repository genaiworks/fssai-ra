# Engineering decisions

- Preserve original paper files during this code-only phase. A metric disagreement is recorded, not repaired by fabricating code or silently rewriting prose.
- Introduce stable public packages around the existing tested implementation instead of moving all modules and breaking imports. New functionality must enforce behavior, not merely rename files.
- Keep separate denominators for action, disclosure, chain, state, ablation, task and institutional attestations. The conference suite legitimately has redundant single-control ablations; require matched combination evidence rather than manufacturing harm for every removal.
- Prefer SQLite and memory for offline qualification. Existing network adapters remain available but unqualified until their actual backend runs the same tests. No automatically inferred production certification.
- Preserve the prior tested SDK changes in the M0 checkpoint, then commit the next milestones separately. All work remains local.
- Static typing is enforced on the new typed public interfaces. Existing untyped implementation modules remain an explicit migration boundary rather than being silenced by broad per-file ignores.
