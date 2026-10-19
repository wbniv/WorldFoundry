"""A source added to an already-configured build directory must still get built.

The engine's CMakeLists.txt collects sources with file(GLOB ...). A plain GLOB runs only when
CMake configures, so a build directory configured before a new .cc existed (Gradle's
android/app/.cxx, build/, build-editor/) never saw it and the link failed with undefined
symbols (2026-10-02: levelmenu::ParseToc, from the new game/level_menu.cc). CONFIGURE_DEPENDS
re-runs the glob on every build and regenerates when the file list changes.

  * static: every file(GLOB ...) / file(GLOB_RECURSE ...) in the repository's own CMake files
    carries CONFIGURE_DEPENDS (vendored trees are not ours and are skipped);
  * behavioural: a tiny project, built, then given a new source file. With the flag the next
    build picks it up and links; without it (the control) the link fails, which shows the test
    models the real failure.

    python3 -m pytest tests/test_cmake_glob_configure_depends.py -v
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SKIP_DIRS = ("vendor", "third_party", "build", ".cxx", "node_modules", ".claude")


def _repo_cmake_files():
    out = subprocess.run(["git", "ls-files", "*CMakeLists.txt", "*.cmake"], cwd=REPO,
                         capture_output=True, text=True, check=True).stdout.split()
    return [REPO / p for p in out
            if not any(f"/{d}/" in f"/{p}" or p.startswith(d + "/") for d in SKIP_DIRS)
            and (REPO / p).exists()]


def _glob_statements(text: str):
    """Yield each file(GLOB ...) / file(GLOB_RECURSE ...) call as one string (they span lines)."""
    for m in re.finditer(r"\bfile\s*\(\s*GLOB(?:_RECURSE)?\b", text, re.I):
        depth, i = 0, m.start()
        while i < len(text):
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        yield text[m.start():i + 1]


def test_every_glob_in_our_cmake_files_has_configure_depends():
    found = 0
    for f in _repo_cmake_files():
        for stmt in _glob_statements(f.read_text()):
            found += 1
            assert "CONFIGURE_DEPENDS" in stmt, f"{f.relative_to(REPO)}: {' '.join(stmt.split())}"
    assert found >= 1, "the engine's CMakeLists.txt glob was not found: the scan is broken"


def _tools():
    cmake, cc = shutil.which("cmake"), shutil.which("cc")
    gen = "Ninja" if shutil.which("ninja") else ("Unix Makefiles" if shutil.which("make") else None)
    if not (cmake and cc and gen):
        pytest.skip("needs cmake, a C compiler and ninja or make")
    return cmake, gen


def _project(tmp_path: Path, flag: str) -> Path:
    src = tmp_path / "proj"
    (src / "src").mkdir(parents=True)
    (src / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.22)\nproject(globtest C)\n"
        f'file(GLOB srcs {flag} "${{CMAKE_SOURCE_DIR}}/src/*.c")\n'
        "add_executable(globtest ${srcs})\n")
    (src / "src" / "main.c").write_text("int main(void) { return 0; }\n")
    return src


def _run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def _build_then_add_a_source(tmp_path: Path, flag: str):
    cmake, gen = _tools()
    src = _project(tmp_path, flag)
    build = tmp_path / "build"
    assert _run([cmake, "-S", str(src), "-B", str(build), "-G", gen], tmp_path).returncode == 0
    first = _run([cmake, "--build", str(build)], tmp_path)
    assert first.returncode == 0, first.stdout + first.stderr
    # A new source arrives after the build directory was configured; main.c now needs it.
    (src / "src" / "extra.c").write_text("int extra_marker = 42;\n")
    (src / "src" / "main.c").write_text(
        "extern int extra_marker;\nint main(void) { return extra_marker == 42 ? 0 : 1; }\n")
    second = _run([cmake, "--build", str(build)], tmp_path)
    return second, build


def test_with_configure_depends_a_new_source_is_built_and_linked(tmp_path):
    second, build = _build_then_add_a_source(tmp_path, "CONFIGURE_DEPENDS")
    assert second.returncode == 0, second.stdout + second.stderr
    assert subprocess.run([str(build / "globtest")]).returncode == 0


def test_control_without_it_the_new_source_is_missed(tmp_path):
    second, _ = _build_then_add_a_source(tmp_path, "")
    out = second.stdout + second.stderr
    assert second.returncode != 0 and "extra_marker" in out, out
