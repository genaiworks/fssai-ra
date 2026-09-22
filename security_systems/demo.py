"""Clone and run: ``python demo.py``. No install, no network, no API key, no GPU.

Needs Python 3.10+ with ``pyyaml`` and ``cryptography`` (``pip install -e .`` installs
both). Arguments pass straight through to ``trustkernel demo``, for example
``python demo.py --scene 2`` or ``python demo.py --world education``.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from trustkernel.cli import main  # noqa: E402

raise SystemExit(main(["demo", *sys.argv[1:]]))
