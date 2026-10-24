package org.worldfoundry.screensaver;

import android.app.Activity;
import android.os.Bundle;
import android.util.Log;
import android.view.WindowManager;
import android.widget.Toast;
import org.json.JSONException;
import org.json.JSONObject;

/**
 * Launches the Planted Tank on demand. Intent extras ({@code --es water}, {@code --el seed},
 * {@code --ef speed}, {@code --ei hold}, {@code --ef age}, {@code --ez textures},
 * {@code --ez sway}) overlay the saved settings for this run only and are never saved.
 * The Settings launch overrides may also carry the app-level orientation for this run.
 */
public final class PlantedTankActivity extends Activity {
    private static final String TAG = "planted";
    static final String SETTINGS_OVERRIDES_EXTRA = "org.worldfoundry.settings.OVERRIDES";

    private TankPlayer player;
    private String line;
    private String orientation;

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        orientation = OrientationSettings.load(this);
        try {
            line = overlay(PlantedSettings.load(this), getIntent().getExtras()).toLine();
        } catch (IllegalArgumentException | JSONException rejected) {
            Log.e(TAG, rejected.getMessage());
            Toast.makeText(this, rejected.getMessage(), Toast.LENGTH_LONG).show();
            finish();
            return;
        }
        getWindow().setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN,
                WindowManager.LayoutParams.FLAG_FULLSCREEN);
        DreamOrientation.apply(this, orientation);
        // A passive preview has no touch input to reset the phone's screen timeout.
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        player = new TankPlayer(this);
        setContentView(player.view());
    }

    @SuppressWarnings("deprecation")
    private PlantedConfig overlay(PlantedConfig base, Bundle extras) throws JSONException {
        if (extras == null) return base;
        PlantedConfig config = base;
        for (String key : PlantedConfig.KEYS) {
            if (extras.containsKey(key)) config = config.with(key, extras.get(key));
        }
        if (extras.containsKey(SETTINGS_OVERRIDES_EXTRA)) {
            String json = extras.getString(SETTINGS_OVERRIDES_EXTRA);
            if (json == null || json.length() > 8192) {
                throw new IllegalArgumentException("Invalid Settings launch overrides");
            }
            JSONObject updates = new JSONObject(json);
            // overlay validates every override (and their count) first.
            PlantedConfig overlaid = PlantedSettingsProvider.overlay(this, config, updates);
            String launched = PlantedSettingsProvider.launchOrientation(this, config, updates);
            if (launched != null) orientation = launched;
            config = overlaid;
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
