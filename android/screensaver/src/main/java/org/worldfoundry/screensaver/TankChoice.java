package org.worldfoundry.screensaver;

import android.content.Context;
import android.content.SharedPreferences;

import java.security.SecureRandom;

/**
 * The content choice shared by the TV app, Dream, and coordinator settings call. The tanks are the
 * package's LevelCatalog (wflevels/aquarium-menu.manifest, the one roster), read once per process.
 */
final class TankChoice {
    static final String RANDOM = LevelCatalog.RANDOM;

    private static final String PREFS = "screensaver";
    private static final String KEY = "tank";
    private static final SecureRandom RNG = new SecureRandom();

    private TankChoice() { }

    /** The package's tanks, from its levels.manifest asset. */
    static LevelCatalog catalog(Context context) {
        final Context app = context.getApplicationContext() != null ? context.getApplicationContext() : context;
        return LevelCatalog.shared(() -> app.getAssets().open(LevelCatalog.ASSET));
    }

    static boolean valid(Context context, String id) {
        return catalog(context).valid(id);
    }

    static int indexOf(Context context, String id) {
        return catalog(context).indexOf(id);
    }

    static String get(Context context) {
        SharedPreferences prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        String id = prefs.getString(KEY, RANDOM);
        return valid(context, id) ? id : RANDOM;
    }

    static boolean set(Context context, String id) {
        if (!valid(context, id)) return false;
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit().putString(KEY, id).commit();
    }

    /** The generator that resolves Random, once per run (see LevelCatalog#choose). */
    static SecureRandom rng() {
        return RNG;
    }
}
