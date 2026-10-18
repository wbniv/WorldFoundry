package org.worldfoundry.screensaver;

import android.content.Context;
import android.os.Process;
import android.view.Surface;
import android.view.SurfaceHolder;
import android.view.SurfaceView;
import java.io.File;

/** Surface and render thread shared by the Dream and the TV launcher preview. */
final class TankPlayer implements SurfaceHolder.Callback {
    static { System.loadLibrary("wf_dream"); }

    private final SurfaceView view;
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
    }

    SurfaceView view() { return view; }

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
