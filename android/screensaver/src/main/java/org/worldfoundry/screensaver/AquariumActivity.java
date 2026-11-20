package org.worldfoundry.screensaver;

import android.app.Activity;
import android.os.Bundle;
import android.view.WindowManager;

public final class AquariumActivity extends Activity {
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
        TankLaunch.startChosen(this, player);
    }

    @Override
    protected void onPause() {
        player.stop();
        super.onPause();
        finish();
    }
}
