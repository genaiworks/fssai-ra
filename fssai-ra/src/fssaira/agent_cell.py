"""One contained cell per agent: a hardened container spec, and a probe run inside it.

:mod:`fssaira.isolation` measures a host. A swarm needs more: each agent in its
own cell, so one compromised worker cannot read another's memory, reuse its
credentials or share its network. This module builds that cell for any container
runtime that accepts ``docker run`` arguments, and does not trust the spec to mean
what it says: it runs a probe *inside* the cell and measures each property from
where the agent would stand.

The cell is:

* a read-only root filesystem with a small ``noexec`` scratch ``/tmp``;
* every Linux capability dropped, and ``no-new-privileges``;
* an unprivileged, non-root user;
* no network at all (or a named internal network that reaches only the gate);
* process, memory and CPU limits;
* no host mounts, and a process started with an empty environment (``env -i``),
  so neither the host nor the image leaves anything ambient to inherit.

``verify_cell`` turns the probe's observations into the same three outcomes the
host gate uses. A property the probe could not observe is not satisfied, and a
cell with any unsatisfied property is refused (``CELL_NOT_ISOLATED``).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass

REQUIREMENTS = ("non_root_identity", "no_capabilities", "read_only_root", "no_egress",
                "no_cloud_metadata", "no_ambient_credentials")

#: Runs inside the cell with only the standard library. Prints one JSON object.
PROBE = r"""
import json, os, re, socket
def reach(host, port):
    try:
        socket.create_connection((host, port), timeout=2).close()
        return True
    except OSError:
        return False
cap = "unknown"
try:
    for line in open("/proc/self/status"):
        if line.startswith("CapEff:"):
            cap = line.split()[1]
except OSError:
    pass
try:
    open("/usr/.fssaira-probe", "w").close()
    writable = True
except OSError:
    writable = False
print(json.dumps({
    "uid": os.getuid(), "cap_eff": cap, "root_writable": writable,
    "egress": reach("1.1.1.1", 53) or reach("8.8.8.8", 53),
    "metadata": reach("169.254.169.254", 80),
    "credential_env": sorted(k for k in os.environ
                             if re.search(r"KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL", k, re.I)),
}))
"""


class CellNotIsolated(RuntimeError):
    """A cell failed a containment property measured from inside it."""


@dataclass(frozen=True)
class CellSpec:
    agent: str
    image: str
    user: str = "65534:65534"
    network: str = "none"
    memory: str = "256m"
    cpus: str = "0.5"
    pids: int = 64

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,62}", self.agent):
            raise ValueError("agent identifiers for cells are 1-63 safe characters")

    def run_args(self) -> list[str]:
        return ["run", "--rm", "--name", f"fssaira-cell-{self.agent}",
                "--label", f"fssaira.agent={self.agent}",
                "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m",
                "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                "--user", self.user, "--network", self.network,
                "--pids-limit", str(self.pids), "--memory", self.memory, "--cpus", self.cpus,
                "--entrypoint", "env", self.image]

    def command(self, *argv: str) -> list[str]:
        """Run ``argv`` in the cell with an empty environment.

        Images declare environment variables of their own (base images often set
        signing-key fingerprints and similar), and ``docker run`` cannot unset
        them. ``env -i`` starts the agent's process with nothing but ``PATH``.
        """
        return [*self.run_args(), "-i", "PATH=/usr/local/bin:/usr/bin:/bin", *argv]


def verify_cell(observed: dict) -> dict:
    """Turn inside-the-cell observations into satisfied / violated / not_measurable."""
    def outcome(ok):
        return "not_measurable" if ok is None else ("satisfied" if ok else "violated")

    cap = observed.get("cap_eff")
    results = {
        "non_root_identity": outcome(None if observed.get("uid") is None else observed["uid"] != 0),
        "no_capabilities": outcome(None if cap in (None, "unknown") else int(cap, 16) == 0),
        "read_only_root": outcome(None if "root_writable" not in observed else not observed["root_writable"]),
        "no_egress": outcome(None if "egress" not in observed else not observed["egress"]),
        "no_cloud_metadata": outcome(None if "metadata" not in observed else not observed["metadata"]),
        "no_ambient_credentials": outcome(None if "credential_env" not in observed
                                          else not observed["credential_env"]),
    }
    return {"requirements": results,
            "isolated": all(value == "satisfied" for value in results.values())}


def probe_cell(spec: CellSpec, *, runtime: str = "docker", timeout: float = 60) -> dict:
    """Launch the cell, run the probe inside it, and refuse it unless every property holds."""
    binary = shutil.which(runtime)
    if binary is None:
        raise CellNotIsolated(f"CELL_RUNTIME_UNAVAILABLE: {runtime} is not installed")
    run = subprocess.run([binary, *spec.command("python3", "-c", PROBE)], capture_output=True, text=True,
                         timeout=timeout)
    if run.returncode != 0:
        raise CellNotIsolated(f"CELL_PROBE_FAILED: {run.stderr.strip()[-300:]}")
    observed = json.loads(run.stdout.strip().splitlines()[-1])
    verdict = {"agent": spec.agent, "observed": observed, **verify_cell(observed)}
    if not verdict["isolated"]:
        failed = sorted(k for k, v in verdict["requirements"].items() if v != "satisfied")
        raise CellNotIsolated("CELL_NOT_ISOLATED: " + ", ".join(failed))
    return verdict


__all__ = ["PROBE", "REQUIREMENTS", "CellNotIsolated", "CellSpec", "probe_cell", "verify_cell"]
