"""Keep public runtime validation independent of private manuscript archives."""
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1]
MANUSCRIPT_MODULES = {
    "test_paper_revision_build.py", "test_submission.py",
    "test_conference_paper_alignment.py", "test_tbc_alignment.py",
}
ARCHIVE_INPUTS = (
    "paper/extended-abstract.md", "paper/form-ready-abstract.md",
    "paper/composition-supplement.md", "paper/trust-by-construction.md",
    "paper/foundation-claims.json", "paper/tbc-v11/implementation.json",
    "paper/tbc-v11/TBC_v11.docx", "paper/tbc-v12/implementation.json",
    "paper/tbc-v12/TBC_v12_Engineering_Revision.docx",
    "paper/tbc-v13/implementation.json", "paper/tbc-v13/TBC_v13_Frontier_Threat_Revision.docx",
    "paper/tbc-v14/implementation.json", "paper/tbc-v14/TBC_v14_Developer_Security_Revision.docx",
    "paper/tbc-v15/implementation.json", "paper/tbc-v15/revision-content.json",
    "docs/extended-abstract.docx",
)


def pytest_addoption(parser):
    parser.addoption("--include-manuscripts", action="store_true", default=False,
                     help="Include private manuscript checks; missing archive inputs are an error")


def pytest_configure(config):
    config.addinivalue_line("markers", "manuscript: requires local-only historical paper artifacts")
    if config.getoption("--include-manuscripts"):
        missing = [p for p in ARCHIVE_INPUTS if not (APP / p).is_file()]
        if missing:
            raise pytest.UsageError(
                "Private manuscript checks requested, but archive inputs are missing:\n  "
                + "\n  ".join(missing)
                + "\nPublic runtime checks: python -m pytest (without --include-manuscripts)."
            )


def pytest_ignore_collect(collection_path, config):
    if not config.getoption("--include-manuscripts"):
        return collection_path.name in MANUSCRIPT_MODULES
    return None


def pytest_collection_modifyitems(config, items):
    if config.getoption("--include-manuscripts"):
        return
    excluded = [item for item in items if item.get_closest_marker("manuscript")]
    if excluded:
        items[:] = [item for item in items if item not in excluded]
        config.hook.pytest_deselected(items=excluded)


def pytest_terminal_summary(terminalreporter, config):
    if not config.getoption("--include-manuscripts"):
        terminalreporter.write_line(
            "Scope: public runtime/docs/evidence checks. Private manuscript checks are excluded; "
            "run make manuscript-check only with the local archive."
        )
