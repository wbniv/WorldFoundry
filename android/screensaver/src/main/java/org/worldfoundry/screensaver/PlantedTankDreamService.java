package org.worldfoundry.screensaver;

import android.service.dreams.DreamService;

/** A separate Dream that runs the Planted Tank level with the saved settings. */
public final class PlantedTankDreamService extends DreamService {
    private TankPlayer player;

    @Override
    public void onAttachedToWindow() {
        super.onAttachedToWindow();
        setInteractive(false);
        setFullscreen(true);
        player = new TankPlayer(this);
        setContentView(player.view());
    }

    @Override
    public void onDreamingStarted() {
        super.onDreamingStarted();
        // A Dream has no intent extras, so only the saved settings apply. They are read
        // at each Dream start, so a changed setting takes effect the next time.
        player.configure(PlantedSettings.load(this).toLine());
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
