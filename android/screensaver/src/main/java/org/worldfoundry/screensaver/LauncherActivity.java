package org.worldfoundry.screensaver;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.view.KeyEvent;
import android.view.WindowManager;

/**
 * The launcher entry of every pack (WF Aquarium, WF Clocks): one app that is also the screensaver, and
 * the two behave identically (Will, 2026-11-21: "both clocks and aquarium should behave exactly the same").
 * {@link LaunchMode} decides what a start does:
 * <ul>
 *   <li>Launched normally, from the launcher or by a person: the engine's chooser menu over the pack's
 *       levels. Choosing one plays it for this run only; nothing here writes the saved choice. Back in a
 *       level returns to the menu; Back on the menu leaves.</li>
 *   <li>Started with the {@code LEVEL} extra (a catalogue id or {@code random}): that level, no menu.
 *       An unknown id starts nothing.</li>
 *   <li>Started with the {@code DREAM} extra: the saved choice, {@code random} by default.</li>
 * </ul>
 * The Dream service and the preview activity never show the menu. The pack's roster is its menu
 * manifest, read by {@link LevelCatalog}; the menu itself is the engine's, from the pack's bundle
 * (dream_host.cc). docs/howto/combine-levels-chooser-and-screensaver-launch.md, section 4;
 * docs/plans/2026-11-21-one-aquarium-app.md.
 */
public abstract class LauncherActivity extends Activity {
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
