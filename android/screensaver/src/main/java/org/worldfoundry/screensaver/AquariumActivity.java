package org.worldfoundry.screensaver;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.view.KeyEvent;
import android.view.WindowManager;

/**
 * The TV launcher entry. Launched normally it shows the tank menu (the engine's level menu over the
 * playable tanks, as the Aquarium game app shows it); started with the LEVEL or DREAM extra it plays
 * a tank as the screensaver does. {@link LaunchMode} decides. docs/plans/2026-11-21-one-aquarium-app.md.
 */
public final class AquariumActivity extends Activity {
    private TankPlayer player;
    private LaunchMode mode;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN,
                WindowManager.LayoutParams.FLAG_FULLSCREEN);
        DreamOrientation.apply(this, OrientationSettings.load(this));
        mode = modeOf(getIntent());
        player = new TankPlayer(this);
        // Back on the menu ends the engine; the activity follows it out.
        player.onEngineExit(this::finish);
        setContentView(player.view());
    }

    @SuppressWarnings("deprecation")   // Bundle.get: the LEVEL extra of any type, refused unless it is a known id
    private static LaunchMode modeOf(Intent intent) {
        Bundle extras = intent.getExtras();
        Object level = extras == null ? null : extras.get(LevelLaunch.EXTRA_LEVEL);
        boolean dream = extras != null && extras.containsKey(ScreensaverPreviewActivity.EXTRA_DREAM);
        return LaunchMode.forLauncherActivity(level == null ? null : String.valueOf(level), dream);
    }

    @Override
    protected void onResume() {
        super.onResume();
        switch (mode.kind) {
            case MENU:
                // The menu starts a tank for this run only: nothing here writes the saved choice.
                player.startMenu();
                break;
            case PLAY_LEVEL:
                if (!LevelLaunch.startChosen(this, player, mode.level)) finish();
                break;
            default:
                if (!LevelLaunch.startChosen(this, player, null)) finish();
                break;
        }
    }

    /** The menu takes the remote's keys; Back navigates it. Elsewhere every key keeps its meaning. */
    @Override
    public boolean dispatchKeyEvent(KeyEvent event) {
        if (mode.kind == LaunchMode.Kind.MENU) {
            int action = event.getAction();
            if (event.getKeyCode() == KeyEvent.KEYCODE_BACK) {
                if (action == KeyEvent.ACTION_UP && !event.isCanceled()) player.back();
                return true;
            }
            if ((action == KeyEvent.ACTION_DOWN || action == KeyEvent.ACTION_UP)
                    && player.key(event.getKeyCode(), action == KeyEvent.ACTION_DOWN)) {
                return true;
            }
        }
        return super.dispatchKeyEvent(event);
    }

    @Override
    protected void onPause() {
        player.stop();
        super.onPause();
        finish();
    }
}
