package org.worldfoundry.screensaver;

import android.app.Activity;
import android.os.Bundle;
import android.view.WindowManager;

/** Shows the same live level as the selected Dream on demand. */
public final class ScreensaverPreviewActivity extends Activity {
    public static final String EXTRA_DREAM = "org.worldfoundry.screensaver.DREAM";
    public static final String SEAHORSE_GRID = "seahorse_grid";

    private TankPlayer player;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN,
                WindowManager.LayoutParams.FLAG_FULLSCREEN);
        player = new TankPlayer(this);
        setContentView(player.view());
    }

    @Override
    protected void onResume() {
        super.onResume();
        String dream = getIntent().getStringExtra(EXTRA_DREAM);
        int level = SEAHORSE_GRID.equals(dream)
                ? 0 : TankChoice.indexOf(TankChoice.chooseForDream(this));
        player.start(level);
    }

    @Override
    protected void onPause() {
        player.stop();
        super.onPause();
        finish();
    }
}
