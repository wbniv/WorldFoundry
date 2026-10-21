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
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;

/**
 * Shell-only settings contract for the Planted Tank, same shape as TankSettingsProvider.
 * Methods: getCapabilities, getSettings, setSetting (arg {@code key:value}), resetSettings.
 * getCapabilities serves the OAD-generated asset {@value #CAPABILITIES_ASSET} with the saved values.
 */
public final class PlantedSettingsProvider extends ContentProvider {
    /** Generated from the settings OAD; see scripts/gen-planted-capabilities.py. */
    static final String CAPABILITIES_ASSET = "planted-settings.json";

    @Override
    public boolean onCreate() { return true; }

    @Override
    public Bundle call(String method, String arg, Bundle extras) {
        int caller = Binder.getCallingUid();
        if (caller != Process.SHELL_UID && caller != Process.myUid()) {
            throw new SecurityException("Planted Tank settings require the device shell");
        }
        Bundle result = new Bundle();
        if ("getCapabilities".equals(method)) {
            try {
                PlantedConfig config = PlantedSettings.load(getContext());
                JSONObject document = capabilities(config);
                result.putString("settings_b64", Base64.encodeToString(
                        document.toString().getBytes(StandardCharsets.UTF_8), Base64.NO_WRAP));
            } catch (JSONException error) {
                throw new IllegalStateException(error);
            }
        } else if ("getSettings".equals(method)) {
            putValues(result, PlantedSettings.load(getContext()));
        } else if ("setSetting".equals(method)) {
            int colon = arg == null ? -1 : arg.indexOf(':');
            if (colon < 0) {
                throw new IllegalArgumentException("setSetting needs key:value");
            }
            String key = arg.substring(0, colon);
            boolean saved = PlantedSettings.set(getContext(), key, arg.substring(colon + 1));
            result.putBoolean("saved", saved);
            result.putString("key", key);
            result.putString("value", PlantedSettings.load(getContext()).valueOf(key));
        } else if ("resetSettings".equals(method)) {
            result.putBoolean("saved", PlantedSettings.reset(getContext()));
            putValues(result, PlantedSettings.load(getContext()));
        } else {
            throw new IllegalArgumentException("Unknown settings method");
        }
        return result;
    }

    private static void putValues(Bundle bundle, PlantedConfig config) {
        for (String key : PlantedConfig.KEYS) bundle.putString(key, config.valueOf(key));
    }

    /**
     * The capabilities asset, generated at build time from the settings OAD by
     * scripts/gen-planted-capabilities.py, with each setting's {@code value} replaced by the
     * saved one. A numeric field shown as presets (Hold) also lists a custom current value.
     */
    private JSONObject capabilities(PlantedConfig config) throws JSONException {
        JSONObject document = new JSONObject(readAsset(CAPABILITIES_ASSET));
        JSONArray settings = document.getJSONArray("settings");
        for (int i = 0; i < settings.length(); i++) {
            JSONObject setting = settings.getJSONObject(i);
            String value = config.valueOf(setting.getString("id"));
            setting.put("value", value);
            if (PlantedConfig.HOLD.equals(setting.getString("id"))) {
                setting.put("options", withCustomSeconds(setting.getJSONArray("options"), value));
            }
        }
        return document;
    }

    private String readAsset(String name) {
        try (InputStream in = getContext().getAssets().open(name)) {
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            byte[] buffer = new byte[4096];
            for (int n; (n = in.read(buffer)) > 0; ) bytes.write(buffer, 0, n);
            return new String(bytes.toByteArray(), StandardCharsets.UTF_8);
        } catch (IOException missing) {
            throw new IllegalStateException("assets/" + name + " is missing: the APK must be built "
                    + "after scripts/gen-planted-capabilities.py (task build-planted-level)", missing);
        }
    }

    /** The presets in order, with {@code current} inserted before the first larger one. */
    private static JSONArray withCustomSeconds(JSONArray presets, String current)
            throws JSONException {
        long seconds = Long.parseLong(current);
        JSONArray options = new JSONArray();
        boolean placed = false;
        for (int i = 0; i < presets.length(); i++) {
            if (presets.getJSONObject(i).getString("id").equals(current)) return presets;
        }
        for (int i = 0; i < presets.length(); i++) {
            JSONObject preset = presets.getJSONObject(i);
            if (!placed && seconds < Long.parseLong(preset.getString("id"))) {
                options.put(new JSONObject().put("id", current).put("label", secondsLabel(seconds)));
                placed = true;
            }
            options.put(preset);
        }
        if (!placed) {
            options.put(new JSONObject().put("id", current).put("label", secondsLabel(seconds)));
        }
        return options;
    }

    /** Same labels as the generator's presets: whole minutes as "N min", else "N s". */
    private static String secondsLabel(long seconds) {
        return seconds >= 60 && seconds % 60 == 0 ? (seconds / 60) + " min" : seconds + " s";
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
