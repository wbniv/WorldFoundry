package org.worldfoundry.screensaver;

import android.content.Context;
import android.content.SharedPreferences;

/** The saved Planted Tank values shared by the Dream, the launcher activity and the settings call. */
final class PlantedSettings {
    private static final String PREFS = "planted";

    private PlantedSettings() { }

    /** Defaults overlaid with whatever was saved; an unreadable saved value is ignored. */
    static PlantedConfig load(Context context) {
        SharedPreferences prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        PlantedConfig config = PlantedConfig.defaults();
        for (String key : PlantedConfig.KEYS) {
            String saved = prefs.getString(key, null);
            if (saved == null) continue;
            try {
                config = config.with(key, saved);
            } catch (IllegalArgumentException stale) {
                // A bad saved value must never stop the Dream; fall back to the default.
            }
        }
        return config;
    }

    /**
     * Validates and saves one value, returning whether it was written. Throws
     * IllegalArgumentException with the rejection message and saves nothing when invalid.
     */
    static boolean set(Context context, String key, String value) {
        String canonical = PlantedConfig.defaults().with(key, value).valueOf(key);
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit().putString(key, canonical).commit();
    }

    /** Forgets every saved value so all keys return to their defaults. */
    static boolean reset(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().clear().commit();
    }
}
