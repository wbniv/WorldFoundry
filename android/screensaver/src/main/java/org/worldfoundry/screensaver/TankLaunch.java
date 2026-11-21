package org.worldfoundry.screensaver;

import android.content.Context;

/** Starts the Dream's chosen tank, handing the engine that tank's saved level settings first. */
final class TankLaunch {
    private TankLaunch() { }

    /** Choose the tank (Random is resolved once, here), set its launch overrides, start it. */
    static void startChosen(Context context, TankPlayer player) {
        String tank = TankChoice.chooseForDream(context);
        if (LevelSettings.SEA_STARS_TANK.equals(tank)) {
            LevelSettings settings = LevelSettings.seaStars(context);
            player.launchOverrides(settings.schema(), settings.overrides());
        }
        player.start(TankChoice.indexOf(tank));
    }
}
