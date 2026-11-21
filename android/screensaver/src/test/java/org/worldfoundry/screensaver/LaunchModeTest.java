package org.worldfoundry.screensaver;

import java.io.FileInputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import java.util.stream.Stream;

/**
 * Plain-Java checks of LaunchMode, the one app's mode decision (JUnit is not in the offline Gradle
 * cache). Run with:
 * javac -d out src/main/java/.../LaunchMode.java src/main/java/.../LevelCatalog.java src/test/java/.../LaunchModeTest.java
 * java -cp out org.worldfoundry.screensaver.LaunchModeTest wflevels/aquarium-menu.manifest android/screensaver/src/main/java/org/worldfoundry/screensaver
 *
 * <p>Every row of the table in docs/plans/2026-11-21-one-aquarium-app.md (Verification 1), an
 * unknown LEVEL refused by the real catalogue exactly as the LevelLaunch contract says, and source
 * guards for the rows that are not a function call: the Dream and the preview never reach the menu,
 * and nothing but the settings provider writes the saved tank (Verification 2).
 */
public final class LaunchModeTest {
    private static int checks;
    private static int failures;

    private static void check(boolean ok, String what) {
        checks++;
        if (!ok) {
            failures++;
            System.out.println("FAIL " + what);
        }
    }

    private static void mode(String level, boolean dream, String wanted) {
        String got = LaunchMode.forLauncherActivity(level, dream).toString();
        check(wanted.equals(got), "level=" + level + " dream=" + dream + ": " + got + ", wanted " + wanted);
    }

    private static String read(Path path) throws IOException {
        return new String(Files.readAllBytes(path), StandardCharsets.UTF_8);
    }

    public static void main(String[] args) throws IOException {
        // A plain MAIN + LEANBACK_LAUNCHER start (the launcher, Homeboard's app tile, recents): the menu.
        mode(null, false, "MENU");
        // DREAM extra (any value, as ScreensaverPreviewActivity takes it): the screensaver's saved content.
        mode(null, true, "PLAY_SAVED");
        // LEVEL extra: one run of that level, whatever DREAM says; LEVEL wins, as on the preview.
        mode("aquarium_plants", false, "PLAY_LEVEL(aquarium_plants)");
        mode("aquarium_plants", true, "PLAY_LEVEL(aquarium_plants)");
        mode("random", false, "PLAY_LEVEL(random)");
        mode("random", true, "PLAY_LEVEL(random)");
        // Present but not a catalogue id: still PLAY_LEVEL, so the catalogue refuses it; never the menu.
        mode("aquarium_no_such_tank", false, "PLAY_LEVEL(aquarium_no_such_tank)");
        mode("", false, "PLAY_LEVEL()");
        mode("3", false, "PLAY_LEVEL(3)");   // an --ei LEVEL 3 arrives as its text
        check(LaunchMode.forLauncherActivity(null, false) == LaunchMode.MENU, "MENU is the shared value");
        check(LaunchMode.forLauncherActivity("random", false).level.equals("random"), "level carried");
        check(LaunchMode.forLauncherActivity(null, true).level == null, "PLAY_SAVED carries no level");

        if (args.length >= 1) {
            // What LevelLaunch.startChosen does with each PLAY_LEVEL: catalog.choose(requested, saved, rng).
            LevelCatalog real = LevelCatalog.read(new FileInputStream(args[0]), args[0]);
            Random rng = new Random(3);
            for (String id : real.ids()) {
                LaunchMode m = LaunchMode.forLauncherActivity(id, false);
                check(id.equals(real.choose(m.level, "random", rng)), id + " plays itself, not the saved tank");
            }
            check(real.valid(real.choose(LaunchMode.forLauncherActivity("random", false).level, "aquarium", rng)),
                    "LEVEL=random draws a tank");
            check("aquarium".equals(real.choose(LaunchMode.forLauncherActivity(null, true).level, "aquarium", rng)),
                    "PLAY_SAVED plays the saved tank");
            for (String bad : new String[] {"aquarium_no_such_tank", "", "3", "aquarium_plants-standalone.iff"}) {
                try {
                    real.choose(LaunchMode.forLauncherActivity(bad, false).level, "aquarium", rng);
                    check(false, "unknown LEVEL \"" + bad + "\" was accepted");
                } catch (IllegalArgumentException refused) {
                    check(refused.getMessage().contains("\"" + bad + "\""),
                            "the refusal names \"" + bad + "\": " + refused.getMessage());
                }
            }
        }

        if (args.length >= 2) {
            Path java = Paths.get(args[1]);
            // The Dream and the preview never consult LaunchMode and never start the menu.
            for (String name : new String[] {"AquariumDreamService", "ScreensaverPreviewActivity"}) {
                String text = read(java.resolve(name + ".java"));
                check(!text.contains("LaunchMode") && !text.contains("startMenu") && !text.contains("TankPlayer.MENU"),
                        name + " must not reach the menu");
                check(text.contains("LevelLaunch.startChosen(this, player, "), name + " still starts through LevelLaunch");
            }
            String activity = read(java.resolve("AquariumActivity.java"));
            check(activity.contains("LaunchMode.forLauncherActivity("), "AquariumActivity decides through LaunchMode");
            check(activity.contains("player.startMenu()"), "AquariumActivity starts the menu for MENU");
            // The menu changes nothing that is saved: TankChoice.set has one caller, the settings provider.
            List<String> writers = new ArrayList<>();
            try (Stream<Path> files = Files.list(java)) {
                for (Path p : (Iterable<Path>) files::iterator) {
                    String name = p.getFileName().toString();
                    if (name.endsWith(".java") && read(p).contains("TankChoice.set(")) writers.add(name);
                }
            }
            check(writers.size() == 1 && writers.get(0).equals("TankSettingsProvider.java"),
                    "only TankSettingsProvider writes the saved tank, found " + writers);
            check(!activity.contains("getSharedPreferences") && !activity.contains("TankChoice.set"),
                    "AquariumActivity writes no preference");
        }

        System.out.println(checks + " checks, " + failures + " failures");
        if (failures != 0) System.exit(1);
    }
}
