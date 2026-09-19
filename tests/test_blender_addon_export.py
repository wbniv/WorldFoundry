"""
Test the wf_blender add-on's level exporter against pinned Blender versions.

Loads a fixture .blend in headless Blender, runs WF_OT_export_level, and
byte-compares the output .lev against a checked-in golden.

To run locally against an arbitrary Blender install:

    BLENDER_BIN=/path/to/blender pytest tests/test_blender_addon_export.py

If $BLENDER_BIN is unset the test is skipped (so the broader pytest run
doesn't fail on developer machines without a pinned Blender). CI sets the
env var explicitly per matrix job.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import textwrap
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
ADDON_PARENT = REPO / "wftools"
ADDON_DIR = ADDON_PARENT / "wf_blender"
WF_PY_DIR = ADDON_PARENT / "wf_py"
FIXTURE_BLEND = REPO / "wflevels" / "qbert_practice" / "qbert_practice.blend"
GOLDEN_LEV = REPO / "tests" / "fixtures" / "qbert_practice-golden.lev"
RUNNER = REPO / "tests" / "blender_runner" / "run_export.py"


@pytest.fixture(scope="session")
def wf_core_so() -> Path:
    """Locate or build the wf_core Rust extension; return the .so path.

    Search order:
      1. wftools/wf_py/target/wheels/wf_core-*.whl — newest wheel from a
         prior maturin build.
      2. Build via `maturin build --release` (slow, ~1-2 min cold).
    Either way, extract the .so into tests/.cache/ and return that path.

    The .so is built with pyo3 abi3 so a single artifact works across the
    Python versions that ship in different Blender releases (verified
    on 3.10/4.0.2)."""
    cache_dir = REPO / "tests" / ".cache"
    cache_dir.mkdir(exist_ok=True)
    cache_so = cache_dir / "wf_core.so"

    def _wheels() -> list[Path]:
        wheels_dir = WF_PY_DIR / "target" / "wheels"
        return sorted(wheels_dir.glob("wf_core-*.whl"), key=lambda p: p.stat().st_mtime)

    wheels = _wheels()
    if not wheels:
        if not shutil.which("maturin"):
            pytest.skip("wf_core not built and maturin not on PATH — "
                        "install maturin or pre-build the wheel "
                        "(cd wftools/wf_py && maturin build --release)")
        subprocess.run(
            ["maturin", "build", "--release"],
            cwd=str(WF_PY_DIR), check=True,
        )
        wheels = _wheels()
        if not wheels:
            pytest.fail("maturin build succeeded but produced no wheel")

    # Extract wf_core's .so from the newest wheel
    wheel = wheels[-1]
    with zipfile.ZipFile(wheel) as z:
        so_names = [n for n in z.namelist() if n.endswith(".so")]
        if not so_names:
            pytest.fail(f"no .so found inside {wheel}")
        cache_so.write_bytes(z.read(so_names[0]))
    return cache_so


def _blender_bin() -> Path:
    bin_path = os.environ.get("BLENDER_BIN")
    if not bin_path:
        pytest.skip("BLENDER_BIN not set — point at a Blender binary to run this test")
    p = Path(bin_path)
    if not p.is_file() or not os.access(p, os.X_OK):
        pytest.skip(f"BLENDER_BIN={bin_path} is not an executable file")
    return p


def _blender_version(bin_path: Path) -> str:
    out = subprocess.run(
        [str(bin_path), "--version"],
        capture_output=True, text=True, timeout=15,
    )
    # First line: "Blender X.Y.Z"
    return out.stdout.splitlines()[0].split()[-1] if out.stdout else "unknown"


_EXPORT_CACHE: dict = {}


def _export_fixture(tmp_path: Path, wf_core_so: Path) -> tuple[Path, str]:
    """Run the headless export of the qbert fixture once per session; both tests below
    read the same output directory (the .lev plus the per-mesh .iff files beside it)."""
    if 'out' in _EXPORT_CACHE:
        return _EXPORT_CACHE['out']
    if not FIXTURE_BLEND.is_file():
        pytest.fail(f"fixture missing: {FIXTURE_BLEND}")
    if not RUNNER.is_file():
        pytest.fail(f"runner missing: {RUNNER}")

    bin_path = _blender_bin()
    bl_ver = _blender_version(bin_path)
    print(f"\n  Testing against Blender {bl_ver} ({bin_path})")

    out_lev = tmp_path / "qbert_practice-out.lev"

    # Build a $BLENDER_USER_RESOURCES sandbox — a clean, throwaway user
    # resources dir so Blender (a) doesn't pick up the developer's actually-
    # installed addons from ~/.config/blender/<ver>/ and (b) DOES find
    # wf_blender from the repo's source tree.
    #
    # We need the *RESOURCES* env var (not SCRIPTS) because --factory-startup
    # excludes user scripts from addon-discovery; pointing the whole user-
    # resources dir at a sandbox sidesteps that gating.
    user_resources = tmp_path / "blender-user-resources"
    # Layout under BLENDER_USER_RESOURCES: scripts/addons/<addon> (NO
    # version subdir — that's only how ~/.config/blender/<ver>/ is laid out;
    # the BLENDER_USER_RESOURCES override uses a flat layout per Blender's
    # bpy.utils.user_resource('SCRIPTS') resolution).
    addons_dir = user_resources / "scripts" / "addons"
    addons_dir.mkdir(parents=True)
    # Copy the addon source into place (rather than symlinking the whole
    # source dir) so we can also drop wf_core.so beside the __init__.py
    # without polluting the developer's working tree.
    sandbox_addon = addons_dir / "wf_blender"
    shutil.copytree(ADDON_DIR, sandbox_addon, symlinks=False)
    shutil.copy(wf_core_so, sandbox_addon / "wf_core.so")

    env = os.environ.copy()
    env["WF_EXPORT_OUT"] = str(out_lev)
    env["BLENDER_USER_RESOURCES"] = str(user_resources)

    # Run Blender headless with our runner. NO --factory-startup: that flag
    # disables user-scripts entirely, defeating the sandbox we built above.
    # The sandbox itself provides the isolation --factory-startup would
    # normally give us.
    result = subprocess.run(
        [
            str(bin_path),
            "--background",
            str(FIXTURE_BLEND),
            "--python", str(RUNNER),
            "--python-exit-code", "1",  # propagate script errors to exit code
        ],
        capture_output=True, text=True, env=env, timeout=120,
    )

    if result.returncode != 0:
        # Surface Blender's stdout/stderr so the failure is debuggable
        pytest.fail(textwrap.dedent(f"""
            Blender headless export failed (exit {result.returncode})

            --- stdout ---
            {result.stdout}

            --- stderr ---
            {result.stderr}
        """).strip())

    if not out_lev.is_file():
        pytest.fail(f"runner exited cleanly but {out_lev} was not produced")
    _EXPORT_CACHE['out'] = (out_lev, bl_ver)
    return out_lev, bl_ver


def test_blender_addon_export_qbert_practice(tmp_path: Path, wf_core_so: Path) -> None:
    """End-to-end: load fixture .blend, run wf_blender's level export, compare
    output to the committed golden .lev. Byte-identical match required.

    Regen the golden when an EXPECTED export-format change lands (or when the Blender
    version's float noise moves the slope/bbox digits — check the diff is only that):
        BLENDER_BIN=$(which blender) python3 -m pytest tests/test_blender_addon_export.py
        cp <printed out.lev> tests/fixtures/qbert_practice-golden.lev
    """
    out_lev, bl_ver = _export_fixture(tmp_path, wf_core_so)

    if not GOLDEN_LEV.is_file():
        # On first run there's no golden yet. Print the produced output and
        # the regen command, but still fail — the developer must review +
        # commit the golden explicitly. Don't silently auto-generate.
        produced = out_lev.read_text()
        pytest.fail(textwrap.dedent(f"""
            Golden not found at {GOLDEN_LEV}.

            Test produced {out_lev.stat().st_size} bytes. Review the output:

                {out_lev}

            If it looks right, commit it as the golden:

                mkdir -p {GOLDEN_LEV.parent}
                cp {out_lev} {GOLDEN_LEV}
                git add {GOLDEN_LEV.relative_to(REPO)}
                git commit
        """).strip())

    # Byte-identical check
    actual = out_lev.read_bytes()
    expected = GOLDEN_LEV.read_bytes()
    if actual != expected:
        # Surface a first-line-of-divergence hint for easy triage
        for i, (a, e) in enumerate(zip(actual, expected)):
            if a != e:
                pytest.fail(textwrap.dedent(f"""
                    Export output differs from golden at byte {i}.

                    Blender version: {bl_ver}
                    Actual:   {out_lev} ({len(actual)} bytes)
                    Expected: {GOLDEN_LEV} ({len(expected)} bytes)

                    Run a diff:

                        diff {out_lev} {GOLDEN_LEV}

                    If the change is intentional + the new output is correct,
                    regenerate the golden:

                        cp {out_lev} {GOLDEN_LEV}
                """).strip())
        # If lengths differ but the common prefix matches:
        pytest.fail(
            f"Export output length differs from golden: "
            f"actual={len(actual)}, expected={len(expected)}"
        )


# ── Face hand ─────────────────────────────────────────────────────────────────
# The engine computes a face normal as (v2−v0)×(v1−v0) (gfx/face.hpi), Blender as
# (v1−v0)×(v2−v0). export_level.py reverses each face's loop order so a mesh that is outward
# in Blender is outward in WF. This pins that: every face of an exported closed box must have
# its WF normal pointing away from the box centroid. Comment the reversal out and it fails.
_VRTX_SIZE, _FACE_SIZE = 24, 8


def _iff_chunks(data: bytes) -> dict:
    """Flat {tag: payload} over a binary IFF blob (first occurrence of each tag)."""
    chunks, i = {}, 0
    while i + 8 <= len(data):
        tag = data[i:i + 4]
        if not tag.isalpha() and tag not in (b'FORM',):
            i += 1
            continue
        size = int.from_bytes(data[i + 4:i + 8], 'little')
        if 0 < size <= len(data) - i - 8:
            key = tag.decode('ascii', 'replace')
            if key not in chunks:
                chunks[key] = data[i + 8:i + 8 + size]
            if key in ('MODL', 'FORM'):
                i += 8                      # descend
                continue
            i += 8 + size
        else:
            i += 1
    return chunks


def _wf_faces(iff_path: Path):
    """→ (verts[(x, y, z)], faces[(a, b, c)]) in WF's on-disk order."""
    import struct
    chunks = _iff_chunks(iff_path.read_bytes())
    vrtx, face = chunks.get('VRTX', b''), chunks.get('FACE', b'')
    verts = []
    for i in range(len(vrtx) // _VRTX_SIZE):
        _u, _v, _c, x, y, z = struct.unpack_from('<iiIiii', vrtx, i * _VRTX_SIZE)
        verts.append((x / 65536.0, y / 65536.0, z / 65536.0))
    faces = [struct.unpack_from('<hhh', face, i * _FACE_SIZE) for i in range(len(face) // _FACE_SIZE)]
    return verts, faces


def test_exported_faces_are_wf_outward(tmp_path: Path, wf_core_so: Path) -> None:
    out_lev, _ = _export_fixture(tmp_path, wf_core_so)
    boxes = []
    for iff in sorted(out_lev.parent.glob('*.iff')):
        verts, faces = _wf_faces(iff)
        if len(verts) == 8 and len(faces) == 12:      # a closed box
            boxes.append((iff.name, verts, faces))
    assert boxes, f"no 8-vertex/12-face box mesh among {[p.name for p in out_lev.parent.glob('*.iff')]}"
    for name, verts, faces in boxes:
        cx = sum(v[0] for v in verts) / 8; cy = sum(v[1] for v in verts) / 8; cz = sum(v[2] for v in verts) / 8
        for a, b, c in faces:
            v0, v1, v2 = verts[a], verts[b], verts[c]
            e1 = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])       # WF: (v2−v0) × (v1−v0)
            e2 = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
            n = (e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0])
            fc = ((v0[0] + v1[0] + v2[0]) / 3 - cx, (v0[1] + v1[1] + v2[1]) / 3 - cy, (v0[2] + v1[2] + v2[2]) / 3 - cz)
            dot = n[0] * fc[0] + n[1] * fc[1] + n[2] * fc[2]
            assert dot > 0, f"{name}: face ({a},{b},{c}) has its WF normal pointing INTO the box (dot {dot:.4g}) — the exporter's hand reversal is missing"
