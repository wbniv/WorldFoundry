package org.worldfoundry.screensaver;

import android.app.Activity;
import android.os.Bundle;
import android.view.WindowManager;

/**
 * Tide Harbour Phase 0 spike: plays level N of the spike bundle (0 to 3 = variants a to d), N from the intent extra
 * "level" (default 0). Throwaway; see docs/plans/2026-11-21-tide-harbour-clock.md, Phase 0.
 */
public class TideSpikeActivity extends Activity {
    private TankPlayer player;
    private int level;

    /** The level to play: the intent extra "level", unless a subclass fixes it. The coordinator starts a registered activity with no extras. */
    protected int level() { return getIntent().getIntExtra("level", 0); }

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN,
                WindowManager.LayoutParams.FLAG_FULLSCREEN);
        level = level();
        player = new TankPlayer(this);
        setContentView(player.view());
    }

    @Override protected void onResume() {
        super.onResume();
        player.start(level);
    }

    @Override protected void onPause() {
        player.stop();
        super.onPause();
        finish();
    }
}
