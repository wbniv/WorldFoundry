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
 * Shell-only settings contract for the Planted Tank, same shape as TankSettingsProvider.
 * Methods: getCapabilities, getSettings, setSetting (arg {@code key:value}), resetSettings.
 */
public final class PlantedSettingsProvider extends ContentProvider {
    private static final long[] HOLD_PRESETS = { 60, 120, 300, 600 };
    private static final String[] SPEED_IDS = { "0.25", "0.5", "1", "2", "4", "8" };

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
                JSONObject document = new JSONObject().put("schema", 1).put("settings",
                        new JSONArray()
                                .put(waterSetting(config))
                                .put(speedSetting(config))
                                .put(holdSetting(config)));
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

    private static JSONObject choice(String id, String label, String value, JSONArray options)
            throws JSONException {
        return new JSONObject().put("id", id).put("type", "choice").put("label", label)
                .put("value", value).put("options", options);
    }

    private static JSONObject option(String id, String label) throws JSONException {
        return new JSONObject().put("id", id).put("label", label);
    }

    private static JSONObject waterSetting(PlantedConfig config) throws JSONException {
        JSONArray options = new JSONArray()
                .put(option(PlantedConfig.RANDOM, "Random"))
                .put(option(PlantedConfig.FRESHWATER, "Freshwater"))
                .put(option(PlantedConfig.SALTWATER, "Saltwater"));
        return choice(PlantedConfig.WATER, "Water", config.water(), options);
    }

    private static JSONObject speedSetting(PlantedConfig config) throws JSONException {
        JSONArray options = new JSONArray();
        for (String id : SPEED_IDS) options.put(option(id, id + "x"));
        return choice(PlantedConfig.SPEED, "Speed", config.valueOf(PlantedConfig.SPEED), options);
    }

    /** The four presets, plus the current value when it is a custom number of seconds. */
    private static JSONObject holdSetting(PlantedConfig config) throws JSONException {
        long current = config.hold();
        JSONArray options = new JSONArray();
        boolean placed = false;
        for (long preset : HOLD_PRESETS) {
            if (!placed && current < preset && !isPreset(current)) {
                options.put(option(Long.toString(current), holdLabel(current)));
                placed = true;
            }
            options.put(option(Long.toString(preset), holdLabel(preset)));
        }
        if (!placed && !isPreset(current)) {
            options.put(option(Long.toString(current), holdLabel(current)));
        }
        return choice(PlantedConfig.HOLD, "Hold", Long.toString(current), options);
    }

    private static boolean isPreset(long seconds) {
        for (long preset : HOLD_PRESETS) {
            if (preset == seconds) return true;
        }
        return false;
    }

    private static String holdLabel(long seconds) {
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
