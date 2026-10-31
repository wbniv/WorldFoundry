"""wflevels/main-cd.manifest is the one list of the main cd.iff's levels.

`task build-cd-iff`, wflevels/baseline/verify.py and tests/level_menu_harness.py all read it, so
adding a level is one appended line. These tests keep it that way: the manifest is valid, the
committed bundle matches it, the build script reproduces the committed bytes, and no hand-written
copy of the list creeps back in.
"""
import importlib.util
import struct
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / "wfsource/source/game"
BUNDLE = GAME / "cd.iff"
CDPACK = ROOT / "wftools/cdpack-rs/target/release/cdpack"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cd_manifest = _load("cd_manifest", ROOT / "scripts/cd_manifest.py")


def _toc(data):
    count = struct.unpack_from("<I", data, 12)[0] // 12
    return [struct.unpack_from("<4sII", data, 16 + i * 12) for i in range(count)]


def test_manifest_is_valid_and_ordered():
    levels = cd_manifest.load()
    assert [level.index for level in levels] == list(range(len(levels)))
    assert levels[0].slug == "smb_w1_1"  # shell.fth boots level 0, and W1-1..W1-4 chain by index 0-3
    assert [level.slug for level in levels[:4]] == ["smb_w1_%d" % n for n in (1, 2, 3, 4)]
    assert len({level.slug for level in levels}) == len(levels)
    assert len({level.name for level in levels}) == len(levels)
    # Indices that scripts and device checks name must not move: append only.
    assert {level.slug: level.index for level in levels}["baseline"] == 7


@pytest.mark.parametrize("text, message", [
    ("title WF\nlevel baseline-standalone.iff | Baseline\n", "no menu"),
    ("prompt Pick\nlevel baseline-standalone.iff | Baseline\n", "no menu"),
    ("level baseline-standalone.iff Baseline\n", "expected"),
    ("level baseline.iff | Baseline\n", "standalone"),
    ("level missing-standalone.iff | Missing\n", "does not exist"),
    ("level baseline-standalone.iff | Baseline\nlevel baseline-standalone.iff | Again\n", "twice"),
    ("level baseline-standalone.iff | \n", "expected"),
    ("level baseline-standalone.iff | Café\n", "ASCII"),
    ("# only a comment\n\n", "no levels"),
])
def test_loader_rejects_bad_manifests(tmp_path, text, message):
    for name in ("baseline-standalone.iff",):
        (tmp_path / name).write_bytes(b"x")
    manifest = tmp_path / "m.manifest"
    manifest.write_text(text)
    with pytest.raises(ValueError, match=message):
        cd_manifest.load(manifest)


def test_committed_bundle_matches_the_manifest():
    levels = cd_manifest.load()
    data = BUNDLE.read_bytes()
    toc = _toc(data)
    assert len(toc) == len(levels) + 2, "shell + manifest levels + UI font; run task build-cd-iff"
    assert toc[0][0] == b"SHEL" and toc[-1][0] == b"UIFT"
    for level in levels:
        tag, offset, size = toc[level.index + 1]
        assert offset % 2048 == 0
        assert data[offset:offset + size] == level.path.read_bytes(), \
            "%s is stale in wfsource/source/game/cd.iff: run task build-cd-iff and commit it" % level.slug


@pytest.mark.skipif(not CDPACK.is_file(), reason="cdpack is not built (cargo build --release --manifest-path wftools/cdpack-rs/Cargo.toml)")
def test_build_script_reproduces_the_committed_bundle(tmp_path):
    out = tmp_path / "cd.iff"
    subprocess.run([sys.executable, str(ROOT / "scripts/build-main-cd.py"), "-o", str(out)],
                   check=True, capture_output=True)
    assert out.read_bytes() == BUNDLE.read_bytes()


def test_no_hand_written_copy_of_the_level_list():
    taskfile = (ROOT / "Taskfile.yml").read_text()
    block = taskfile.split("\n  build-cd-iff:\n", 1)[1].split("\n  build-cd-iff-", 1)[0]
    assert "scripts/build-main-cd.py" in block
    assert "-standalone.iff" not in block, "the main bundle's levels belong in wflevels/main-cd.manifest only"
    verify = (ROOT / "wflevels/baseline/verify.py").read_text()
    assert "marble-madness" not in verify and "'qbert_practice'" not in verify
    harness = (ROOT / "tests/level_menu_harness.py").read_text()
    assert "marble-madness" not in harness
