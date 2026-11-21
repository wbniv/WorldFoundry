"""The clocks flavor reads its roster from wflevels/clocks-menu.manifest through the shared LevelCatalog.

Plan: docs/plans/2026-11-21-tide-harbour-clock.md, "The bundle and the chooser", D2 to D4, and the
HOWTO docs/howto/combine-levels-chooser-and-screensaver-launch.md, section 4: a Gradle Copy puts the
manifest in the flavor's assets as levels.manifest; the launch activities start through LevelLaunch;
LevelCatalog and LevelLaunch are never copied. With no LEVEL extra the launcher opens the chooser
(-1); the Dream plays the saved choice and never the chooser; nothing but the settings provider
writes the saved choice, so a preview or a one-run LEVEL launch never overwrites it.
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'android/screensaver'
JAVA = APP / 'src/main/java/org/worldfoundry/screensaver'
GRADLE = (APP / 'build.gradle.kts').read_text()
sys.path.insert(0, str(ROOT / 'scripts'))
import level_manifest  # noqa: E402

MANIFEST = level_manifest.read(ROOT / 'wflevels/clocks-menu.manifest')


def flavor_block(name):
    m = re.search(r'create\("' + name + r'"\)\s*\{(.*?)\n\s*\}', GRADLE, re.S)
    assert m, f'no {name} flavor in build.gradle.kts'
    return m.group(1)


def test_clocks_flavor_has_its_own_application_id():
    assert 'applicationId = "org.worldfoundry.clocks"' in flavor_block('clocks')


def test_gradle_copies_the_clocks_manifest_into_the_flavor_assets_as_levels_manifest():
    copy = re.search(r'val copyClocksLevelCatalog by tasks\.registering\(Copy::class\) \{(.*?)\n\}', GRADLE, re.S)
    assert copy, 'copyClocksLevelCatalog task missing'
    assert 'from(rootProject.file("../wflevels/clocks-menu.manifest"))' in copy.group(1)
    assert 'rename { "levels.manifest" }' in copy.group(1)
    assert 'into(clocksCatalogAssets)' in copy.group(1)
    assert 'sourceSets.getByName("clocks").assets.srcDir(clocksCatalogAssets)' in GRADLE
    assert re.search(r'tasks\.named\("preBuild"\) \{ dependsOn\([^)]*copyClocksLevelCatalog', GRADLE)
    assert 'LevelCatalog.ASSET' in (JAVA / 'TankChoice.java').read_text()
    assert re.search(r'ASSET = "levels\.manifest"', (JAVA / 'LevelCatalog.java').read_text())


def test_flavor_manifest_declares_the_three_clocks_components():
    xml = (APP / 'src/clocks/AndroidManifest.xml').read_text()
    for name in ['.ClocksActivity', '.ClocksDreamService', '.ClocksSettingsProvider']:
        assert f'android:name="{name}"' in xml, name
        assert (JAVA / f'{name[1:]}.java').is_file(), name
    assert xml.count('org.worldfoundry.clocks.settings') == 2      # the Dream's meta-data and the provider
    assert 'LEANBACK_LAUNCHER' in xml and 'android.service.dreams.DreamService' in xml


def test_clocks_flavor_does_not_copy_the_generic_classes():
    copies = [p for p in (APP / 'src').rglob('*.java')
              if p.name in ('LevelCatalog.java', 'LevelLaunch.java') and p.parent != JAVA]
    assert not copies, copies
    assert not list((APP / 'src/clocks').rglob('*.java'))


def test_launcher_opens_the_chooser_without_an_extra_and_starts_the_extra_through_level_launch():
    java = (JAVA / 'ClocksActivity.java').read_text()
    assert 'static final int SHOW_MENU = -1;' in java
    assert 'getIntent().getStringExtra(LevelLaunch.EXTRA_LEVEL)' in java
    assert 'if (requested == null) player.start(SHOW_MENU);' in java
    assert 'else if (!LevelLaunch.startChosen(this, player, requested)) finish();' in java


def test_dream_plays_the_saved_choice_never_the_chooser():
    java = (JAVA / 'ClocksDreamService.java').read_text()
    assert 'LevelLaunch.startChosen(this, player, null);' in java
    assert 'SHOW_MENU' not in java and 'start(-1)' not in java
    assert 'setInteractive(false);' in java


def test_only_the_settings_provider_writes_the_saved_choice():
    writers = sorted(p.name for p in JAVA.glob('*.java')
                     if 'TankChoice.set(' in p.read_text() and p.name != 'TankChoice.java')
    assert writers == ['ClocksSettingsProvider.java', 'TankSettingsProvider.java'], writers


def test_settings_provider_offers_random_and_every_clock_and_rejects_unknown_ids():
    java = (JAVA / 'ClocksSettingsProvider.java').read_text()
    assert 'static final String CLOCK = "clock";' in java
    assert 'AUTHORITY = "org.worldfoundry.clocks.settings"' in java
    assert 'TankChoice.RANDOM' in java and 'clocks.ids()' in java
    assert 'TankSettingsProvider.orientationSetting(' in java
    assert re.search(r'if \(!TankChoice\.valid\(getContext\(\), id\)\) throw new IllegalArgumentException', java)


def test_manifest_ids_are_stable_lowercase_and_not_the_reserved_random():
    for clock in MANIFEST.ids:
        assert re.fullmatch(r'[a-z][a-z0-9_]*', clock), clock
        assert clock != 'random'


def test_build_clocks_apk_packs_the_bundle_and_checks_both_abis():
    """The Chromecasts are armeabi-v7a only; the Pixel 8 Pro and the Lenovo tablet are arm64-v8a."""
    import yaml
    tasks = yaml.safe_load((ROOT / 'Taskfile.yml').read_text())['tasks']
    assert tasks['clocks-bundle']['deps'] == ['minute-machine-level']
    assert 'python3 scripts/pack-clocks-bundle.py' in ' '.join(tasks['clocks-bundle']['cmds'])
    apk = tasks['build-clocks-apk']
    assert apk['deps'] == ['clocks-bundle']
    script = '\n'.join(str(c) for c in apk['cmds'])
    assert ':screensaver:assembleClocksRelease --offline' in script
    assert 'set -euo pipefail' in script
    for abi in ('arm64-v8a', 'armeabi-v7a'):
        assert abi in script, abi
    assert re.search(r'abiFilters \+= setOf\("arm64-v8a", "armeabi-v7a"\)', GRADLE)


def test_clocks_replaces_the_minutemachine_flavor():
    """D2: one app for the clocks. The old flavor, its classes, source set, task and pack script are gone."""
    import yaml
    assert 'create("minutemachine")' not in GRADLE
    assert not (APP / 'src/minutemachine').exists()
    assert not list(JAVA.glob('MinuteMachine*.java'))
    assert not (ROOT / 'scripts/pack-minute-machine-bundle.py').exists()
    tasks = yaml.safe_load((ROOT / 'Taskfile.yml').read_text())['tasks']
    assert 'build-minute-machine-apk' not in tasks and 'minute-machine-level' in tasks
    icons = (ROOT / 'scripts/gen-screensaver-android-icons.py').read_text()
    assert '"clocks": build_clocks' in icons and 'minutemachine' not in icons
    for density in ('mdpi', 'hdpi', 'xhdpi', 'xxhdpi', 'xxxhdpi'):
        assert (APP / f'src/clocks/res/mipmap-{density}/ic_launcher.png').is_file(), density
    assert (APP / 'src/clocks/res/drawable/tv_banner.png').is_file()
