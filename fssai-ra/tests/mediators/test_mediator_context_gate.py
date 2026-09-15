"""The Rule 2 facade names the gate; it never becomes a second gate."""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import fssaira.disclosure as disclosure
import fssaira.mediators.context_gate as facade
import fssaira.privacy_pipeline as privacy_pipeline

SOURCE = Path(facade.__file__)


def test_the_facade_re_exports_the_one_gate_implementation():
    assert facade.DisclosureGate is disclosure.DisclosureGate
    assert facade.DataLabel is disclosure.DataLabel
    assert facade.PrivacyGate is privacy_pipeline.PrivacyGate
    for name in facade.__all__:
        obj = getattr(facade, name)
        assert inspect.getmodule(obj) in (disclosure, privacy_pipeline), name


def test_the_facade_defines_no_logic_of_its_own():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    own = [node for node in tree.body
           if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    assert own == []


def test_release_takes_no_label_from_its_caller():
    """The output label is derived by the gate; release accepts none from a model."""
    params = inspect.signature(disclosure.DisclosureGate.release).parameters
    assert not {name for name in params if "label" in name or "classif" in name}
