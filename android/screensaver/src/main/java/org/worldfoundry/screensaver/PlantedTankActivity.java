package org.worldfoundry.screensaver;

import android.app.Activity;
import android.os.Bundle;
import android.util.Log;
import android.view.WindowManager;
import android.widget.Toast;

/**
 * Launches the Planted Tank on demand. Intent extras ({@code --es water}, {@code --el seed},
 * {@code --ef speed}, {@code --ei hold}, {@code --ef age}, {@code --ez textures},
 * {@code --ez sway}) overlay the saved settings for this run only and are never saved.
 */
public final class PlantedTankActivity extends Activity {
    private static final String TAG = "planted";

    private TankPlayer player;
    private String line;

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        try {
            line = overlay(PlantedSettings.load(this), getIntent().getExtras()).toLine();
        } catch (IllegalArgumentException rejected) {
            Log.e(TAG, rejected.getMessage());
            Toast.makeText(this, rejected.getMessage(), Toast.LENGTH_LONG).show();
            finish();
            return;
        }
        getWindow().setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN,
                WindowManager.LayoutParams.FLAG_FULLSCREEN);
        player = new TankPlayer(this);
        setContentView(player.view());
    }

    @SuppressWarnings("deprecation")
    private static PlantedConfig overlay(PlantedConfig base, Bundle extras) {
        if (extras == null) return base;
        PlantedConfig config = base;
        for (String key : PlantedConfig.KEYS) {
            if (extras.containsKey(key)) config = config.with(key, extras.get(key));
        }
        return config;
    }

    @Override protected void onResume() {
        super.onResume();
        if (player == null) return;
        player.configure(line);
        player.start(0);
    }

    @Override protected void onPause() {
        if (player != null) player.stop();
        super.onPause();
        finish();
    }
}
