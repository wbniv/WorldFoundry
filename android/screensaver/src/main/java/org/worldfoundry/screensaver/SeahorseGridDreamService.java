package org.worldfoundry.screensaver;

import android.service.dreams.DreamService;

/** A separate Dream that runs the seahorse grid World Foundry level. */
public final class SeahorseGridDreamService extends DreamService {
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
        player.start(0);
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
