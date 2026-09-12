"""Keep the public learning paths executable and honest."""

import re
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DOCS_INDEX = DOCS / "README.md"
START = ROOT / "docs" / "START_HERE.md"
LITERACY = ROOT / "docs" / "SYSTEM_LITERACY.md"


def _local_links(path: Path) -> list[Path]:
    links = re.findall(r"\[[^]]+\]\(([^)]+)\)", path.read_text(encoding="utf-8"))
    return [path.parent / link.split("#", 1)[0] for link in links
            if "://" not in link and not link.startswith("#")]


def test_learning_path_links_resolve():
    missing = [str(path) for source in (START, LITERACY)
               for path in _local_links(source) if not path.exists()]
    assert not missing, f"learning path contains broken local links: {missing}"


def test_all_five_system_literacies_are_taught_and_assessed():
    text = LITERACY.read_text(encoding="utf-8").lower()
    plain = " ".join(text.split())
    for name in ("data", "delegation", "verification", "escalation", "accountability"):
        assert f"{name} literacy" in text
    assert "assessment rubric" in text
    assert "no learner study has yet been conducted" in plain


def test_tour_reaches_the_requested_reference_stack_without_equating_it_to_proof():
    text = START.read_text(encoding="utf-8")
    plain = " ".join(text.split())
    for component in ("FastAPI", "Redis", "Apache Kafka", "PySpark", "Apache Iceberg", "data diode"):
        assert component in text
    assert "A Python interface cannot prove physical directionality" in plain


def test_tour_ends_with_transfer_not_repository_trivia():
    text = START.read_text(encoding="utf-8")
    assert "fssaira init my_domain" in text
    assert "You understand the repository when you can teach back this checklist" in text
    assert "distinguish tamper-evidence from truth, fairness" in text


def test_every_document_artifact_is_linked_from_the_documentation_map():
    """A file added under docs must be deliberately discoverable or removed."""
    index_targets = {
        target.split("#", 1)[0]
        for target in re.findall(
            r"\[[^]]+\]\(([^)]+)\)", DOCS_INDEX.read_text(encoding="utf-8")
        )
        if "://" not in target
    }
    artifacts = {
        path.relative_to(DOCS).as_posix()
        for path in DOCS.rglob("*")
        if path.is_file() and path != DOCS_INDEX
    }
    missing = sorted(artifacts - index_targets)
    assert not missing, f"docs/README.md does not link these documentation artifacts: {missing}"


def test_every_markdown_document_can_return_to_the_map():
    missing = []
    for path in DOCS.rglob("*.md"):
        if path == DOCS_INDEX:
            continue
        text = path.read_text(encoding="utf-8")
        if "**Documentation navigation:**" not in text:
            missing.append(path.relative_to(ROOT).as_posix())
    assert not missing, f"Markdown documents without common navigation: {missing}"


def test_every_guided_markdown_document_names_a_next_step():
    missing = []
    for path in DOCS.rglob("*.md"):
        if path in (DOCS_INDEX, DOCS / "GLOSSARY.md"):
            continue
        if "**Recommended next:**" not in path.read_text(encoding="utf-8"):
            missing.append(path.relative_to(ROOT).as_posix())
    assert not missing, f"Markdown documents without a recommended next step: {missing}"


def test_all_local_links_in_markdown_documents_resolve():
    broken = []
    for source in DOCS.rglob("*.md"):
        for target in re.findall(
            r"\[[^]]+\]\(([^)]+)\)", source.read_text(encoding="utf-8")
        ):
            if "://" in target or target.startswith(("#", "mailto:")):
                continue
            relative = target.split("#", 1)[0].strip("<>")
            if relative and not (source.parent / relative).exists():
                broken.append(
                    f"{source.relative_to(ROOT).as_posix()} -> {relative}"
                )
    assert not broken, "broken local documentation links:\n" + "\n".join(broken)


def test_interactive_documents_return_to_the_documentation_map():
    for relative in (
        "worksheet/index.html",
        "oversight/index.html",
        "presentation/slides.html",
    ):
        text = (DOCS / relative).read_text(encoding="utf-8")
        assert 'href="../README.md"' in text, f"{relative} cannot return to docs/README.md"


def test_formatted_abstract_uses_the_current_paper_title():
    title = (ROOT / "paper" / "form-ready-abstract.md").read_text(
        encoding="utf-8"
    ).splitlines()[0].removeprefix("# ")
    with ZipFile(DOCS / "extended-abstract.docx") as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")
    assert title in document_xml
