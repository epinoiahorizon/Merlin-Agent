"""Regression tests for the conftest live-system guard's argv handling.

The guard must treat only argv[0] of a list/tuple command as the executable
(arguments are data: a file named ``skill`` is not the ``skill`` binary),
while still scanning every token of wrapper invocations like ``bash -c``.
All blocked-case commands use patterns that match no real process, so a
guard regression cannot kill anything.
"""

import os
import subprocess
import sys

import pytest


def test_argv_arguments_are_not_treated_as_executables(tmp_path):
    """A file argument whose basename is a killer name must not trip the
    guard (the path contains "merlin" via the pytest tmp root)."""
    target = tmp_path / "skill"
    target.write_text("just a filename\n")
    result = subprocess.run(["cat", str(target)], capture_output=True, text=True)
    assert result.returncode == 0
    assert "just a filename" in result.stdout


def test_direct_killer_argv_is_still_blocked():
    with pytest.raises(RuntimeError, match="live-system guard"):
        subprocess.run(["pkill", "-f", "merlin-guard-regression-nomatch"])


def test_wrapped_killer_command_is_still_blocked():
    """argv[0]-only scanning must not exempt commands hidden behind a
    shell wrapper."""
    with pytest.raises(RuntimeError, match="live-system guard"):
        subprocess.run(["bash", "-c", "pkill -f merlin-guard-regression-nomatch"])


def test_env_wrapped_killer_command_is_still_blocked():
    with pytest.raises(RuntimeError, match="live-system guard"):
        subprocess.run(["env", "GUARD_TEST=1", "pkill", "-f", "merlin-guard-regression-nomatch"])


def test_gateway_start_inside_a_container_exec_is_not_blocked():
    """``docker exec <ctr> merlin gateway start`` launches the gateway INSIDE the container,
    where it cannot reach the host's systemd unit or webhook port; tests/docker/ depends on it.
    The binary is a stub so the argv stays exact without needing a Docker daemon."""
    import os
    import stat

    stub_dir = os.path.join(os.environ["MERLIN_HOME"], "stub-bin")
    os.makedirs(stub_dir, exist_ok=True)
    stub = os.path.join(stub_dir, "docker")
    with open(stub, "w") as fh:
        fh.write("#!/bin/sh\nexit 0\n")
    os.chmod(stub, os.stat(stub).st_mode | stat.S_IXUSR)
    result = subprocess.run(
        [stub, "exec", "-u", "merlin", "ctr", "sh", "-c", "merlin -p prof gateway start"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_gateway_start_on_the_host_is_still_blocked():
    with pytest.raises(RuntimeError, match="REAL.*gateway runtime"):
        subprocess.run(["python", "-m", "merlin_cli.main", "gateway", "start"])


def test_custom_home_tmpdir_is_relocated_before_pytest_uses_it(tmp_path):
    home = tmp_path / "custom-home"
    scratch = home / "cache" / "scratch"
    scratch.mkdir(parents=True)
    env = dict(os.environ, MERLIN_HOME=str(home), TMPDIR=str(scratch))
    env.pop("MERLIN_SCRATCH_DIR", None)
    result = subprocess.run(
        [sys.executable, "-c", "import tempfile, tests.conftest; print(tempfile.gettempdir())"],
        env=env, capture_output=True, text=True, check=True,
    )
    assert not result.stdout.strip().startswith(str(home))


def test_repointing_home_cannot_move_the_guarded_root(tmp_path):
    """The guarded root comes from the OS account, not from $HOME.

    The previous version of this test assumed a disposable $HOME would *become* the guarded root, and
    that conftest would then strip a TMPDIR inside it. That stopped being true when
    ``_real_platform_state_root()`` was hardened to ignore the environment — a root an environment
    variable can move is exactly the isolation escape it exists to prevent — so the test asserted a
    design the code had deliberately abandoned, and it failed on every machine with a real install.
    Assert the invariant instead: repointing HOME must not move the root.
    """
    operator_home = tmp_path / "operator"
    (operator_home / ".merlin" / "cache" / "scratch").mkdir(parents=True)
    env = dict(os.environ, HOME=str(operator_home), USERPROFILE=str(operator_home))
    env.pop("MERLIN_HOME", None)
    env.pop("MERLIN_SCRATCH_DIR", None)
    result = subprocess.run(
        [sys.executable, "-c",
         "from merlin_state_guard import _real_platform_state_root as r; print(r())"],
        env=env, capture_output=True, text=True, check=True,
    )
    root = result.stdout.strip()
    assert root, "guarded root resolved to nothing"
    assert not root.startswith(str(operator_home)), f"guarded root followed $HOME: {root}"
