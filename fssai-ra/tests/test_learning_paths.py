"""Keep the public learning paths executable and honest."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
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
