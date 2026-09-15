"""The joined workflow's JSON boundary rejects every non-finite number.

Found by the GenAI integration-contract work: ``strict_json`` hooked only
``parse_constant``, so the NaN and Infinity literals were refused, but an
overflowing literal such as ``1e999`` parsed to ``inf``.
"""
from __future__ import annotations

import json

import pytest

from fssaira.joined_workflow import strict_json


@pytest.mark.parametrize("literal", ["1e999", "-1e999", "1E400", "9" * 400 + ".0e10", "NaN", "Infinity", "-Infinity"])
def test_non_finite_numbers_are_refused(literal):
    with pytest.raises(ValueError, match="NONFINITE"):
        strict_json(f'{{"value": {literal}}}')


def test_nested_non_finite_numbers_are_refused():
    with pytest.raises(ValueError, match="NONFINITE"):
        strict_json('{"op": "propose", "args": {"scores": [1.5, 2e308, 1e999]}}')


@pytest.mark.parametrize("literal", ["0.5", "-2.25e10", "1e308", "123456789012345678901234567890"])
def test_finite_numbers_still_parse(literal):
    assert strict_json(f'{{"value": {literal}}}')["value"] == json.loads(literal)


def test_duplicate_fields_and_size_limit_still_hold():
    with pytest.raises(ValueError, match="DUPLICATE_FIELD"):
        strict_json('{"op": "read", "op": "propose"}')
    with pytest.raises(ValueError, match="REQUEST_TOO_LARGE"):
        strict_json('{"pad": "' + "x" * 17000 + '"}')
