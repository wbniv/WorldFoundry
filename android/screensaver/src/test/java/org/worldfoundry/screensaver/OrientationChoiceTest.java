package org.worldfoundry.screensaver;

/**
 * Plain-Java checks of OrientationChoice (JUnit is not in the offline Gradle cache). Run with:
 * javac -d out src/main/java/.../OrientationChoice.java src/test/java/.../OrientationChoiceTest.java
 * java -cp out org.worldfoundry.screensaver.OrientationChoiceTest
 *
 * <p>DreamOrientation.apply needs a real Window, so it is checked on a device (plan steps 3-7).
 */
public final class OrientationChoiceTest {
    private static int checks;
    private static int failures;

    private static void check(boolean ok, String what) {
        checks++;
        if (!ok) {
            failures++;
            System.out.println("FAIL " + what);
        }
    }

    private static void rejects(String id) {
        try {
            String got = OrientationChoice.parse(id);
            check(false, "parse(" + id + ") was accepted as " + got);
        } catch (IllegalArgumentException error) {
            check(error.getMessage().contains("Unknown orientation"),
                    "parse(" + id + ") message \"" + error.getMessage() + "\"");
        }
        try {
            OrientationChoice.requestedOrientation(id);
            check(false, "requestedOrientation(" + id + ") was accepted");
        } catch (IllegalArgumentException expected) {
            check(true, "requestedOrientation rejects " + id);
        }
    }

    public static void main(String[] args) {
        check(OrientationChoice.DEFAULT.equals("landscape"), "default is landscape");
        check(OrientationChoice.IDS.length == 3 && OrientationChoice.LABELS.length == 3,
                "three values, each with a label");

        for (String id : OrientationChoice.IDS) {
            check(OrientationChoice.valid(id), id + " is valid");
            check(id.equals(OrientationChoice.parse(id)), "parse(" + id + ") is canonical");
            check(id.equals(OrientationChoice.savedOrDefault(id)), "saved " + id + " is kept");
        }

        // The values must equal android.content.pm.ActivityInfo.SCREEN_ORIENTATION_*.
        check(OrientationChoice.requestedOrientation("landscape") == 0, "landscape -> LANDSCAPE (0)");
        check(OrientationChoice.requestedOrientation("sensor-landscape") == 6,
                "sensor-landscape -> SENSOR_LANDSCAPE (6)");
        check(OrientationChoice.requestedOrientation("follow-device") == -1,
                "follow-device -> UNSPECIFIED (-1)");

        rejects("portrait");
        rejects("Landscape");
        rejects(" landscape");
        rejects("");
        rejects(null);

        check(OrientationChoice.savedOrDefault(null).equals("landscape"), "nothing saved -> default");
        check(OrientationChoice.savedOrDefault("portrait").equals("landscape"), "stale saved -> default");

        System.out.println(checks + " checks, " + failures + " failures");
        if (failures > 0) System.exit(1);
    }
}
