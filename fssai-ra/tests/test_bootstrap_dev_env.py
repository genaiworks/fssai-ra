import json
import subprocess
import sys
from pathlib import Path


def test_bootstrap_generates_complete_distinct_local_identities(tmp_path):
    (tmp_path / "deploy").mkdir()
    script = Path(__file__).parents[1] / "scripts" / "bootstrap_dev_env.py"

    subprocess.run([sys.executable, str(script)], cwd=tmp_path, check=True)

    values = dict(
        line.split("=", 1)
        for line in (tmp_path / "deploy" / ".env").read_text().splitlines()
        if line and not line.startswith("#")
    )
    identities = json.loads(values["FSSAI_AUTH_TOKENS_JSON"])
    officers = [
        item["subject"] for item in identities.values()
        if "student_support_officer" in item["roles"]
    ]
    assert sorted(officers) == ["officer.one", "officer.two"]
    assert len(identities) == 4
    assert values["FSSAI_MODEL_FALLBACK"] == "deny"
    assert values["FSSAI_EVIDENCE_TOKEN"] != values["FSSAI_APPROVAL_SIGNING_KEY"]
