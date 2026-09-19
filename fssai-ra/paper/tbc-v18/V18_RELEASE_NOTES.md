# Trust by Construction — V18 release

Released 19 September 2026. Author: Rachana (Gen) Srivastava.

## Submission files

- `Trust_by_Construction_V18_Extended_Abstract.docx` / `.pdf` — the submission-length contribution for the invitation supplied by the author. Four pages; 1,497 whitespace-delimited words including title, author block, headings, two figure captions and nine references (1,376 before references). Word processors may count differently. The invitation requests approximately 1,500 words and gives 21 September 2026 as its deadline.
- `Trust_by_Construction_V18.docx` / `.pdf` — the full technical manuscript. Sixteen pages; 7,146 words including tables and references; six original figures, five tables, one capability-contract listing and 46 references.

Use the extended abstract for the invited submission and retain the full paper as supporting material. No conference-specific Word template was supplied; this release uses a consistent scholarly layout and asserts no publisher-template certification. Nothing has been submitted externally.

## What changed from V17

V18 is a substantial revision rather than an edit pass.

1. **Six original figures instead of one.** The enforcement path, the five-step contract across the task lifecycle, the authority envelope that draws Property 1, the recorded delivery-and-revocation trace, agent-graph composition, and the release-channel measurement. Every figure is a drawing of the architecture or of a recorded mechanism trace; none reports a field measurement.
2. **The reference base is agentic-era.** 46 references, 38 of them from 2023–2026: the 2026 model-hosting compromise and its independent investigation, indirect prompt injection, InjecAgent, AgentDojo, AgentHarm, CaMeL, FIDES, prompt-injection design patterns, system-level information-flow defence, SecAlign, AI control, monitorability and sabotage evaluations, AgentSecBench, AgentDyn, Silent Egress, the Model Context Protocol, NIST Zero Trust and the NIST agent identity and authorisation work, OWASP's agentic Top 10 and Agent Control Standard, ISO/IEC 42001, the EU AI Act, UNESCO guidance and competency frameworks, FERPA, the Global Digital Compact and SDG 4. Six pre-2007 anchors remain because the argument rests on them directly: Lampson, Saltzer and Schroeder, Denning, FERPA, Sabelfeld and Myers, Nissenbaum.
3. **Swarm composition is restored from V12** as §3.6 with its own figure: individually acceptable agent scopes composing into a protected-source-to-public-sink path, and the declared-graph check that rejects it.
4. **Five numbered trusted assumptions (Table 3)** make the guarantee's dependencies checkable against an intended deployment instead of implied by prose.
5. **A claim-to-test map (Table 4) and a full capability contract (Listing 1)** let a reviewer follow any claim to the executable refusal that backs it.
6. **The mechanism evidence is de-emphasised and re-framed.** No counts appear in the abstract or the conclusion. Table 5 states for each row what it is not, and the section is titled for what the evidence does not show. Fixture provenance is disclosed once, precisely.
7. **V12's voice is back**: the slogan subtitle, the conference theme line, section titles that say something, and the closing cadence.

## Verification performed for this release

- `python source/verify_release.py` — all checks pass.
- Both DOCX files rebuild byte-for-byte from source on this toolchain.
- Every in-text reference number resolves and every listed reference is cited; the build fails otherwise.
- All sixteen full-paper pages and four abstract pages were rendered and visually inspected.
- The full implementation suite was re-run: **1,445 tests collected and passed**. The targeted frontier-control, covert-channel and monitor-evaluation suites (114 tests) also pass, and the three `pytest -k` selectors named in the manuscript each resolve to live tests.
- No implementation code was changed for this release.

Local source revision examined: 729ff4ac (branch `integrate/third-audit-hardening`).

## One item to spot-check before submission

Three 2026 ecosystem references carried forward from the V12 manuscript — the model-hosting security incident disclosure, the vendor response and the independent investigation — should have their links confirmed at submission time. They are the paper's opening motivation, so a stale URL is worth two minutes.

## Rebuilding

`source/` holds the editable manuscripts, the reference database, the figure generator and the deterministic builder. With Python, python-docx, Pillow and matplotlib installed:

```
python source/build_release.py <output-directory>
python source/verify_release.py
```

The builder writes each manuscript twice from one markdown source: a DOCX through python-docx, saved with fixed zip entry metadata so the bytes are reproducible, and a paginated print HTML rendered to PDF by headless Chrome. `render/` keeps that HTML and the figures it references, so the PDFs can be re-rendered without Python. PDF bytes are not reproducible — the renderer stamps a creation time — so `V18_SHA256SUMS.txt` records the PDFs as distributed. Figures use the system Arial fonts; equivalent font and library versions are required for byte-identical DOCX output.

Implementation repository: https://github.com/genaiworks/fssai-ra
