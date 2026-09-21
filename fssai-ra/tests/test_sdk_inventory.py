"""The public interface contract must be verifiable without a manuscript."""
import json
from pathlib import Path

import pytest
from scripts.check_sdk_inventory import check


def test_public_sdk_inventory_matches_dispatch():
    assert check()['passed']


def test_inventory_rejects_a_missing_dispatch_entry(tmp_path):
    source = Path(__file__).resolve().parents[1] / 'profiles/tbc/education-passport.json'
    passport = json.loads(source.read_text())
    inventory = passport['interface_inventory'] if 'interface_inventory' in passport else passport['inventory']
    if isinstance(inventory, dict):
        inventory.pop(next(iter(inventory)))
    else:
        inventory.pop()
    destination = tmp_path / 'profiles/tbc/education-passport.json'
    destination.parent.mkdir(parents=True)
    destination.write_text(json.dumps(passport))
    with pytest.raises(ValueError):
        check(tmp_path)
