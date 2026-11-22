package org.worldfoundry.screensaver;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.net.Uri;
import android.os.Binder;
import android.os.Bundle;
import android.os.Process;
import android.util.Base64;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;
import java.nio.charset.StandardCharsets;

/**
 * Shell-only settings contract for WF Clocks, the shape of TankSettingsProvider: the saved Dream
 * clock ({@code clock:<id>} or {@code clock:random}, from the package's LevelCatalog) beside the
 * orientation. Declared only in the clocks flavor's manifest. An unknown id saves nothing.
 * docs/plans/2026-11-21-tide-harbour-clock.md, "The bundle and the chooser".
 */
public final class ClocksSettingsProvider extends ContentProvider {
    static final String CLOCK = "clock";

    @Override
    public boolean onCreate() { return true; }

    @Override
    public Bundle call(String method, String arg, Bundle extras) {
        int caller = Binder.getCallingUid();
        if (caller != Process.SHELL_UID && caller != Process.myUid()) {
            throw new SecurityException("WF Clocks settings require the device shell");
        }
        Bundle result = new Bundle();
        String clockPrefix = CLOCK + ":";
        String orientationPrefix = TankSettingsProvider.ORIENTATION + ":";
        if ("getCapabilities".equals(method)) {
            try {
                JSONArray options = new JSONArray();
                options.put(new JSONObject().put("id", TankChoice.RANDOM).put("label", "Random"));
                LevelCatalog clocks = TankChoice.catalog(getContext());
                for (String id : clocks.ids()) {
                    options.put(new JSONObject().put("id", id).put("label", clocks.label(id)));
                }
                JSONObject clock = new JSONObject().put("id", CLOCK).put("type", "choice")
                        .put("label", "Clock").put("value", TankChoice.get(getContext())).put("options", options);
                JSONArray settings = new JSONArray().put(clock)
                        .put(TankSettingsProvider.orientationSetting(OrientationSettings.load(getContext())));
                JSONObject document = new JSONObject().put("schema", 1).put("settings", settings);
                result.putString("settings_b64", Base64.encodeToString(
                        document.toString().getBytes(StandardCharsets.UTF_8), Base64.NO_WRAP));
            } catch (JSONException error) {
                throw new IllegalStateException(error);
            }
        } else if ("getClock".equals(method)) {
            result.putString(CLOCK, TankChoice.get(getContext()));
        } else if ("setSetting".equals(method) && arg != null && arg.startsWith(orientationPrefix)) {
            TankSettingsProvider.putOrientation(getContext(), result, arg.substring(orientationPrefix.length()));
        } else if ("setSetting".equals(method) && arg != null && arg.startsWith(clockPrefix)) {
            String id = arg.substring(clockPrefix.length());
            if (!TankChoice.valid(getContext(), id)) throw new IllegalArgumentException("Unknown clock: " + id);
            result.putBoolean("saved", TankChoice.set(getContext(), id));
            result.putString(CLOCK, TankChoice.get(getContext()));
        } else if ("setSetting".equals(method)) {
            throw new IllegalArgumentException("Unknown setting");
        } else {
            throw new IllegalArgumentException("Unknown settings method");
        }
        return result;
    }

    @Override public Cursor query(Uri uri, String[] projection, String selection,
                                  String[] selectionArgs, String sortOrder) {
        throw new UnsupportedOperationException();
    }
    @Override public String getType(Uri uri) { throw new UnsupportedOperationException(); }
    @Override public Uri insert(Uri uri, ContentValues values) { throw new UnsupportedOperationException(); }
    @Override public int delete(Uri uri, String selection, String[] selectionArgs) {
        throw new UnsupportedOperationException();
    }
    @Override public int update(Uri uri, ContentValues values, String selection, String[] selectionArgs) {
        throw new UnsupportedOperationException();
    }
}
