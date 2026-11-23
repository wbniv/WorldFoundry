package org.worldfoundry.screensaver;

import android.service.dreams.DreamService;

/**
 * The WF Clocks Dream (clocks flavor): plays the saved clock choice (default Random, resolved once
 * per run by LevelLaunch), never the chooser, because a screensaver must never wait for a person.
 * docs/plans/2026-11-21-tide-harbour-clock.md, decision D3.
 */
public final class ClocksDreamService extends DreamService {
    private TankPlayer player;

    @Override
    public void onAttachedToWindow() {
        super.onAttachedToWindow();
        setInteractive(false);
        setFullscreen(true);
        DreamOrientation.apply(this, OrientationSettings.load(this));
        player = new TankPlayer(this);
        setContentView(player.view());
    }

    @Override
    public void onDreamingStarted() {
        super.onDreamingStarted();
        LevelLaunch.startChosen(this, player, null);
    }

    @Override
    public void onDreamingStopped() {
        if (player != null) player.stop();
        super.onDreamingStopped();
    }

    @Override
    public void onDetachedFromWindow() {
        if (player != null) player.stop();
        player = null;
        super.onDetachedFromWindow();
    }
}
