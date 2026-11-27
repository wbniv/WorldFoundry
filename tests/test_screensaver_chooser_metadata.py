"""Which screensaver packs offer the "use for screensaver" chooser, and how they declare it.

docs: docs/plans/2026-11-27-screensaver-chooser.md and android/screensaver/README.md, "Choosing the screensaver".
One ScreensaverChooserActivity serves every pack. Whether a pack offers it is data, not code: a pack whose roster
(wflevels/<flavor>-menu.manifest, copied into the flavor as levels.manifest by build.gradle.kts) has more than one
level points its Dream at @xml/dream_chooser and declares the activity; a pack with one level (Seahorse Grid) or no
roster keeps the empty @xml/dream and declares nothing (decision D7). Homeboard and Android read settingsActivity from
the Dream XML, so it must be the full class name: Homeboard joins a leading '.' with the applicationId, and Android
ignores a package/class outside the Dream's own package.
"""
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "android/screensaver"
SRC = MODULE / "src"
ANDROID = "{http://schemas.android.com/apk/res/android}"
CHOOSER = "org.worldfoundry.screensaver.ScreensaverChooserActivity"
AUTHORITY = "org.worldfoundry.screensaver.SETTINGS_AUTHORITY"
DREAM_ACTION = "android.service.dreams.DreamService"


def rosters():
    """flavor -> roster manifest, from the manifests build.gradle.kts copies (wflevels/<flavor>-menu.manifest)."""
    gradle = (MODULE / "build.gradle.kts").read_text()
    found = {m.group(1): ROOT / "wflevels" / f"{m.group(1)}-menu.manifest"
             for m in re.finditer(r'"\.\./wflevels/([a-z0-9_]+)-menu\.manifest"', gradle)}
    assert found, "build.gradle.kts copies no wflevels/<flavor>-menu.manifest"
    return found


def level_count(manifest):
    return sum(1 for line in manifest.read_text().splitlines() if line.strip().startswith("level "))


def dream_flavors():
    """Every flavor whose manifest declares a Dream service: {flavor: parsed manifest}."""
    out = {}
    for manifest in sorted(SRC.glob("*/AndroidManifest.xml")):
        tree = ET.parse(manifest)
        if any(a.get(ANDROID + "name") == DREAM_ACTION for a in tree.iter("action")):
            out[manifest.parent.name] = tree
    return out


def dream_service(tree):
    services = [s for s in tree.iter("service")
                if any(a.get(ANDROID + "name") == DREAM_ACTION for a in s.iter("action"))]
    assert len(services) == 1
    return services[0]


def dream_resource(tree):
    metas = [m for m in dream_service(tree).findall("meta-data") if m.get(ANDROID + "name") == "android.service.dream"]
    assert len(metas) == 1
    return metas[0].get(ANDROID + "resource")


def chooser_activities(tree):
    return [a for a in tree.iter("activity") if a.get(ANDROID + "name") in (".ScreensaverChooserActivity", CHOOSER)]


def offers_chooser(flavor):
    roster = rosters().get(flavor)
    return roster is not None and level_count(roster) > 1


def test_the_rosters_exist_and_the_dream_flavors_were_found():
    for flavor, roster in rosters().items():
        assert roster.is_file(), f"{flavor}: {roster} is missing"
        assert (SRC / flavor).is_dir(), f"{roster.name} names no flavor directory {flavor}"
    flavors = dream_flavors()
    assert {"aquarium", "clocks", "seahorse"} <= set(flavors), sorted(flavors)


def test_the_shipped_packs_offer_it_where_expected():
    assert offers_chooser("aquarium") and offers_chooser("clocks")
    assert not offers_chooser("seahorse") and not offers_chooser("planted"), "one-level packs offer no chooser (D7)"


def test_dream_chooser_names_the_activity_by_its_full_class_name():
    dream = ET.parse(SRC / "main/res/xml/dream_chooser.xml").getroot()
    value = dream.get(ANDROID + "settingsActivity")
    assert value == CHOOSER
    assert "/" not in value and not value.startswith(".")
    java = SRC / "main/java" / (value.replace(".", "/") + ".java")
    assert java.is_file(), f"{value} is not a class in src/main"


def test_the_plain_dream_xml_has_no_settings_link():
    dream = ET.parse(SRC / "main/res/xml/dream.xml").getroot()
    assert dream.get(ANDROID + "settingsActivity") is None


def test_the_main_manifest_does_not_declare_the_chooser():
    assert not chooser_activities(ET.parse(SRC / "main/AndroidManifest.xml")), \
        "declare the chooser only in the flavors that offer it"


@pytest.mark.parametrize("flavor", sorted(dream_flavors()))
def test_a_pack_declares_the_chooser_exactly_when_its_roster_has_more_than_one_level(flavor):
    tree = dream_flavors()[flavor]
    activities = chooser_activities(tree)
    if offers_chooser(flavor):
        assert dream_resource(tree) == "@xml/dream_chooser"
        assert len(activities) == 1, f"{flavor}: declare ScreensaverChooserActivity once"
        a = activities[0]
        assert a.get(ANDROID + "exported") == "true", "Homeboard and Android's Settings start it by component"
        assert a.get(ANDROID + "process") == ":chooser"
        assert a.get(ANDROID + "taskAffinity") == ""
        assert a.findall("intent-filter") == [], "started by component only"
    else:
        assert dream_resource(tree) == "@xml/dream", f"{flavor}: no chooser, so the plain Dream XML"
        assert not activities, f"{flavor}: offers no chooser, so declares none"


@pytest.mark.parametrize("flavor", sorted(f for f in dream_flavors() if offers_chooser(f)))
def test_the_chooser_finds_a_provider_that_answers_the_shared_level_calls(flavor):
    tree = dream_flavors()[flavor]
    metas = {m.get(ANDROID + "name"): m.get(ANDROID + "value") for m in dream_service(tree).findall("meta-data")}
    authority = metas.get(AUTHORITY)
    assert authority, f"{flavor}: the Dream declares {AUTHORITY}, which the chooser reads"
    providers = [p for p in tree.iter("provider") if p.get(ANDROID + "authorities") == authority]
    assert len(providers) == 1, f"{flavor}: one provider serves {authority}"
    cls = providers[0].get(ANDROID + "name").lstrip(".")
    source = (SRC / "main/java/org/worldfoundry/screensaver" / f"{cls}.java").read_text()
    assert "LevelChoiceCalls.handle(" in source, f"{cls} must answer getLevel and setSetting level:<id>"
