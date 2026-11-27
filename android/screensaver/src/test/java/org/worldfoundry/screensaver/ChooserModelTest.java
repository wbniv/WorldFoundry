package org.worldfoundry.screensaver;

import java.io.FileInputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Arrays;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Plain-Java checks of ChooserModel, the "use for screensaver" chooser's logic (JUnit is not in the
 * offline Gradle cache), and a source guard that the chooser knows no pack. Run with:
 * javac -d out .../LevelCatalog.java .../ChooserModel.java .../ChooserModelTest.java
 * java -cp out org.worldfoundry.screensaver.ChooserModelTest <java dir> <main res dir> <manifest>...
 *
 * <p>docs/plans/2026-11-27-screensaver-chooser.md, Verification 1, with Will's decisions (D4: no
 * Random row; nothing chosen still means Random) and his requirement that one chooser serves every
 * World Foundry screensaver pack, present and future.
 */
public final class ChooserModelTest {
    private static int checks;
    private static int failures;

    private static void check(boolean ok, String what) {
        checks++;
        if (!ok) {
            failures++;
            System.out.println("FAIL " + what);
        }
    }

    private static boolean throwsIllegalArgument(Runnable r) {
        try {
            r.run();
            return false;
        } catch (IllegalArgumentException expected) {
            return true;
        }
    }

    private static String read(Path p) throws IOException {
        return new String(Files.readAllBytes(p), StandardCharsets.UTF_8);
    }

    /** A made-up pack: the chooser must work from any roster and setting id it is given. */
    private static final String INVENTED = "title WF Orrery\nprompt Choose a planet\n"
            + "level mercury-standalone.iff | Mercury\n"
            + "level venus-standalone.iff | Venus | Morning Star\n"
            + "level mars-standalone.iff | Mars\n";

    private static void invented() {
        LevelCatalog roster = LevelCatalog.parse(INVENTED, "invented");
        ChooserModel m = ChooserModel.of(roster, "planet", null);
        check(m.size() == 3, "rows are the roster's levels, no Random row: " + m.size());
        check(m.id(0).equals("mercury") && m.id(1).equals("venus") && m.id(2).equals("mars"), "rows keep the roster order");
        check(m.label(1).equals("Morning Star"), "a row shows the Dream label: " + m.label(1));
        check(m.saved() == null && m.random() && m.missing() == null, "nothing saved: no row saved, Random plays");
        check(m.initialFocus() == 0, "nothing saved: focus on the first row");
        check("planet:venus".equals(m.choose("venus")), "a choice is sent under the given setting id: " + m.choose("venus"));
        check(throwsIllegalArgument(() -> m.choose("random")), "Random is not a row (D4)");
        check(throwsIllegalArgument(() -> m.choose("pluto")), "an id that is not a row is refused");
        m.chosen("venus");
        check("venus".equals(m.saved()) && m.isSaved(1) && !m.random(), "after saving, that row is saved");
        check("random".equals(m.undoValue()) && "venus".equals(m.undoRow()), "Undo returns to Random when nothing was chosen");
        check("planet:random".equals(m.undoArgument()), "Undo sends random: " + m.undoArgument());
        check(m.choose("venus") == null, "OK on the saved row writes nothing");
        m.chosen("mars");
        check("venus".equals(m.undoValue()) && "mars".equals(m.undoRow()), "Undo is one step: the value before the last save");
        m.undone();
        check("venus".equals(m.saved()) && m.undoValue() == null && m.undoRow() == null, "Undo restores once, then goes");
        check(m.undoArgument() == null, "no Undo after Undo");
        boolean threw = false;
        try { m.undone(); } catch (IllegalStateException expected) { threw = true; }
        check(threw, "a second Undo is refused");

        ChooserModel shared = ChooserModel.of(roster, ChooserModel.SETTING, "mars");
        check("level:venus".equals(shared.choose("venus")), "the shared setting id is level");
        check(shared.initialFocus() == 2 && shared.isSaved(2), "focus starts on the saved row");

        ChooserModel gone = ChooserModel.of(roster, ChooserModel.SETTING, "saturn");
        check("saturn".equals(gone.missing()) && gone.saved() == null && !gone.random(),
                "a saved level the roster no longer holds is reported missing (D9)");
        check(gone.initialFocus() == 0, "missing: focus on the first row");
        gone.chosen("mercury");
        check(gone.undoValue() == null && gone.undoRow() == null, "no Undo back to a missing level");
        check(gone.missing() == null && "mercury".equals(gone.saved()), "choosing replaces the missing level");

        ChooserModel stated = ChooserModel.of(roster, ChooserModel.SETTING, "random");
        check(stated.random() && stated.saved() == null && stated.missing() == null, "a saved random reads as nothing chosen");

        ChooserModel moved = ChooserModel.of(roster, ChooserModel.SETTING, "mercury");
        moved.chosen("venus");
        moved.refresh("venus");
        check("mercury".equals(moved.undoValue()), "reading back the same value keeps Undo");
        moved.refresh("mars");
        check(moved.undoValue() == null && "mars".equals(moved.saved()), "a value saved elsewhere drops Undo and shows");

        ChooserModel rotated = ChooserModel.of(roster, ChooserModel.SETTING, "venus");
        rotated.restoreUndo("mercury", "venus");
        check("mercury".equals(rotated.undoValue()), "Undo survives a configuration change");
        ChooserModel stale = ChooserModel.of(roster, ChooserModel.SETTING, "mars");
        stale.restoreUndo("mercury", "venus");
        check(stale.undoValue() == null, "a kept Undo for a row no longer saved is dropped");

        check(throwsIllegalArgument(() -> ChooserModel.of(roster, "", null)), "a setting id is required");
    }

