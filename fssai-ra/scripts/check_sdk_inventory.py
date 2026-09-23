"""Check the public Passport/SDK/dispatcher contract without manuscript files."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fssaira.tbc.contracts import PRIMITIVES, Passport  # noqa: E402
from fssaira.tbc.runtime import SCHEMAS  # noqa: E402


def check(root=ROOT):
    passport = Passport.parse(json.loads((root / "profiles/tbc/education-passport.json").read_text()))
    if set(passport.inventory) != set(SCHEMAS) or set(SCHEMAS) != PRIMITIVES:
        raise ValueError("Passport, SDK and dispatch inventory disagree")
    return {"passed": True, "primitives_bound": len(SCHEMAS),
            "scope": "public interface inventory; behavioral tests run separately"}


if __name__ == "__main__":
    print(json.dumps(check(), indent=2))
