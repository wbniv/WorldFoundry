"""Whether a local build output (an APK under android/*/build) is newer than the tracked files it packs.

Several suites open a release APK if one has been built and compare its assets with the tracked sources. The APK
is gitignored and is rebuilt only by hand, so one built weeks ago failed against every later source change: on
2026-11-26 the condo, smb, qbert and snowgoons APKs dated from 2026-10-19 to 2026-11-14 (triage,
docs/diagnostics/2026-11-26-pytest-triage.md). Comparing a stale build says nothing about the sources, so such
a test skips with the rebuild command; an APK built after its inputs is still compared byte for byte.
"""
from __future__ import annotations

from pathlib import Path


def stale_reason(output: Path, inputs, rebuild: str) -> str | None:
    """None when `output` is newer than every existing path in `inputs`, else a skip reason naming the newest input."""
    built = output.stat().st_mtime
    newer = [p for p in map(Path, inputs) if p.exists() and p.stat().st_mtime > built]
    if not newer:
        return None
    newest = max(newer, key=lambda p: p.stat().st_mtime)
    return f"{output.name} is older than {newest.name}, which it packs: rebuild it ({rebuild})"
