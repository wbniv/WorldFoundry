package org.worldfoundry.screensaver;

import android.app.Activity;
import android.os.Bundle;
import android.view.SurfaceView;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;

/**
 * Tide Harbour Phase 0 spike: plays level N of the spike bundle (0 to 6 = variants a, b, c, d, n, v, g), N from the intent extra
 * "level" (default 0). Throwaway; see docs/plans/2026-11-21-tide-harbour-clock.md, Phase 0.
 */
public class TideSpikeActivity extends Activity {
    private TankPlayer player;
    private int level;

    /** The level to play: the intent extra "level", unless a subclass fixes it. The coordinator starts a registered activity with no extras. */
    protected int level() { return getIntent().getIntExtra("level", 0); }

    /** True: draw to a fixed 1280 x 720 surface the compositor scales up (the night probe's fill-rate test). */
    protected boolean lowRes() { return false; }

    private static void fixSurfaceSize(View v) {
        if (v instanceof SurfaceView) {
            ((SurfaceView) v).getHolder().setFixedSize(1280, 720);
        } else if (v instanceof ViewGroup) {
            ViewGroup g = (ViewGroup) v;
            for (int i = 0; i < g.getChildCount(); i++) fixSurfaceSize(g.getChildAt(i));
        }
    }

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN,
                WindowManager.LayoutParams.FLAG_FULLSCREEN);
        level = level();
        player = new TankPlayer(this);
        setContentView(player.view());
        if (lowRes()) fixSurfaceSize(player.view());
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
