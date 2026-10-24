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
 * Shell-only settings contract for the Seahorse Grid, same shape as TankSettingsProvider.
 * Its one setting is the orientation; declared only in the seahorse flavor's manifest.
 */
public final class SeahorseSettingsProvider extends ContentProvider {
    private static final String AUTHORITY = "org.worldfoundry.seahorsegrid.settings";

    @Override
    public boolean onCreate() { return true; }

    @Override
    public Bundle call(String method, String arg, Bundle extras) {
        int caller = Binder.getCallingUid();
        if (caller != Process.SHELL_UID && caller != Process.myUid()) {
            throw new SecurityException("Seahorse Grid settings require the device shell");
        }
        Bundle result = new Bundle();
        String prefix = TankSettingsProvider.ORIENTATION + ":";
        if ("getCapabilities".equals(method)) {
            try {
                JSONObject document = new JSONObject().put("schema", 1)
                        .put("settings", new JSONArray().put(TankSettingsProvider.orientationSetting(
                                OrientationSettings.load(getContext()))));
                result.putString("settings_b64", Base64.encodeToString(
                        document.toString().getBytes(StandardCharsets.UTF_8), Base64.NO_WRAP));
            } catch (JSONException error) {
                throw new IllegalStateException(error);
            }
        } else if ("setSetting".equals(method)) {
            if (arg == null || !arg.startsWith(prefix)) {
                throw new IllegalArgumentException("Unknown setting");
            }
            TankSettingsProvider.putOrientation(getContext(), result, arg.substring(prefix.length()));
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