    /** Every shipped roster: rows equal the roster, in order, with its labels. */
    private static void shipped(String manifest) throws IOException {
        LevelCatalog roster = LevelCatalog.read(new FileInputStream(manifest), manifest);
        ChooserModel m = ChooserModel.of(roster, ChooserModel.SETTING, null);
        check(m.size() == roster.size(), manifest + ": one row per level");
        for (int i = 0; i < m.size(); i++) {
            check(m.id(i).equals(roster.ids().get(i)) && m.label(i).equals(roster.label(m.id(i))),
                    manifest + ": row " + i + " is the roster's level " + i);
        }
        String last = roster.ids().get(roster.size() - 1);
        check(("level:" + last).equals(m.choose(last)), manifest + ": its last level is saved as level:" + last);
    }

    /** The chooser and its helpers name no pack: everything per pack comes from data. */
    private static void guard(Path java, Path res) throws IOException {
        Pattern pack = Pattern.compile("aquarium|clock|tank|seahorse|planted|lava|tide");
        for (String name : new String[] {"ScreensaverChooserActivity.java", "ChooserModel.java"}) {
            String text = read(java.resolve(name)).toLowerCase(Locale.ROOT);
            Matcher hit = pack.matcher(text);
            boolean found = hit.find();
            check(!found, name + " names a pack" + (found ? " (\"" + hit.group() + "\")" : "") + ": per-pack facts must come from data");
        }
        for (String dir : new String[] {"values", "values-th", "values-es"}) {
            Path strings = res.resolve(dir).resolve("chooser_strings.xml");
            String text = read(strings).toLowerCase(Locale.ROOT).replaceAll("(?s)<!--.*?-->", "");
            check(!pack.matcher(text).find(), dir + "/chooser_strings.xml names a pack");
        }
        String activity = read(java.resolve("ScreensaverChooserActivity.java"));
        check(!activity.contains("getSharedPreferences") && !activity.contains("TankChoice")
                        && !activity.contains("LevelChoiceCalls"),
                "the chooser reads and writes only through its pack's settings provider");
        check(activity.contains("ChooserModel.GET_METHOD") && activity.contains("ChooserModel.SET_METHOD"),
                "the chooser calls the provider's shared level methods");
        check(activity.contains("SETTINGS_AUTHORITY"), "the chooser finds the provider from the Dream's declared authority");
        check(activity.contains("LevelLaunch.EXTRA_LEVEL") && activity.contains("ScreensaverPreviewActivity.class"),
                "Preview is the existing preview screen with LEVEL=<id> (D5)");
        check(!activity.contains("RANDOM, ") && !activity.contains("choose(ChooserModel.RANDOM"), "no Random row is built (D4)");
    }

    public static void main(String[] args) throws IOException {
        if (args.length < 3) {
            System.err.println("usage: ChooserModelTest <java dir> <main res dir> <manifest>...");
            System.exit(2);
        }
        invented();
        for (String manifest : Arrays.copyOfRange(args, 2, args.length)) shipped(manifest);
        guard(Paths.get(args[0]), Paths.get(args[1]));
        System.out.println(checks + " checks, " + failures + " failures");
        if (failures != 0) System.exit(1);
    }
}
