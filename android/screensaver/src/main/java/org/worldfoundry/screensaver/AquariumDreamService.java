package org.worldfoundry.screensaver;

import android.service.dreams.DreamService;

public final class AquariumDreamService extends DreamService {
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
        player.start(TankChoice.indexOf(TankChoice.chooseForDream(this)));
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
