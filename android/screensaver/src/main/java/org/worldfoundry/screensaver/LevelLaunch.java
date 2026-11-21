package org.worldfoundry.screensaver;

import android.content.Context;
import android.util.Log;
import android.widget.Toast;

/**
 * Starts one level of the package: the saved choice (what the Dream plays), or the one-run
 * {@link #EXTRA_LEVEL} a launcher, adb or the coordinator passes. Generic: the decision is
 * {@link LevelCatalog#choose}, so any package with a LevelCatalog uses it unchanged.
 * docs/plans/2026-11-21-aquarium-menu-and-screensaver-launch.md, Phase 3.
 */
final class LevelLaunch {
    /** Intent string extra: a catalogue id or {@code random}. One run only; it is never saved. */
    static final String EXTRA_LEVEL = "org.worldfoundry.screensaver.LEVEL";
    private static final String TAG = "LevelLaunch";

    private LevelLaunch() { }

    /**
     * Choose the level, set its launch overrides, start it. {@code requested} is the LEVEL extra, or
     * null for the saved choice (Random is resolved once, here). An id the catalogue does not hold is
     * an error: log it, show it, start nothing, return false (the caller finishes). It never falls
     * back to the saved tank, and nothing is written to the saved choice on any path.
     */
    static boolean startChosen(Context context, TankPlayer player, String requested) {
        LevelCatalog catalog = TankChoice.catalog(context);
        String tank;
        try {
            tank = catalog.choose(requested, TankChoice.get(context), TankChoice.rng());
        } catch (IllegalArgumentException error) {
            Log.e(TAG, error.getMessage());
            Toast.makeText(context, error.getMessage(), Toast.LENGTH_LONG).show();
            return false;
        }
        if (LevelSettings.SEA_STARS_TANK.equals(tank)) {
            LevelSettings settings = LevelSettings.seaStars(context);
            player.launchOverrides(settings.schema(), settings.overrides());
        }
        player.start(catalog.indexOf(tank));
        return true;
    }
}
