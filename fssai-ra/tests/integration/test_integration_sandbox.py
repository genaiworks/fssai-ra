"""Sandbox: bounded resources and no inherited secrets -- and its honest limit, executed."""
from __future__ import annotations

import os
import sys
import time

import pytest

pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX rlimits required")

from fssaira.integration.sandbox import (  # noqa: E402
    ISOLATION_STATEMENT,
    SandboxLimits,
    run_python,
)


def test_honest_limit_sandboxed_code_can_read_a_file_the_parent_user_can_read(tmp_path):
    secret_file = tmp_path / "parent-readable.txt"
    secret_file.write_text("SYNTHETIC-PARENT-FILE-CONTENT")
    result = run_python(f"print(open({str(secret_file)!r}).read())")
    assert result.returncode == 0
    assert "SYNTHETIC-PARENT-FILE-CONTENT" in result.stdout  # containment, not isolation
    assert result.security_boundary is False
    assert result.isolation == ISOLATION_STATEMENT
    assert "NOT a security boundary" in result.isolation
    import fssaira.integration.sandbox as module
    assert "NOT a security boundary" in module.__doc__


def test_no_inherited_environment_secrets(monkeypatch):
    monkeypatch.setenv("FSSAI_FAKE_SECRET", "SYNTHETIC-SECRET-DO-NOT-LEAK")
    result = run_python("import os, sys; print(dict(os.environ)); print(sys.flags.isolated, "
                        "sys.flags.no_site)")
    assert result.returncode == 0, result.stderr
    assert "SYNTHETIC-SECRET-DO-NOT-LEAK" not in result.stdout
    assert "FSSAI_FAKE_SECRET" not in result.stdout
    assert result.stdout.strip().splitlines()[-1] == "1 1"
    assert result.interpreter_flags == ("-I", "-S")


def test_runs_in_a_fresh_temporary_directory():
    result = run_python("import os; print(os.getcwd()); print(os.listdir('.'))")
    cwd = result.stdout.splitlines()[0]
    assert "fssaira-sandbox-" in cwd and cwd != os.getcwd()
    assert not os.path.exists(cwd)  # removed afterwards


def test_wall_clock_timeout_kills_the_process_group():
    code = ("import os, time\n"
            "pid = os.fork()\n"
            "if pid == 0:\n    time.sleep(60)\n    os._exit(0)\n"
            "print(pid, flush=True)\n"
            "time.sleep(60)\n")
    started = time.monotonic()
    result = run_python(code, limits=SandboxLimits(wall_clock_seconds=1.0, cpu_seconds=30))
    assert result.timed_out and result.signal_name == "SIGKILL"
    assert time.monotonic() - started < 15
    grandchild = int(result.stdout.split()[0])
    for _ in range(50):
        try:
            os.kill(grandchild, 0)
        except ProcessLookupError:
            break
        time.sleep(0.1)
    else:
        pytest.fail("grandchild survived the process-group kill")


def test_limits_applied_are_recorded_and_enforced_where_applied(tmp_path):
    result = run_python("print('ok')")
    applied = result.limits_applied
    assert set(applied) == {"cpu_seconds", "address_space_bytes", "data_bytes",
                            "file_size_bytes", "open_files", "core_bytes"}
    for name in ("cpu_seconds", "file_size_bytes", "open_files", "core_bytes"):
        assert applied[name]["applied"], (name, applied[name])
    for name, row in applied.items():
        if not row["applied"]:
            assert f"{name} not applied on this host" in result.notes
    if sys.platform == "darwin":
        print("macOS rlimits:", applied)


def test_cpu_limit_kills_a_busy_loop():
    result = run_python("while True:\n    pass\n",
                        limits=SandboxLimits(cpu_seconds=1, wall_clock_seconds=20))
    assert not result.timed_out
    assert result.signal_name in ("SIGXCPU", "SIGKILL")


def test_file_size_and_open_file_limits():
    code = ("try:\n"
            "    open('big.bin','wb').write(b'x' * (4 * 1024 * 1024))\n"
            "except OSError as e:\n    print('fsize', type(e).__name__)\n")
    result = run_python("import signal; signal.signal(signal.SIGXFSZ, signal.SIG_IGN)\n" + code,
                        limits=SandboxLimits(file_size_bytes=64 * 1024))
    assert "fsize" in result.stdout, (result.stdout, result.stderr)
    code = ("fs = []\n"
            "try:\n    [fs.append(open('f%d' % i, 'w')) for i in range(200)]\n"
            "except OSError as e:\n    print('nofile', len(fs))\n")
    result = run_python(code, limits=SandboxLimits(open_files=16))
    assert "nofile" in result.stdout and int(result.stdout.split()[1]) < 16


def test_output_is_captured_bounded():
    result = run_python("import sys\nsys.stdout.write('y' * 200000)\n",
                        limits=SandboxLimits(max_output_bytes=1000, file_size_bytes=1024 * 1024))
    assert result.stdout_truncated and len(result.stdout) == 1000
