"""Review findings H4 and M5: a named test must be one pytest would actually run."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from fssaira.kernel.contract import (
    ContractError,
    _conformance_ids,
    resolve_test_locator,
    verify_bindings,
)


def _tests(tmp_path: Path, name: str, source: str) -> Path:
    (tmp_path / "tests").mkdir(exist_ok=True)
    path = tmp_path / "tests" / name
    path.write_text(textwrap.dedent(source))
    return path


def test_h4_a_file_pytest_does_not_collect_is_not_a_test(tmp_path):
    _tests(tmp_path, "helpers.py", "def test_x():\n    assert True\n")
    with pytest.raises(ContractError, match="does not collect"):
        resolve_test_locator("tests/helpers.py::test_x", root=tmp_path)


def test_h4_the_suffix_form_is_collected(tmp_path):
    _tests(tmp_path, "gate_test.py", "def test_x():\n    assert True\n")
    assert resolve_test_locator("tests/gate_test.py::test_x", root=tmp_path)


@pytest.mark.parametrize("decorator", [
    "@pytest.mark.skip(reason='later')", "@pytest.mark.skipif(True, reason='x')",
    "@pytest.mark.xfail", "@unittest.skip('no')",
])
def test_h4_a_skipped_or_xfailed_test_would_not_run(tmp_path, decorator):
    _tests(tmp_path, "test_marks.py", f"import pytest, unittest\n\n{decorator}\ndef test_x():\n    assert True\n")
    with pytest.raises(ContractError, match="would not run"):
        resolve_test_locator("tests/test_marks.py::test_x", root=tmp_path)


def test_h4_a_skip_on_the_enclosing_class_or_module_would_not_run(tmp_path):
    _tests(tmp_path, "test_class.py", """
        import pytest

        @pytest.mark.skip
        class TestGroup:
            def test_x(self):
                assert True
    """)
    with pytest.raises(ContractError, match="would not run"):
        resolve_test_locator("tests/test_class.py::TestGroup::test_x", root=tmp_path)
    _tests(tmp_path, "test_module.py", "import pytest\npytestmark = pytest.mark.skip\n\ndef test_x():\n    pass\n")
    with pytest.raises(ContractError, match="would not run"):
        resolve_test_locator("tests/test_module.py::test_x", root=tmp_path)


def test_h4_dunder_test_false_is_not_collected(tmp_path):
    _tests(tmp_path, "test_dunder.py", """
        class TestGroup:
            __test__ = False

            def test_x(self):
                assert True
    """)
    with pytest.raises(ContractError, match="would not run"):
        resolve_test_locator("tests/test_dunder.py::TestGroup::test_x", root=tmp_path)


def test_h4_a_parametrized_node_id_resolves_to_its_function(tmp_path):
    _tests(tmp_path, "test_param.py", "import pytest\n\n@pytest.mark.parametrize('v', [1])\ndef test_x(v):\n    pass\n")
    assert resolve_test_locator("tests/test_param.py::test_x[1]", root=tmp_path)


def _bindings(tmp_path: Path, locator: str) -> Path:
    (tmp_path / "contract" / "bindings").mkdir(parents=True, exist_ok=True)
    (tmp_path / "contract" / "bindings" / "core.yaml").write_text(yaml.safe_dump({"bindings": [
        {"requirements": ["R-1"], "mechanism": "unit_test", "locator": locator}]}))
    return tmp_path / "contract"


def test_h4_a_dot_slash_prefix_is_judged_as_a_test(tmp_path):
    _tests(tmp_path, "test_a.py", "def helper():\n    pass\n")
    assert verify_bindings(_bindings(tmp_path, "tests/test_a.py::helper"), root=tmp_path)
    assert verify_bindings(_bindings(tmp_path, "./tests/test_a.py::helper"), root=tmp_path)


def test_m5_a_conformance_id_only_in_a_skip_does_not_exist(tmp_path):
    source = tmp_path / "src" / "fssaira"
    source.mkdir(parents=True)
    (source / "conformance.py").write_text(textwrap.dedent("""
        class Suite:
            def run(self):
                if not self.bundle:
                    return [self._skip("CF-IB-01", "import", "IB-1", "t", "not supplied")]
                return [self._check("CF-IB-02", "import", "IB-2", "t", lambda: True)]
    """))
    assert _conformance_ids(tmp_path) == {"CF-IB-02"}
    assert verify_bindings(_bindings(tmp_path, "CF-IB-01"), root=tmp_path)
    assert not verify_bindings(_bindings(tmp_path, "CF-IB-02"), root=tmp_path)


def test_m5_the_repository_conformance_ids_are_all_registered_checks():
    root = Path(__file__).resolve().parents[2]
    ids = _conformance_ids(root)
    assert ids, "no registered conformance checks found"
    # Every CF-* id a binding cites must be one of these registered checks.
    assert verify_bindings(root / "contract", root=root) == []
