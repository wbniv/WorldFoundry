package org.worldfoundry.screensaver;

import android.content.Context;
import android.content.SharedPreferences;

/**
 * The saved orientation; each flavor is its own package, so each screensaver has its own.
 * Nothing saved means R.string.default_orientation (res/values/orientation.xml).
 */
final class OrientationSettings {
    private static final String PREFS = "screensaver";
    private static final String KEY = "orientation";

    private OrientationSettings() { }

    static String load(Context context) {
        SharedPreferences prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        return OrientationChoice.savedOrDefault(prefs.getString(KEY, null),
                context.getString(R.string.default_orientation));
    }

    /** Validates and saves; throws IllegalArgumentException and saves nothing when invalid. */
    static boolean set(Context context, String id) {
        String canonical = OrientationChoice.parse(id);
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit().putString(KEY, canonical).commit();
    }

    /** Restore the default without clearing unrelated saved settings. */
    static boolean clear(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit().remove(KEY).commit();
    }
}
