package org.worldfoundry.screensaver;

import android.app.Activity;
import android.service.dreams.DreamService;
import android.view.Window;
import android.view.WindowManager;

/**
 * Requests the saved orientation for a Dream or a launcher activity. See
 * docs/plans/2026-10-24-screensaver-landscape-orientation.md.
 */
final class DreamOrientation {
    private DreamOrientation() { }

    /**
     * Call from onAttachedToWindow, before setContentView. From Android 11 the Dream's window
     * belongs to the system's DreamActivity, and WindowManager rotates from that activity's
     * requested orientation; the window attribute is ignored there. Android 10 and earlier
     * give the service its own TYPE_DREAM window with no activity, whose screenOrientation
     * attribute is read instead (checked in the source only, not run on a device).
     */
    static void apply(DreamService dream, String id) {
        int requested = OrientationChoice.requestedOrientation(id);
        Window window = dream.getWindow();
        if (window.getContext() instanceof Activity) {
            ((Activity) window.getContext()).setRequestedOrientation(requested);
        } else {
            WindowManager.LayoutParams attributes = window.getAttributes();
            attributes.screenOrientation = requested;
            window.setAttributes(attributes);
        }
    }

    /** Call from onCreate, before setContentView. */
    static void apply(Activity activity, String id) {
        activity.setRequestedOrientation(OrientationChoice.requestedOrientation(id));
    }
}
