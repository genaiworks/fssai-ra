# Trust by Construction — V17 release

Released 19 September 2026. Author: Rachana (Gen) Srivastava.

## Submission files

- Trust_by_Construction_V17_Extended_Abstract.docx / .pdf: the submission-length contribution for the invitation supplied by the author. Three pages; 1,493 whitespace-delimited words including title, author, headings and seven references (1,370 before references). Word processors may count differently. The supplied invitation requests approximately 1,500 words and gives 21 September 2026 as its deadline.
- Trust_by_Construction_V17.docx / .pdf: the full technical manuscript. Nine pages; 28 references; 4,407 words including tables and references.

Use the extended abstract for the invited abstract submission; retain the full paper as supporting material or for a later proceedings request. No conference-specific Word template was supplied. This release uses a consistent scholarly layout and does not assert publisher-template certification. Nothing has been submitted externally.

## V17 changes and checks

V17 adds an explicit five-step enforcement contract, a worked delivery-revocation trace grounded in executable tests, and direct test selectors. It retains the numbered invariant, classical security foundations, related-work and terminology tables, governance references, extension recipe and bounded interpretation of release-channel results. The abstract is tightened below 1,500 words including references. Fixture provenance is disclosed once per manuscript; experimental checks are not presented as production evidence.

All nine full-paper pages and three abstract pages were rendered and visually inspected. Both DOCX files rebuilt byte-for-byte. All in-text reference numbers resolve. The targeted frontier-control, covert-channel and monitor-evaluation suites passed: 114 tests in 11.04 seconds. The paper's 1,445-test count is recorded full-suite evidence, not a newly rerun full suite for V17. No implementation code was changed.

Implementation repository: https://github.com/genaiworks/fssai-ra
Local source revision examined: 53595b8913c3fa19dfe388513515c238a1761e6c.

## Rebuilding the manuscript

The source/ directory contains the editable manuscripts, references, figure and deterministic Word builder. On macOS with Python, python-docx and Pillow, run `python source/build_release.py rebuilt`. The builder uses the system Arial fonts for its original enforcement diagram. Equivalent font and library versions are required for byte-identical output. Rendering the DOCX to PDF requires a compatible Word renderer; PDF bytes may vary between renderers. The implementation tests and original repository manuscript builder are separate from this V17 editorial build.

SHA256SUMS.txt records the distributed manuscript, PDF and source hashes. Earlier releases are preserved.
