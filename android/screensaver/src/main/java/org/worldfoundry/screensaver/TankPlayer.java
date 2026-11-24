package org.worldfoundry.screensaver;

import android.content.Context;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.os.Process;
import android.view.MotionEvent;
import android.view.Surface;
import android.view.SurfaceHolder;
import android.view.SurfaceView;
import android.view.View;
import android.widget.FrameLayout;
import java.io.File;

/** Surface and render thread shared by the Dream, the preview and the TV launcher's tank menu. */
final class TankPlayer implements SurfaceHolder.Callback {
    static { System.loadLibrary("wf_dream"); }

    /**
     * The level index that runs the launcher's tank menu instead of one tank: the playable menu
     * bundle (assets/menu-cd.iff) with the engine's own level menu. dream_host.cc's kMenuLevel.
     * docs/plans/2026-11-21-one-aquarium-app.md.
     */
    static final int MENU = -1;

    private final SurfaceView view;
    private final FrameLayout contentView;
    private Thread thread;
    private volatile boolean started;
    private int level;
    private String configureLine;
    private String[] launchOverrideTriples = new String[0];
    private Runnable onEngineExit;
    private volatile boolean engineExited;

    private static native void nativeRun(android.content.res.AssetManager assets, Surface surface,
                                         int level, String logPath);
    private static native void nativeConfigure(String line);
    private static native void nativeLaunchOverride(String schema, String key, String value);
    private static native void nativePrepare();
    private static native void nativeStop();
    private static native boolean nativeKey(int keyCode, boolean down);
    private static native void nativeTouchConfigure(boolean enabled, float density);
    private static native boolean nativeStick(float x, float y, float hatX, float hatY);
    private static native boolean nativeTouch(int action, int actionIndex, int viewWidth, int viewHeight,
                                              int[] ids, float[] xs, float[] ys);
    private static native void nativeBack();

    TankPlayer(Context context) {
        view = new SurfaceView(context);
        view.getHolder().addCallback(this);
        // Enable phone touch for the chooser and settings; TVs use their remote.
        PackageManager features = context.getPackageManager();
        nativeTouchConfigure(features.hasSystemFeature(PackageManager.FEATURE_TOUCHSCREEN)
                && !features.hasSystemFeature(PackageManager.FEATURE_LEANBACK),
                context.getResources().getDisplayMetrics().density);
        view.setOnTouchListener((v, event) -> touch(v, event));
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

    /** The launcher's tank menu (Up and Down choose, Select starts, Back returns, Back leaves). */
    void startMenu() { start(MENU); }

    /**
     * Run on the main thread when the engine ends by itself while started: Back on the tank menu.
     * The caller finishes its activity; {@link #stop} then ends the process, as after any run.
     */
    void onEngineExit(Runnable action) { onEngineExit = action; }

    /** A remote key for the tank menu; true when the engine uses it. Inert outside the menu. */
    boolean key(int keyCode, boolean down) { return nativeKey(keyCode, down); }

    /** A hardware gamepad's left stick and hat; true when the host took them. */
    boolean stick(float x, float y, float hatX, float hatY) { return nativeStick(x, y, hatX, hatY); }

    /** One touch on the surface view, handed to the controller; true when it took the event. */
    private static boolean touch(View v, MotionEvent event) {
        int count = event.getPointerCount();
        int[] ids = new int[count];
        float[] xs = new float[count];
        float[] ys = new float[count];
        for (int i = 0; i < count; i++) {
            ids[i] = event.getPointerId(i);
            xs[i] = event.getX(i);
            ys[i] = event.getY(i);
        }
        return nativeTouch(event.getActionMasked(), event.getActionIndex(), v.getWidth(), v.getHeight(), ids, xs, ys);
    }

    /** Back released in the tank menu: closes a settings form, returns from a tank, or leaves. */
    void back() { nativeBack(); }

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

    void stop() {
        started = false;
        nativeStop();
        // The engine already ended (Back on the menu): its process-lifetime globals end with the process.
        if (engineExited) Process.killProcess(Process.myPid());
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
            // engineExited is written before started is read, and stop() writes started before
            // reading engineExited, so whichever runs second ends the process.
            engineExited = true;
            if (!started) Process.killProcess(Process.myPid());
            // Still started: the engine ended by itself (Back on the tank menu). Let the activity
            // finish; its onPause calls stop(), which then ends the process.
            final Runnable exit = onEngineExit;
            if (exit != null) view.post(exit);
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
