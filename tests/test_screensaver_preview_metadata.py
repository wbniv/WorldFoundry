"""Each Dream <service> declares how Homeboard previews it, and the coordinator registry says the same.

docs: ~/homeboard-tv/docs/plans/2026-11-26-screensaver-companion-contract.md, "What each app declares", and
android/screensaver/README.md, "Preview metadata". Homeboard reads PREVIEW_ACTIVITY (the full class name, never a leading
`.` and never the package: it joins the Dream's own package) and, when the preview needs a chooser, PREVIEW_EXTRA with
PREVIEW_VALUE. The coordinator's applications.json carries the same three facts as `preview_activity`
(`<package>/<class>`), `preview_extra` and `preview_value`; the two must not drift.

The registry lives in another repo (chromecast-coordinator). It is looked up at $WF_COORDINATOR_APPLICATIONS_JSON, else
~/chromecast-coordinator/scripts/wf_device/plugins/android/applications.json. When it is absent the expected values below
are still checked and the cross-check is skipped with a visible reason (pytest -rs shows it); it never passes silently.
"""
import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "android/screensaver/src"
ANDROID = "{http://schemas.android.com/apk/res/android}"
PREFIX = "org.worldfoundry.screensaver."
PREVIEW_CLASS = "org.worldfoundry.screensaver.ScreensaverPreviewActivity"
REGISTRY = Path(os.environ.get(
    "WF_COORDINATOR_APPLICATIONS_JSON",
    Path.home() / "chromecast-coordinator/scripts/wf_device/plugins/android/applications.json"))

# flavor -> (registry key, applicationId, dream service, extra, value). Planted is being retired and Tidespike is a spike.
DREAMS = {
    "aquarium": ("aquarium", "org.worldfoundry.game.aquarium", "AquariumDreamService", "org.worldfoundry.screensaver.DREAM", "aquarium"),
    "clocks": ("clocks", "org.worldfoundry.game.clocks", "ClocksDreamService", None, None),
    "seahorse": ("seahorse-screensaver", "org.worldfoundry.seahorsegrid", "SeahorseGridDreamService",
                 "org.worldfoundry.screensaver.DREAM", "seahorse_grid"),
}


def dream_meta(flavor):
    """The <meta-data> of the flavor's Dream <service>, as {name: value}."""
    tree = ET.parse(SRC / flavor / "AndroidManifest.xml")
    services = [s for s in tree.iter("service") if s.get(ANDROID + "name") == "." + DREAMS[flavor][2]]
    assert len(services) == 1, f"{flavor}: expected one {DREAMS[flavor][2]} <service>"
    return {m.get(ANDROID + "name"): m.get(ANDROID + "value") for m in services[0].findall("meta-data")}


@pytest.mark.parametrize("flavor", DREAMS)
def test_the_dream_service_declares_the_preview_activity_and_only_the_expected_extra(flavor):
    _, _, _, extra, value = DREAMS[flavor]
    meta = dream_meta(flavor)
    assert meta[PREFIX + "PREVIEW_ACTIVITY"] == PREVIEW_CLASS      # full class name: no leading '.', no package
    assert meta.get(PREFIX + "PREVIEW_EXTRA") == extra
    assert meta.get(PREFIX + "PREVIEW_VALUE") == value
    assert not {k for k in meta if k.startswith(PREFIX)} - {
        PREFIX + k for k in ("SETTINGS_AUTHORITY", "PREVIEW_ACTIVITY", "PREVIEW_EXTRA", "PREVIEW_VALUE")}, \
        "Homeboard reads no other org.worldfoundry.screensaver.* Dream meta-data (LEVEL_*, provider access were dropped)"


def test_the_preview_activity_is_exported_in_the_main_manifest_and_no_flavor_overrides_it():
    main = ET.parse(SRC / "main/AndroidManifest.xml")
    previews = [a for a in main.iter("activity") if a.get(ANDROID + "name") == ".ScreensaverPreviewActivity"]
    assert len(previews) == 1 and previews[0].get(ANDROID + "exported") == "true"
    for flavor in DREAMS:                                           # the manifest merger would let a flavor redeclare it
        activities = [a.get(ANDROID + "name") for a in ET.parse(SRC / flavor / "AndroidManifest.xml").iter("activity")]
        assert ".ScreensaverPreviewActivity" not in activities, f"{flavor} redeclares the preview activity"
    assert (ROOT / "android/screensaver/src/main/java/org/worldfoundry/screensaver/ScreensaverPreviewActivity.java").is_file()


@pytest.mark.parametrize("flavor", DREAMS)
def test_the_manifest_matches_the_coordinator_registry(flavor):
    if not REGISTRY.is_file():
        pytest.skip(f"coordinator registry not found at {REGISTRY}; set WF_COORDINATOR_APPLICATIONS_JSON to cross-check")
    key, package, _, _, _ = DREAMS[flavor]
    entry = json.loads(REGISTRY.read_text())["applications"][key]
    assert entry["package"] == package
    registry_package, registry_class = entry["preview_activity"].split("/")
    assert registry_package == package
    meta = dream_meta(flavor)
    assert meta[PREFIX + "PREVIEW_ACTIVITY"] == registry_class
    assert meta.get(PREFIX + "PREVIEW_EXTRA") == entry.get("preview_extra")
    assert meta.get(PREFIX + "PREVIEW_VALUE") == entry.get("preview_value")


@pytest.mark.parametrize("flavor", DREAMS)
def test_the_application_id_in_the_gradle_flavor_is_the_package_the_preview_is_joined_with(flavor):
    gradle = (ROOT / "android/screensaver/build.gradle.kts").read_text()
    block = re.search(r'create\("%s"\)\s*\{(.*?)\n\s*\}' % flavor, gradle, re.S).group(1)
    assert f'applicationId = "{DREAMS[flavor][1]}"' in block
