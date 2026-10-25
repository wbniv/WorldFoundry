"""The level-outputs freshness check: scripts/level-outputs-compare.py and the
regenerate list of scripts/aquarium-levels.sh.

The full check (task aquarium-check) needs Docker and the Blender image; CI runs it
in .github/workflows/level-outputs.yml. These tests need only git and Python.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPARE = ROOT / "scripts" / "level-outputs-compare.py"
LEVELS_SH = ROOT / "scripts" / "aquarium-levels.sh"


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout


def committed_repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / "wflevels" / "tank").mkdir(parents=True)
    (repo / "wflevels" / "tank" / "body.iff").write_bytes(b"MODL\x08\0\0\0FACE\0\0\0\0")
    (repo / "wflevels" / "tank.iff").write_bytes(b"\0" * 64)
    (repo / "wflevels" / "tank" / "generate.py").write_text("print('source')\n")
    git(tmp_path, "init", "-q", str(repo))
    git(repo, "add", ".")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "levels")
    return repo


def rebuilt_copy(repo, tmp_path):
    tree = tmp_path / "rebuilt"
    shutil.copytree(repo, tree, ignore=shutil.ignore_patterns(".git"))
    (tree / "wflevels" / "tank" / "textile.log.htm").write_text("untracked intermediate\n")
    return tree


def compare(repo, tree, *pathspecs):
    return subprocess.run([sys.executable, str(COMPARE), "--repo", str(repo), "--ref", "HEAD",
                           "--tree", str(tree), "--regenerate", "task aquarium-regenerate", "--",
                           *(pathspecs or ["wflevels"])],
                          capture_output=True, text=True)


def test_fresh_output_passes(tmp_path):
    repo = committed_repo(tmp_path)
    result = compare(repo, rebuilt_copy(repo, tmp_path))
    assert result.returncode == 0, result.stdout
    assert "level outputs fresh: all 3 tracked files" in result.stdout


def test_stale_output_fails_with_the_file_and_the_command(tmp_path):
    repo = committed_repo(tmp_path)
    tree = rebuilt_copy(repo, tmp_path)
    # The rebuild produces a different body.iff than the commit holds: the commit is stale.
    (tree / "wflevels" / "tank" / "body.iff").write_bytes(b"MODL\x08\0\0\0FACE\x01\0\0\0")
    (tree / "wflevels" / "tank.iff").unlink()
    result = compare(repo, tree)
    assert result.returncode == 1
    lines = result.stdout.splitlines()
    assert lines[0].startswith("level outputs STALE: 2 of 3 tracked files")
    assert "  changed  wflevels/tank/body.iff" in lines
    assert "  missing  wflevels/tank.iff" in lines
    assert not any("generate.py" in l or "textile.log" in l for l in lines)
    assert lines[-1] == "Regenerate them with `task aquarium-regenerate`, then commit the changed files."


def test_glob_pathspecs_as_aquarium_levels_sh_passes_them(tmp_path):
    """INPUTS uses :(glob) magic, which git ls-tree rejects; the file list comes from git archive."""
    repo = committed_repo(tmp_path)
    tree = rebuilt_copy(repo, tmp_path)
    (tree / "wflevels" / "tank.iff").write_bytes(b"\1" * 64)
    result = compare(repo, tree, ":(glob)wflevels/tank*/**", ":(glob)wflevels/tank*.iff")
    assert result.returncode == 1, result.stderr
    assert result.stdout.splitlines()[0].startswith("level outputs STALE: 1 of 3 tracked files")
    assert "  changed  wflevels/tank.iff" in result.stdout


def test_regenerate_builds_every_tank_of_the_menu_bundle():
    """A tank added to the Android selector must also be regenerated and checked."""
    manifest = (ROOT / "wflevels" / "aquarium-menu.manifest").read_text()
    menu = [m.group(1) for m in re.finditer(r"^level (\S+)-standalone\.iff", manifest, re.M)]
    script = LEVELS_SH.read_text()
    tanks = re.search(r"^TANKS=\(([^)]*)\)", script, re.M).group(1).split()
    assert sorted(["aquarium", *tanks]) == sorted(menu)
    assert "blender_create_aquarium.py" in script  # the clownfish tank, which has no build.sh
    for tank in tanks:
        assert (ROOT / "wflevels" / tank / "build.sh").is_file()


def test_help_exits_zero():
    result = subprocess.run(["bash", str(LEVELS_SH), "--help"], capture_output=True, text=True)
    assert result.returncode == 0 and "check" in result.stdout
