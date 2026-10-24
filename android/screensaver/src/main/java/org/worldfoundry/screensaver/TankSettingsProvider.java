package org.worldfoundry.screensaver;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.content.Context;
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

/** Small shell-only contract for the coordinator's owned settings workflow. */
public final class TankSettingsProvider extends ContentProvider {
    private static final String AUTHORITY = "org.worldfoundry.screensaver.settings";
    static final String ORIENTATION = "orientation";

    @Override
    public boolean onCreate() { return true; }

    @Override
    public Bundle call(String method, String arg, Bundle extras) {
        int caller = Binder.getCallingUid();
        if (caller != Process.SHELL_UID && caller != Process.myUid()) {
            throw new SecurityException("Screensaver settings require the device shell");
        }
        Bundle result = new Bundle();
        if ("getCapabilities".equals(method)) {
            JSONArray options = new JSONArray();
            try {
                options.put(new JSONObject().put("id", TankChoice.RANDOM).put("label", "Random"));
                for (int i = 0; i < TankChoice.IDS.length; i++) {
                    options.put(new JSONObject().put("id", TankChoice.IDS[i])
                            .put("label", TankChoice.LABELS[i]));
                }
                JSONObject setting = new JSONObject().put("id", "tank")
                        .put("type", "choice").put("label", "Tank")
                        .put("value", TankChoice.get(getContext())).put("options", options);
                JSONObject document = new JSONObject().put("schema", 1)
                        .put("settings", new JSONArray().put(setting)
                                .put(orientationSetting(OrientationSettings.load(getContext()))));
                result.putString("settings_b64", Base64.encodeToString(
                        document.toString().getBytes(StandardCharsets.UTF_8), Base64.NO_WRAP));
            } catch (JSONException error) {
                throw new IllegalStateException(error);
            }
        } else if ("getTank".equals(method)) {
            result.putString("tank", TankChoice.get(getContext()));
        } else if ("setSetting".equals(method) && arg != null && arg.startsWith(ORIENTATION + ":")) {
            putOrientation(getContext(), result, arg.substring(ORIENTATION.length() + 1));
        } else if ("setSetting".equals(method)) {
            if (arg == null || !arg.startsWith("tank:") || !TankChoice.valid(arg.substring(5))) {
                throw new IllegalArgumentException("Unknown tank");
            }
            result.putBoolean("saved", TankChoice.set(getContext(), arg.substring(5)));
            result.putString("tank", TankChoice.get(getContext()));
        } else {
            throw new IllegalArgumentException("Unknown settings method");
        }
        return result;
    }

    /** The app-level orientation choice, in schema 1 form; shared with SeahorseSettingsProvider. */
    static JSONObject orientationSetting(String value) throws JSONException {
        JSONArray options = new JSONArray();
        for (int i = 0; i < OrientationChoice.IDS.length; i++) {
            options.put(new JSONObject().put("id", OrientationChoice.IDS[i])
                    .put("label", OrientationChoice.LABELS[i]));
        }
        return new JSONObject().put("id", ORIENTATION).put("type", "choice")
                .put("label", "Orientation").put("value", value).put("options", options);
    }

    /** Validate, save and echo one orientation; IllegalArgumentException saves nothing. */
    static void putOrientation(Context context, Bundle result, String requested) {
        result.putBoolean("saved", OrientationSettings.set(context, requested));
        result.putString(ORIENTATION, OrientationSettings.load(context));
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
