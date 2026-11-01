"""The ``tools.connectors`` package must never re-export its own siblings eagerly.

``tools/registry.py`` discovery imports ``tools.connectors.tool`` — taking the parent
package lock first, then the module lock — while other surfaces (``model_tools``,
``tui_gateway``) import the package itself. An eager ``__init__`` that imports ``tool``
makes those two lock orders invertible, and CPython reports the collision as
``_DeadlockError: deadlock detected by _ModuleLock('tools.connectors.tool')``; the losing
thread's import is abandoned, so the ``connections`` tool never registers in that process.

Both tests run in a subprocess: module locks are per-process, so an in-process assertion
would be satisfied by whatever this worker already imported.
"""

import subprocess
import sys
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Two threads, released together, importing the two entry points that real code uses:
# registry discovery takes the submodule, the RPC/tool surfaces take the package.
RACE_SCRIPT = textwrap.dedent(
    """
    import sys, threading

    errors = []
    barrier = threading.Barrier(2)

    def grab(target):
        barrier.wait()
        try:
            __import__(target)
        except BaseException as exc:  # a deadlock surfaces as _DeadlockError
            errors.append(f"{target}: {type(exc).__name__}: {exc}")

    threads = [
        threading.Thread(target=grab, args=("tools.connectors.tool",)),
        threading.Thread(target=grab, args=("tools.connectors",)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    deadlocks = [e for e in errors if "deadlock" in e.lower()]
    if deadlocks:
        print("DEADLOCK " + deadlocks[0])
        sys.exit(1)
    if errors:
        print("ERROR " + errors[0])
        sys.exit(2)
    print("ok")
    """
)

LAZY_SCRIPT = textwrap.dedent(
    """
    import sys

    import tools.connectors as package

    # The cycle edge: importing the boundary must not drag in the tool module.
    if "tools.connectors.tool" in sys.modules:
        print("EAGER tools.connectors.tool was imported by the package __init__")
        sys.exit(1)

    # …while the documented surface still resolves on first touch.
    from tools.connectors import (
        CONNECTOR_BATCH_SENTINEL,
        MANAGE_CONNECTIONS_SCHEMA,
        connector_describe,
        connector_search_hits,
        connectors_available,
        dispatch_connector_batch,
        dispatch_connector_call,
        is_connector_name,
        manage_connections,
    )

    expected = set(package.__all__)
    resolved = {
        "CONNECTOR_BATCH_SENTINEL",
        "MANAGE_CONNECTIONS_SCHEMA",
        "connector_describe",
        "connector_search_hits",
        "connectors_available",
        "dispatch_connector_batch",
        "dispatch_connector_call",
        "is_connector_name",
        "manage_connections",
    }
    if resolved != expected:
        print(f"__all__ drift: {sorted(expected ^ resolved)}")
        sys.exit(1)

    for name in package.__all__:
        getattr(package, name)

    try:
        package.definitely_not_exported
    except AttributeError:
        pass
    else:
        print("unknown attribute did not raise AttributeError")
        sys.exit(1)

    print("ok")
    """
)


def _run(script: str, attempts: int = 1) -> list:
    """Run ``script`` in fresh interpreters; return the failing outputs."""
    failures = []
    for _ in range(attempts):
        proc = subprocess.run(
            [sys.executable, "-c", script],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=180,
        )
        if proc.returncode != 0:
            failures.append((proc.stdout + proc.stderr).strip())
    return failures


def test_package_import_is_lazy_and_keeps_its_surface():
    failures = _run(LAZY_SCRIPT)
    assert not failures, failures[0]


def test_racing_package_and_submodule_imports_do_not_deadlock():
    # Three fresh interpreters: the pre-fix package deadlocked in every single one, so a
    # green here is the regression tripwire, not a flake sample.
    failures = _run(RACE_SCRIPT, attempts=3)
    assert not failures, failures[0]
