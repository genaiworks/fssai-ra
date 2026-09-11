from pathlib import Path

from scripts.check_submission import validate


def test_form_ready_abstract_fits_every_form_limit():
    text = Path("paper/form-ready-abstract.md").read_text(encoding="utf-8")
    report = validate(text)
    assert report["valid"], report


def test_checker_rejects_a_missing_section():
    assert not validate("## Introduction\n" + "word " * 210)["valid"]
