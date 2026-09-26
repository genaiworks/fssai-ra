"""One contained cell per agent, measured from inside the cell."""
import shutil
import subprocess

import pytest

from fssaira.agent_cell import REQUIREMENTS, CellNotIsolated, CellSpec, probe_cell, verify_cell

IMAGE = "fssaira-platform:local"
ISOLATED = {"uid": 65534, "cap_eff": "0000000000000000", "root_writable": False, "egress": False,
            "metadata": False, "credential_env": []}


def test_the_cell_spec_drops_everything_ambient():
    args = CellSpec("worker-a", IMAGE).run_args()
    for flag in ("--read-only", "--cap-drop", "ALL", "no-new-privileges", "--network", "none",
                 "--pids-limit", "--memory", "--cpus"):
        assert flag in args
    assert args[args.index("--user") + 1] == "65534:65534"
    assert not any(a in ("-v", "--volume", "--mount", "--privileged", "--env-file") for a in args)
    command = CellSpec("worker-a", IMAGE).command("python3", "-V")
    assert command[len(args):] == ["-i", "PATH=/usr/local/bin:/usr/bin:/bin", "python3", "-V"]
    assert args[args.index("--entrypoint") + 1] == "env"


def test_unsafe_agent_identifiers_are_refused():
    with pytest.raises(ValueError):
        CellSpec("../../etc", IMAGE)


def test_every_property_must_be_observed_and_satisfied():
    assert verify_cell(ISOLATED) == {"requirements": dict.fromkeys(REQUIREMENTS, "satisfied"),
                                     "isolated": True}
    for key, bad in (("uid", 0), ("cap_eff", "00000000a80425fb"), ("root_writable", True),
                     ("egress", True), ("metadata", True), ("credential_env", ["API_TOKEN"])):
        assert verify_cell({**ISOLATED, key: bad})["isolated"] is False, key
    unmeasured = {k: v for k, v in ISOLATED.items() if k != "egress"}
    result = verify_cell(unmeasured)
    assert result["requirements"]["no_egress"] == "not_measurable" and result["isolated"] is False


def docker_ready():
    if shutil.which("docker") is None:
        return False
    return subprocess.run(["docker", "image", "inspect", IMAGE], capture_output=True).returncode == 0


needs_docker = pytest.mark.skipif(not docker_ready(), reason=f"needs docker and the {IMAGE} image")


@needs_docker
def test_a_real_cell_is_isolated_when_measured_from_inside():
    verdict = probe_cell(CellSpec("cell-test-a", IMAGE))
    assert verdict["isolated"] is True
    assert verdict["observed"]["uid"] == 65534 and verdict["observed"]["egress"] is False


@needs_docker
def test_a_cell_running_as_root_is_refused():
    with pytest.raises(CellNotIsolated, match="CELL_NOT_ISOLATED: non_root_identity"):
        probe_cell(CellSpec("cell-test-b", IMAGE, user="0:0"))
