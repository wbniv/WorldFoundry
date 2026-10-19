package org.worldfoundry.screensaver;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.os.Process;
import android.view.Gravity;
import android.view.Surface;
import android.view.SurfaceHolder;
import android.view.SurfaceView;
import android.view.View;
import android.widget.FrameLayout;
import android.widget.ImageView;
import java.io.File;

/** Surface and render thread shared by the Dream and the TV launcher preview. */
final class TankPlayer implements SurfaceHolder.Callback {
    static { System.loadLibrary("wf_dream"); }

    private final SurfaceView view;
    private final FrameLayout contentView;
    private Thread thread;
    private volatile boolean started;
    private int level;

    private static native void nativeRun(android.content.res.AssetManager assets, Surface surface,
                                         int level, String logPath);
    private static native void nativePrepare();
    private static native void nativeStop();

    TankPlayer(Context context) {
        view = new SurfaceView(context);
        view.getHolder().addCallback(this);
        contentView = new FrameLayout(context);
        contentView.addView(view, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));

        ImageView logo = new ImageView(context);
        Bitmap sourceLogo = BitmapFactory.decodeResource(context.getResources(), R.drawable.wf_logo);
        logo.setImageBitmap(Bitmap.createBitmap(sourceLogo, 4, 25, 78, 104));
        logo.setContentDescription(context.getString(R.string.wf_logo_description));
        int size = Math.round(72 * context.getResources().getDisplayMetrics().density);
        int margin = Math.round(24 * context.getResources().getDisplayMetrics().density);
        FrameLayout.LayoutParams logoLayout = new FrameLayout.LayoutParams(size, size * 4 / 3,
                Gravity.END | Gravity.BOTTOM);
        logoLayout.setMargins(margin, margin, margin, margin);
        contentView.addView(logo, logoLayout);
    }

    View view() { return contentView; }

    void start(int selectedLevel) {
        level = selectedLevel;
        started = true;
        startIfReady();
    }

    void stop() {
        started = false;
        nativeStop();
    }

    private void startIfReady() {
        if (!started || thread != null || !view.getHolder().getSurface().isValid()) return;
        final Surface surface = view.getHolder().getSurface();
        final int selected = level;
        File logDirectory = view.getContext().getExternalFilesDir(null);
        final String logPath = logDirectory == null ? null : new File(logDirectory, "wf.log").getAbsolutePath();
        nativePrepare();
        thread = new Thread(() -> {
            if (started) nativeRun(view.getContext().getAssets(), surface, selected, logPath);
            // The renderer has process-lifetime globals. Both callers run in a
            // dedicated process, so ending a stopped player resets them safely.
            if (!started) Process.killProcess(Process.myPid());
        }, "aquarium-player");
        thread.start();
    }

    @Override public void surfaceCreated(SurfaceHolder holder) { startIfReady(); }
    @Override public void surfaceChanged(SurfaceHolder holder, int format, int width, int height) { }
    @Override public void surfaceDestroyed(SurfaceHolder holder) {
        stop();
        if (thread != null) {
            try { thread.join(3000); }
            catch (InterruptedException error) { Thread.currentThread().interrupt(); }
        }
    }
}
