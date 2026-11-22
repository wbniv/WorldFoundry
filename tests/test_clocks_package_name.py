"""WF Clocks is `org.worldfoundry.game.clocks`, and nothing outside the history still names the old id.

Will, 2026-11-22: every new app uses org.worldfoundry.game.{name} as its applicationId; the Java code package
(namespace, org.worldfoundry.screensaver) keeps its name. docs/plans/2026-11-22-one-aquarium-apk.md (D5) and the
"Package names" section of android/README.md. A new applicationId is a new app to Android, so the coordinator
registry entry clocks-screensaver changes in the same administrator upgrade as the Aquarium's.
"""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD = "org.worldfoundry.clocks"
NEW = "org.worldfoundry.game.clocks"
RENAME_NOTES = ("was `org.worldfoundry.clocks` until",              # android/screensaver/README.md: records the rename
                "The old `org.worldfoundry.clocks` stays installed")      # TODO.md: the landing item says what happens on the devices


SKIP_DIRS = {".git", ".worktrees", "build", "build-docker", "node_modules", "target", ".gradle", "outputs", "__pycache__"}
# The HOWTO's registry tables name each app's ids as they were. The Aquarium owner rewrites them for both apps in the push that
# lands the Aquarium half, so the file is exempt until then; delete this entry in that push.
EXEMPT_FILES = {"docs/howto/combine-levels-chooser-and-screensaver-launch.md"}
SKIP_PREFIXES = ("docs/diagnostics", "docs/plans", "docs/transcripts")          # history: transcripts, measurements and plans keep what was true then
TEXT = {".md", ".py", ".sh", ".kts", ".xml", ".java", ".json", ".yml", ".yaml", ".manifest", ".txt", ".cc", ".h", ".hp", ".gradle",
        ".toml", ".cmake", ".properties"}


def tracked_hits():
    """Every line outside the history that still names the old package. Walks the files itself: `git grep` cannot run in
    the test container (a worktree's .git points outside it), and a guard that cannot look must not pass."""
    hits = []
    for folder, dirs, files in __import__("os").walk(ROOT):
        rel = Path(folder).relative_to(ROOT).as_posix()
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not (f"{rel}/{d}" if rel != "." else d).startswith(SKIP_PREFIXES)]
        for name in files:
            path = Path(folder) / name
            if path.relative_to(ROOT).as_posix() in EXEMPT_FILES:
                continue
            if (path.suffix not in TEXT and name not in ("Taskfile.yml",)) or name == "test_clocks_package_name.py":
                continue
            try:
                lines = path.read_text().splitlines()
            except (UnicodeDecodeError, OSError):
                continue
            hits += [f"{path.relative_to(ROOT)}:{n}" for n, line in enumerate(lines, 1)
                     if re.search(re.escape(OLD) + r"(?!\w)", line) and not any(note in line for note in RENAME_NOTES)]
    return hits


def test_the_clocks_flavor_application_id_is_the_game_package_and_the_namespace_is_unchanged():
    gradle = (ROOT / "android/screensaver/build.gradle.kts").read_text()
    block = re.search(r'create\("clocks"\)\s*\{(.*?)\n\s*\}', gradle, re.S).group(1)
    assert f'applicationId = "{NEW}"' in block
    assert 'namespace = "org.worldfoundry.screensaver"' in gradle          # the code package is not renamed


def test_no_tracked_file_outside_history_names_the_old_clocks_package():
    assert tracked_hits() == []


def test_the_clocks_manifest_has_no_hard_coded_package_and_launches_by_full_class_name_in_the_docs():
    xml = (ROOT / "android/screensaver/src/clocks/AndroidManifest.xml").read_text()
    assert "authorities=\"${applicationId}.settings\"" in xml
    readme = (ROOT / "android/screensaver/README.md").read_text()
    assert f"am start -n {NEW}/org.worldfoundry.screensaver.ClocksActivity" in readme    # a leading "." would resolve against the id
    assert not re.search(rf"{re.escape(NEW)}/\.", readme)
