package org.worldfoundry.screensaver;

import android.content.Context;
import android.graphics.Color;
import android.os.Process;
import android.view.Surface;
import android.view.SurfaceHolder;
import android.view.SurfaceView;
import android.view.View;
import android.widget.FrameLayout;
import java.io.File;

/** Surface and render thread shared by the Dream and the TV launcher preview. */
final class TankPlayer implements SurfaceHolder.Callback {
    static { System.loadLibrary("wf_dream"); }

    private final SurfaceView view;
    private final FrameLayout contentView;
    private Thread thread;
    private volatile boolean started;
    private int level;
    private String configureLine;
    private String[] launchOverrideTriples = new String[0];

    private static native void nativeRun(android.content.res.AssetManager assets, Surface surface,
                                         int level, String logPath);
    private static native void nativeConfigure(String line);
    private static native void nativeLaunchOverride(String schema, String key, String value);
    private static native void nativePrepare();
    private static native void nativeStop();
    private static native void nativeButtons(int mask);
    private static native boolean nativeBackToMenu();

    TankPlayer(Context context) {
        view = new SurfaceView(context);
        view.getHolder().addCallback(this);
        contentView = new FrameLayout(context) {
            private int surfaceHeight;

            @Override protected void onMeasure(int widthSpec, int heightSpec) {
                super.onMeasure(widthSpec, heightSpec);
                int width = MeasureSpec.getSize(widthSpec);
                int height = MeasureSpec.getSize(heightSpec);
                // The tank is composed for a landscape display. Keep its full width visible
                // on a portrait phone instead of applying a narrow portrait projection.
                surfaceHeight = width < height ? Math.min(height, width * 9 / 16) : height;
                view.measure(MeasureSpec.makeMeasureSpec(width, MeasureSpec.EXACTLY),
                        MeasureSpec.makeMeasureSpec(surfaceHeight, MeasureSpec.EXACTLY));
            }

            @Override protected void onLayout(boolean changed, int left, int top, int right, int bottom) {
                super.onLayout(changed, left, top, right, bottom);
                int width = right - left;
                int height = bottom - top;
                int surfaceTop = (height - surfaceHeight) / 2;
                view.layout(0, surfaceTop, width, surfaceTop + surfaceHeight);
            }
        };
        contentView.setBackgroundColor(Color.BLACK);
        contentView.addView(view, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));

    }

    View view() { return contentView; }

    void start(int selectedLevel) {
        level = selectedLevel;
        started = true;
        startIfReady();
    }

    /** Hands the engine a launch-parameter line on the next start; unset leaves other flavors untouched. */
    void configure(String line) { configureLine = line; }

    /** Engine launch overrides (schema, OAD field key, value) to set on the player thread before the level loads. */
    void launchOverrides(String schema, java.util.Map<String, String> values) {
        String[] triples = new String[values.size() * 3];
        int at = 0;
        for (java.util.Map.Entry<String, String> entry : values.entrySet()) {
            triples[at++] = schema;
            triples[at++] = entry.getKey();
            triples[at++] = entry.getValue();
        }
        launchOverrideTriples = triples;
    }

    /**
     * The remote buttons held now, as the engine's EJ_BUTTONF_* bits (see ClocksActivity); 0 releases
     * them. Only ClocksActivity's chooser calls it: Dreams and the other flavors never send input.
     */
    void buttons(int mask) { nativeButtons(mask); }

    /** Back in a clock picked from the chooser: return to the chooser. False: leave the app instead. */
    boolean backToMenu() { return nativeBackToMenu(); }

    void stop() {
        started = false;
        nativeStop();
    }

    private void startIfReady() {
        if (!started || thread != null || !view.getHolder().getSurface().isValid()) return;
        final Surface surface = view.getHolder().getSurface();
        final int selected = level;
        final String configure = configureLine;
        final String[] overrides = launchOverrideTriples;
        File logDirectory = view.getContext().getExternalFilesDir(null);
        final String logPath = logDirectory == null ? null : new File(logDirectory, "wf.log").getAbsolutePath();
        nativePrepare();
        thread = new Thread(() -> {
            if (started && configure != null) nativeConfigure(configure);
            for (int i = 0; started && i + 2 < overrides.length; i += 3) {
                nativeLaunchOverride(overrides[i], overrides[i + 1], overrides[i + 2]);
            }
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
