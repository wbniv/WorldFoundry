"""Whether an engine binary can start on this machine, for the tests that run wf_game.

The default engine/wf_game is built on the host (glibc 2.43, Ubuntu 26.04). The wf-linux-test container is
Ubuntu 24.04, where that binary cannot load ("version `GLIBC_2.43' not found"), so a test that ran it failed
there instead of skipping (triage 2026-11-26: test_camshot_missing_target, test_wall_clock). Build an engine
inside the container and point WF_GAME at it:

    scripts/in-linux-container.sh scripts/build-wf-game-container.sh
    WF_CONTAINER_ENV="WF_GAME=/build/wf-game/src/engine/wf_game" scripts/in-linux-container.sh ...
"""
from __future__ import annotations

import functools
import shutil
import subprocess
from pathlib import Path


@functools.lru_cache(maxsize=None)
def unloadable_reason(path: Path) -> str | None:
    """None when the dynamic loader can resolve every library and symbol version the binary needs, else why not."""
    path = Path(path)
    if not path.exists():
        return f"engine not built: {path}"
    if shutil.which("ldd") is None:
        return None
    r = subprocess.run(["ldd", str(path)], capture_output=True, text=True)
    missing = [line.strip() for line in (r.stdout + r.stderr).splitlines() if "not found" in line]
    if missing:
        return (f"{path} cannot load on this machine ({missing[0]}); build one here with "
                "scripts/build-wf-game-container.sh and set WF_GAME")
    return None
