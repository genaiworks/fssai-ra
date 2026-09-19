"""Process-level containment for generated code. NOT a security boundary.

READ THIS FIRST. This module runs generated Python in a separate interpreter
process with bounded resources and no inherited environment. That is
**process-level containment, NOT a security boundary against hostile code
running as the same OS user**: the child can read every file that user can
read, write where that user can write (bounded only by the file-size limit),
open network sockets, and signal that user's other processes. Container, VM,
or separate-user isolation (with no credentials, mounts, or network it does not
need) is a **deployment obligation**. The repository's own probe
(``audit/host-isolation-probe.json``) records a same-OS-user subprocess reading
the synthetic database, and ``tests/integration/test_integration_sandbox.py``
executes the same limit against a file in the test's temporary directory.

What it does provide:

* a separate interpreter started with ``-I -S`` (isolated mode: no user site,
  no ``PYTHON*`` environment variables, no ``site`` import);
* an **empty environment** -- no inherited secrets from the parent's variables;
* a fresh temporary working directory, removed afterwards;
* POSIX rlimits set in the child before ``exec``: CPU seconds, address space,
  data segment, file size, open files, core size. The outcome of each
  ``setrlimit`` is reported to the parent over a pipe *before* the generated code
  runs, so the record of which limits actually applied is not self-reported by
  that code. On macOS, address-space and data limits are commonly refused by the
  kernel; they are recorded as not applied rather than assumed;
* a wall-clock timeout that kills the whole process group;
* stdout and stderr captured to files (bounded by the file-size limit) and read
  back truncated to a maximum.

Must NOT / residual risk
------------------------
* Must NOT be described or relied on as isolation from hostile code.
* Must NOT be given secrets through arguments, files in its working directory,
  or readable paths; the empty environment protects only environment variables.
* Residual: no network restriction, no filesystem restriction, no syscall
  filtering, no user separation. Memory limits may not apply on this platform
  (see :attr:`SandboxResult.limits_applied`). ``preexec_fn`` is not safe in a
  multi-threaded parent on every platform.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field

ISOLATION_STATEMENT = (
    "process-level containment only; NOT a security boundary against hostile code running as "
    "the same OS user (it can read that user's files and open sockets). Container, VM or "
    "separate-user isolation is a deployment obligation."
)

INTERPRETER_FLAGS: tuple[str, ...] = ("-I", "-S")


@dataclass(frozen=True)
class SandboxLimits:
    cpu_seconds: int = 2
    address_space_bytes: int = 512 * 1024 * 1024
    data_bytes: int = 512 * 1024 * 1024
    file_size_bytes: int = 1024 * 1024
    open_files: int = 32
    wall_clock_seconds: float = 5.0
    max_output_bytes: int = 64 * 1024


@dataclass(frozen=True)
class SandboxResult:
    returncode: int | None
    stdout: str
    stderr: str
    stdout_truncated: bool
    stderr_truncated: bool
    timed_out: bool
    signal_name: str | None
    wall_seconds: float
    limits_requested: dict
    limits_applied: dict
    interpreter_flags: tuple[str, ...]
    environment_keys: tuple[str, ...]
    #: Always False. Present so no caller can mistake this result for isolation evidence.
    security_boundary: bool = False
    isolation: str = ISOLATION_STATEMENT
    notes: tuple[str, ...] = field(default_factory=tuple)


def _rlimit_plan(limits: SandboxLimits) -> list[tuple[str, str, int]]:
    return [
        ("cpu_seconds", "RLIMIT_CPU", int(limits.cpu_seconds)),
        ("address_space_bytes", "RLIMIT_AS", int(limits.address_space_bytes)),
        ("data_bytes", "RLIMIT_DATA", int(limits.data_bytes)),
        ("file_size_bytes", "RLIMIT_FSIZE", int(limits.file_size_bytes)),
        ("open_files", "RLIMIT_NOFILE", int(limits.open_files)),
        ("core_bytes", "RLIMIT_CORE", 0),
    ]


def run_python(code: str, *, limits: SandboxLimits | None = None,
               python: str | None = None) -> SandboxResult:
    """Run ``code`` under process-level containment. Read the module docstring."""
    if os.name != "posix":
        raise RuntimeError("the sandbox requires POSIX rlimits and process groups")
    import resource

    limits = limits if limits is not None else SandboxLimits()
    plan = _rlimit_plan(limits)
    workdir = tempfile.mkdtemp(prefix="fssaira-sandbox-")
    capture = tempfile.mkdtemp(prefix="fssaira-sandbox-out-")
    script = os.path.join(workdir, "main.py")
    with open(script, "w", encoding="utf-8") as handle:
        handle.write(code)
    report_r, report_w = os.pipe()  # both ends close-on-exec

    def apply_limits() -> None:  # runs in the child, after fork, before exec
        outcome = {}
        for name, attr, value in plan:
            const = getattr(resource, attr, None)
            if const is None:
                outcome[name] = {"applied": False, "error": "unsupported"}
                continue
            try:
                resource.setrlimit(const, (value, value))
                soft, hard = resource.getrlimit(const)
                outcome[name] = {"applied": soft == value and hard == value, "soft": soft}
            except (ValueError, OSError) as exc:
                outcome[name] = {"applied": False, "error": type(exc).__name__}
        os.write(report_w, json.dumps(outcome).encode())

    started = time.monotonic()
    timed_out = False
    with open(os.path.join(capture, "stdout"), "wb") as out, \
            open(os.path.join(capture, "stderr"), "wb") as err:
        try:
            proc = subprocess.Popen(
                [python or sys.executable, *INTERPRETER_FLAGS, script], cwd=workdir, env={},
                stdin=subprocess.DEVNULL, stdout=out, stderr=err, close_fds=True,
                start_new_session=True, preexec_fn=apply_limits,
            )
        finally:
            os.close(report_w)
        try:
            proc.wait(timeout=limits.wall_clock_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            with _suppress():
                os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
        with _suppress():
            os.killpg(proc.pid, signal.SIGKILL)  # reap any process the code left behind
    elapsed = time.monotonic() - started
    chunks = []
    while True:
        block = os.read(report_r, 65536)
        if not block:
            break
        chunks.append(block)
    os.close(report_r)
    applied = json.loads(b"".join(chunks) or b"{}")

    def bounded(name: str) -> tuple[str, bool]:
        with open(os.path.join(capture, name), "rb") as handle:
            data = handle.read(limits.max_output_bytes + 1)
        return (data[:limits.max_output_bytes].decode("utf-8", errors="replace"),
                len(data) > limits.max_output_bytes)

    stdout, out_trunc = bounded("stdout")
    stderr, err_trunc = bounded("stderr")
    shutil.rmtree(workdir, ignore_errors=True)
    shutil.rmtree(capture, ignore_errors=True)
    code_ = proc.returncode
    signal_name = None
    if code_ is not None and code_ < 0:
        try:
            signal_name = signal.Signals(-code_).name
        except ValueError:
            signal_name = f"SIG{-code_}"
    notes = tuple(f"{name} not applied on this host" for name, row in sorted(applied.items())
                  if not row.get("applied"))
    return SandboxResult(
        returncode=code_, stdout=stdout, stderr=stderr, stdout_truncated=out_trunc,
        stderr_truncated=err_trunc, timed_out=timed_out, signal_name=signal_name,
        wall_seconds=elapsed, limits_requested={name: value for name, _a, value in plan}
        | {"wall_clock_seconds": limits.wall_clock_seconds,
           "max_output_bytes": limits.max_output_bytes},
        limits_applied=applied, interpreter_flags=INTERPRETER_FLAGS, environment_keys=(),
        notes=notes,
    )


class _suppress:
    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None,
                 tb: object) -> bool:
        return exc_type is not None and issubclass(exc_type, (ProcessLookupError,
                                                              PermissionError))


__all__ = ["INTERPRETER_FLAGS", "ISOLATION_STATEMENT", "SandboxLimits", "SandboxResult",
           "run_python"]
