"""Pytest fixtures for the wf debug-bridge tests.

Launches wf_game in a subprocess with the bridge enabled, on a per-session
basis. Skips the whole module if no DISPLAY is available — wf_game requires
an X server to run (no headless mode yet).
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from debug_bridge_client import BridgeClient

REPO_ROOT = Path(__file__).resolve().parent.parent
WF_GAME   = Path(os.environ.get("WF_GAME", REPO_ROOT / "engine" / "wf_game"))  # or a container-built engine
GAME_CWD  = REPO_ROOT / "wfsource" / "source" / "game"
LIB_DIR   = REPO_ROOT / "engine" / "libs"
LEVEL     = REPO_ROOT / "wflevels" / "qbert_practice-standalone.iff"

# Use a non-default port so we don't collide with a Blender session.
BRIDGE_PORT = 7778


@pytest.fixture(scope="session")
def bridge():
    if not WF_GAME.exists():
        pytest.skip(f"wf_game not built: {WF_GAME} missing (run task build)")
    if not LEVEL.exists():
        pytest.skip(f"qbert_practice level missing: {LEVEL}")
    if not os.environ.get("DISPLAY"):
        pytest.skip("no DISPLAY — wf_game requires X")

    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = f"{LIB_DIR}:{env.get('LD_LIBRARY_PATH', '')}"

    log_path = REPO_ROOT / "tests" / ".wf_game.log"
    log_fp = open(log_path, "w")
    proc = subprocess.Popen(
        [str(WF_GAME), f"-L{LEVEL}",
         "--debug-port", str(BRIDGE_PORT),
         "--debug-bind", "127.0.0.1"],
        cwd=str(GAME_CWD),
        env=env,
        stdout=log_fp,
        stderr=subprocess.STDOUT,
    )

    client: BridgeClient | None = None
    try:
        # The engine boots quickly; the bridge listener comes up after init.
        client = BridgeClient("127.0.0.1", BRIDGE_PORT, timeout=15.0)
        # Sanity: ping/pong.
        client.ping()
        if client.wait_for(lambda m: m.get("op") == "pong", timeout=2.0) is None:
            pytest.fail("no pong from bridge")
        yield client
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2.0)


# ---------------------------------------------------------------------------
# Build-output prerequisites.
#
# Several suites compile or run things that no checkout contains: the Rust tools' cargo
# outputs and the cooked Planted Tank level. A fresh checkout or worktree used to fail
# those suites with a bare linker error or CalledProcessError. A suite that names one of
# these outputs is now skipped, with the command that produces it, when it is missing.
# Suites that build their own tools with cargo are left alone.
# ---------------------------------------------------------------------------
BUILD_OUTPUTS = {
    "wf_attr_edit/target/release/libwf_attr_edit.a": "task build-test-tools",
    "wf_attr_edit/target/release/catalog": "task build-test-tools",
    "oas2oad-rs/target/release/oas2oad": "task build-test-tools",
    "cdpack-rs/target/release/cdpack": "task build-test-tools",
}
_module_needs: dict = {}


def _needs(path: Path) -> list:
    if path not in _module_needs:
        source = path.read_text()
        built_by_the_test = "'cargo'" in source or '"cargo"' in source
        _module_needs[path] = [] if built_by_the_test else [
            (fragment, command) for fragment, command in BUILD_OUTPUTS.items() if fragment in source]
    return _module_needs[path]


def pytest_collection_modifyitems(config, items):
    for item in items:
        for fragment, command in _needs(Path(str(item.fspath))):
            located = [p for p in (REPO_ROOT / "wftools", REPO_ROOT / "wflevels") if (p / fragment).exists()]
            if not located:
                item.add_marker(pytest.mark.skip(reason=f"missing build output {fragment}: run `{command}`"))
                break


# ---------------------------------------------------------------------------
# Per-module isolation of level-local modules.
#
# Level suites import their level's helpers by bare name after a sys.path.insert
# (`import timeline`, `from config import ...`, `import forth`), and several levels
# ship a module of the same name. Python caches an import by name, so the first level
# collected won: a later level's `import timeline` silently got the wrong file and its
# collection died with an AttributeError or ImportError (and, since collection errors
# abort the run, so did every `-k` filter). `--import-mode=importlib` does not help:
# it changes how *test* files are imported, not these bare imports.
#
# Each test module is therefore collected against a clean slate of repo-local modules
# (anything whose file lives in the repo outside tests/: level and tool directories,
# docs/ poster generators, ...). The modules it brought in,
# and the sys.path it ended collection with, are replayed around each of its tests, so
# a lazy `from config import ...` inside a test body resolves to the same file the
# module-level import did. sys.path itself keeps accumulating during collection, as it
# always has: a suite may import a sibling test module that did the path insert.
# ---------------------------------------------------------------------------
_TESTS_DIR = Path(__file__).resolve().parent
_isolated: dict = {}   # test module path -> (sys.path at the end of its collection, its local modules)


def _local_modules() -> dict:
    found = {}
    for name, mod in list(sys.modules.items()):
        origin = getattr(mod, "__file__", None)
        if origin:
            parents = Path(origin).resolve().parents
            if REPO_ROOT in parents and _TESTS_DIR not in parents:
                found[name] = mod
    return found


def _swap_in(local: dict) -> None:
    for name in _local_modules():
        del sys.modules[name]
    sys.modules.update(local)


@pytest.hookimpl(hookwrapper=True)
def pytest_make_collect_report(collector):
    if not isinstance(collector, pytest.Module):
        yield
        return
    outside = _local_modules()
    _swap_in({})
    yield
    _isolated[collector.path] = (list(sys.path), _local_modules())
    _swap_in(outside)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    entry = _isolated.get(item.path)
    if entry is None:
        yield
        return
    outside, path = _local_modules(), list(sys.path)
    _swap_in(entry[1])
    sys.path[:] = entry[0]
    yield
    entry[1].update(_local_modules())   # keep what a test imported lazily for its siblings
    _swap_in(outside)
    sys.path[:] = path
