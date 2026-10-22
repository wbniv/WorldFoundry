package org.worldfoundry.screensaver;

import android.app.Activity;
import android.os.Bundle;
import android.view.WindowManager;

/** Launches the Seahorse Grid Dream's own level on demand. */
public final class SeahorseGridActivity extends Activity {
    private TankPlayer player;

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN,
                WindowManager.LayoutParams.FLAG_FULLSCREEN);
        player = new TankPlayer(this);
        setContentView(player.view());
    }

    @Override protected void onResume() {
        super.onResume();
        player.start(0);
    }

    @Override protected void onPause() {
        player.stop();
        super.onPause();
        finish();
    }
}
