package org.worldfoundry.screensaver;

import android.content.Context;
import android.os.Bundle;

/**
 * The saved level choice as every pack's settings provider serves it, and the one place that writes
 * it ({@link TankChoice#set}). Each provider keeps its own coordinator-facing setting id (the
 * Aquarium's {@code tank}, WF Clocks' {@code clock}) and also answers the shared
 * {@link ChooserModel#SETTING} id, so the one chooser activity serves every pack without knowing
 * which it is. {@code getCapabilities} is unchanged; the shared id is accepted, never advertised.
 * docs/plans/2026-11-27-screensaver-chooser.md, "Critical files".
 *
 * <p>Only settings providers call this (LaunchModeTest's source guard); the chooser reaches it
 * through its pack's provider, and the Dream and the preview only read the choice.
 */
final class LevelChoiceCalls {
    private LevelChoiceCalls() { }

    /**
     * Answers {@code getLevel} and {@code setSetting level:<id>}; returns false for any other call,
     * which the provider then handles itself. {@code getLevel} returns {@code level} (the choice in
     * effect: a roster id or {@code random}) and, when something is saved, {@code stored} (the raw
     * value, which can be an id the roster no longer holds).
     */
    static boolean handle(Context context, String method, String arg, Bundle result) {
        if (ChooserModel.GET_METHOD.equals(method)) {
            result.putString(ChooserModel.SETTING, TankChoice.get(context));
            String stored = TankChoice.stored(context);
            if (stored != null) result.putString(ChooserModel.STORED, stored);
            return true;
        }
        String prefix = ChooserModel.SETTING + ":";
        if (ChooserModel.SET_METHOD.equals(method) && arg != null && arg.startsWith(prefix)) {
            String id = arg.substring(prefix.length());
            save(context, id, result, ChooserModel.SETTING, "Unknown level: " + id);
            return true;
        }
        return false;
    }

    /**
     * Validate, save and echo one level choice ({@code random} or a roster id) under {@code key}.
     * An id the roster does not hold throws IllegalArgumentException with {@code refusal} and saves nothing.
     */
    static void save(Context context, String id, Bundle result, String key, String refusal) {
        if (!TankChoice.valid(context, id)) throw new IllegalArgumentException(refusal);
        result.putBoolean("saved", TankChoice.set(context, id));
        result.putString(key, TankChoice.get(context));
    }
}
