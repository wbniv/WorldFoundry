package org.worldfoundry.screensaver;

import android.app.Activity;
import android.os.Bundle;
import android.view.WindowManager;

/**
 * WF Clocks' TV launcher entry (clocks flavor). With no {@link LevelLaunch#EXTRA_LEVEL} it opens the
 * engine's chooser (the MENU chunk of wflevels/clocks-menu.manifest): the player gets -1 and the host
 * leaves out the positional level. With the extra it starts that clock id through the shared
 * LevelLaunch, and an unknown id starts nothing. Neither path writes the saved Dream choice.
 * docs/plans/2026-11-21-tide-harbour-clock.md, decision D3.
 */
public final class ClocksActivity extends Activity {
    /** TankPlayer.start's "show the menu" index; dream_host.cc omits the positional level for it. */
    static final int SHOW_MENU = -1;

    private TankPlayer player;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN,
                WindowManager.LayoutParams.FLAG_FULLSCREEN);
        DreamOrientation.apply(this, OrientationSettings.load(this));
        player = new TankPlayer(this);
        setContentView(player.view());
    }

    @Override
    protected void onResume() {
        super.onResume();
        String requested = getIntent().getStringExtra(LevelLaunch.EXTRA_LEVEL);
        if (requested == null) player.start(SHOW_MENU);
        else if (!LevelLaunch.startChosen(this, player, requested)) finish();
    }

    @Override
    protected void onPause() {
        player.stop();
        super.onPause();
        finish();
    }
}
