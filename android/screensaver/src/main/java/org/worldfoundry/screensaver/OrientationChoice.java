package org.worldfoundry.screensaver;

/**
 * The screensaver's orientation choice, shared by every Dream, launcher activity and settings
 * call. Free of Android classes so OrientationChoiceTest runs under plain javac.
 */
final class OrientationChoice {
    static final String LANDSCAPE = "landscape";
    static final String SENSOR_LANDSCAPE = "sensor-landscape";
    static final String FOLLOW_DEVICE = "follow-device";
    /** Used when the R.string.default_orientation resource itself is not a valid value. */
    static final String FALLBACK = LANDSCAPE;

    static final String[] IDS = { LANDSCAPE, SENSOR_LANDSCAPE, FOLLOW_DEVICE };
    static final String[] LABELS = { "Landscape", "Sensor landscape", "Follow device" };

    // android.content.pm.ActivityInfo constants, inlined so this class needs no android.jar.
    static final int SCREEN_ORIENTATION_UNSPECIFIED = -1;
    static final int SCREEN_ORIENTATION_LANDSCAPE = 0;
    static final int SCREEN_ORIENTATION_SENSOR_LANDSCAPE = 6;

    private OrientationChoice() { }

    static boolean valid(String id) {
        for (String candidate : IDS) {
            if (candidate.equals(id)) return true;
        }
        return false;
    }

    /** The canonical value, or IllegalArgumentException for anything not offered. */
    static String parse(String id) {
        if (!valid(id)) throw new IllegalArgumentException("Unknown orientation: " + id);
        return id;
    }

    /**
     * A saved value that is missing or unreadable must never stop the Dream; use the app's
     * default (the R.string.default_orientation resource), or landscape if that is invalid too.
     */
    static String savedOrDefault(String saved, String appDefault) {
        if (valid(saved)) return saved;
        return valid(appDefault) ? appDefault : FALLBACK;
    }

    /** The ActivityInfo.SCREEN_ORIENTATION_* value an orientation requests. */
    static int requestedOrientation(String id) {
        switch (parse(id)) {
            case SENSOR_LANDSCAPE: return SCREEN_ORIENTATION_SENSOR_LANDSCAPE;
            case FOLLOW_DEVICE: return SCREEN_ORIENTATION_UNSPECIFIED;
            default: return SCREEN_ORIENTATION_LANDSCAPE;
        }
    }
}
