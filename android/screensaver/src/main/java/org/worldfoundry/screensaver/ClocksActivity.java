package org.worldfoundry.screensaver;

import android.app.Activity;
import android.os.Bundle;
import android.view.KeyEvent;
import android.view.WindowManager;

/**
 * WF Clocks' TV launcher entry (clocks flavor). With no {@link LevelLaunch#EXTRA_LEVEL} it opens the
 * engine's chooser (the MENU chunk of wflevels/clocks-menu.manifest): the player gets -1 and the host
 * leaves out the positional level. With the extra it starts that clock id through the shared
 * LevelLaunch, and an unknown id starts nothing. Neither path writes the saved Dream choice.
 * docs/plans/2026-11-21-tide-harbour-clock.md, decision D3.
 *
 * <p>The remote drives the chooser: up and down move, OK (D-pad centre, Enter, gamepad A) picks.
 * Back in a clock picked from the chooser returns to the chooser; Back on the chooser, or in a clock
 * started with the LEVEL extra, leaves the app (docs/plans/2026-10-01-level-menu-selector.md).
 * Buttons are released on key-up and on pause, so none sticks. The Dream never forwards keys.
 */
public final class ClocksActivity extends Activity {
    /** TankPlayer.start's "show the menu" index; dream_host.cc omits the positional level for it. */
    static final int SHOW_MENU = -1;

    // The engine's joystick bits, 1 << EJ_BUTTONB_* of wfsource/source/hal/sjoystic.h
    // (tests/test_dream_host_vram.py checks them against that header).
    static final int BUTTON_A = 1 << 0;       // EJ_BUTTONB_A
    static final int BUTTON_UP = 1 << 11;     // EJ_BUTTONB_UP
    static final int BUTTON_DOWN = 1 << 12;   // EJ_BUTTONB_DOWN

    private TankPlayer player;
    private boolean chooser;     // launched with no LEVEL extra: the remote drives the chooser
    private int held;            // the buttons held now

    /** The engine button for a remote key, or 0 for a key the chooser does not use. */
    static int buttonFor(int keyCode) {
        switch (keyCode) {
            case KeyEvent.KEYCODE_DPAD_UP: return BUTTON_UP;
            case KeyEvent.KEYCODE_DPAD_DOWN: return BUTTON_DOWN;
            case KeyEvent.KEYCODE_DPAD_CENTER:
            case KeyEvent.KEYCODE_ENTER:
            case KeyEvent.KEYCODE_NUMPAD_ENTER:
            case KeyEvent.KEYCODE_BUTTON_A: return BUTTON_A;
            default: return 0;
        }
    }

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
        chooser = requested == null;
        if (chooser) player.start(SHOW_MENU);
        else if (!LevelLaunch.startChosen(this, player, requested)) finish();
    }

    @Override
    public boolean dispatchKeyEvent(KeyEvent event) {
        int code = event.getKeyCode();
        if (code == KeyEvent.KEYCODE_BACK) {
            if (event.getAction() == KeyEvent.ACTION_UP && !(chooser && player.backToMenu())) finish();
            return true;
        }
        int button = chooser ? buttonFor(code) : 0;
        if (button == 0) return super.dispatchKeyEvent(event);
        if (event.getAction() == KeyEvent.ACTION_DOWN) held |= button;
        else if (event.getAction() == KeyEvent.ACTION_UP) held &= ~button;
        player.buttons(held);
        return true;
    }

    @Override
    protected void onPause() {
        held = 0;
        if (chooser) player.buttons(0);
        player.stop();
        super.onPause();
        finish();
    }
}
