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
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.Iterator;

/**
 * Shell-only settings contract for the Planted Tank, same shape as TankSettingsProvider.
 * Methods: getCapabilities, getSettings, setSetting (arg {@code key:value}), resetSettings.
 * getCapabilities serves the owner-aware RP01/OAD-generated asset with saved values, plus the
 * app-level orientation, which is not a level property: it is appended to the first owner as
 * field {@code orientation} (wire ID {@code <owner>.orientation}) and never enters the catalog.
 */
public final class PlantedSettingsProvider extends ContentProvider {
    /** Generated from the level's OAD-derived RP01 catalog. */
    static final String CAPABILITIES_ASSET = "planted-settings.json";
    /** The adapter-added field's OAD-style name; no OAD field carries it. */
    static final String ORIENTATION_KEY = "Orientation";

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
                JSONObject document = capabilities(getContext(), config);
                result.putString("settings_b64", Base64.encodeToString(
                        document.toString().getBytes(StandardCharsets.UTF_8), Base64.NO_WRAP));
            } catch (JSONException error) {
                throw new IllegalStateException(error);
            }
        } else if ("getSettings".equals(method)) {
            putValues(result, PlantedSettings.load(getContext()));
            result.putString(TankSettingsProvider.ORIENTATION, OrientationSettings.load(getContext()));
        } else if ("setSetting".equals(method)) {
            int colon = arg == null ? -1 : arg.indexOf(':');
            if (colon < 0) {
                throw new IllegalArgumentException("setSetting needs owner.field:value");
            }
            try {
                String key = arg.substring(0, colon);
                JSONObject field = findField(capabilities(getContext(), PlantedSettings.load(getContext())), key);
                if (field.getBoolean("readonly")) throw new IllegalArgumentException("Read-only setting");
                String fieldName = field.getString("key");
                String requested = arg.substring(colon + 1);
                validateChoice(field, requested);
                if (ORIENTATION_KEY.equals(fieldName)) {
                    result.putBoolean("saved", OrientationSettings.set(getContext(), requested));
                    result.putString("key", key);
                    result.putString("value", OrientationSettings.load(getContext()));
                    return result;
                }
                String appKey = appKey(fieldName);
                boolean saved = "Seed".equals(fieldName) && "random".equals(requested)
                        ? PlantedSettings.clear(getContext(), appKey)
                        : PlantedSettings.set(getContext(), appKey, appValue(fieldName, requested));
                result.putBoolean("saved", saved);
                result.putString("key", key);
                result.putString("value", currentValue(fieldName, PlantedSettings.load(getContext())));
            } catch (JSONException error) {
                throw new IllegalStateException(error);
            }
        } else if ("resetSettings".equals(method)) {
            boolean saved = PlantedSettings.reset(getContext());
            result.putBoolean("saved", OrientationSettings.clear(getContext()) && saved);
            putValues(result, PlantedSettings.load(getContext()));
            result.putString(TankSettingsProvider.ORIENTATION, OrientationSettings.load(getContext()));
        } else {
            throw new IllegalArgumentException("Unknown settings method");
        }
        return result;
    }

    private static void putValues(Bundle bundle, PlantedConfig config) {
        for (String key : PlantedConfig.KEYS) bundle.putString(key, config.valueOf(key));
    }

    /** Overlay current app values onto every field of the generated Settings owner. */
    static JSONObject capabilities(Context context, PlantedConfig config) throws JSONException {
        JSONObject document = new JSONObject(readAsset(context, CAPABILITIES_ASSET));
        JSONArray objects = document.getJSONArray("objects");
        for (int owner = 0; owner < objects.length(); owner++) {
            JSONArray fields = objects.getJSONObject(owner).getJSONArray("settings");
            for (int i = 0; i < fields.length(); i++) {
                JSONObject field = fields.getJSONObject(i);
                String key = field.getString("key");
                field.put("value", currentValue(key, config));
                if ("Seed".equals(key)) {
                    field.put("unset_value", "random");
                } else if ("Water type".equals(key)) {
                    JSONArray options = field.getJSONArray("options");
                    JSONArray withRandom = new JSONArray();
                    withRandom.put(new JSONObject().put("id", "random").put("label", "Random"));
                    for (int n = 0; n < options.length(); n++) withRandom.put(options.getJSONObject(n));
                    field.put("options", withRandom);
                } else if ("Growth speed".equals(key)) {
                    JSONArray options = field.getJSONArray("options");
                    JSONArray active = new JSONArray();
                    for (int n = 0; n < options.length(); n++) {
                        JSONObject option = options.getJSONObject(n);
                        if (!"0".equals(option.getString("id"))) active.put(option);
                    }
                    field.put("options", active);
                } else if ("Random seed on entry".equals(key)) {
                    field.put("readonly", true); // Derived from whether Seed is set.
                    field.put("help", "Choose a Seed, or set Seed to random.");
                }
            }
        }
        // App-level, like the random water policy above: added here, never in the OAD catalog.
        JSONObject orientation = TankSettingsProvider.orientationSetting(OrientationSettings.load(context))
                .put("key", ORIENTATION_KEY).put("show", 5).put("readonly", false)
                .put("group", "Screensaver");
        objects.getJSONObject(0).getJSONArray("settings").put(orientation);
        return document;
    }

    private static JSONObject findField(JSONObject document, String wireId) throws JSONException {
        JSONArray objects = document.getJSONArray("objects");
        for (int owner = 0; owner < objects.length(); owner++) {
            JSONObject object = objects.getJSONObject(owner);
            JSONArray fields = object.getJSONArray("settings");
            for (int i = 0; i < fields.length(); i++) {
                JSONObject field = fields.getJSONObject(i);
                if (wireId.equals(object.getInt("owner") + "." + field.getString("id"))) return field;
            }
        }
        throw new IllegalArgumentException("Setting is not offered by this APK");
    }

    private static void validateChoice(JSONObject field, String requested) throws JSONException {
        if (!"choice".equals(field.getString("type"))) return;
        JSONArray options = field.getJSONArray("options");
        for (int i = 0; i < options.length(); i++) {
            if (requested.equals(options.getJSONObject(i).getString("id"))) return;
        }
        throw new IllegalArgumentException("Choice is not offered");
    }

    /** Apply owner.field overrides to one launch; the settings provider is never written. */
    static PlantedConfig overlay(Context context, PlantedConfig base, JSONObject updates)
            throws JSONException {
        if (updates.length() > 16) throw new IllegalArgumentException("Too many launch overrides");
        PlantedConfig config = base;
        Iterator<String> keys = updates.keys();
        while (keys.hasNext()) {
            String wireId = keys.next();
            JSONObject field = findField(capabilities(context, config), wireId);
            if (field.getBoolean("readonly")) throw new IllegalArgumentException("Read-only setting");
            String requested = updates.getString(wireId);
            validateChoice(field, requested);
            String key = field.getString("key");
            if (ORIENTATION_KEY.equals(key)) continue; // Not a level value; see launchOrientation.
            config = "Seed".equals(key) && "random".equals(requested)
                    ? config.withoutSeed() : config.with(appKey(key), appValue(key, requested));
        }
        return config;
    }

    /** A validated one-run orientation from the launch overrides, or null when none is given. */
    static String launchOrientation(Context context, PlantedConfig base, JSONObject updates)
            throws JSONException {
        Iterator<String> keys = updates.keys();
        while (keys.hasNext()) {
            String wireId = keys.next();
            JSONObject field = findField(capabilities(context, base), wireId);
            if (!ORIENTATION_KEY.equals(field.getString("key"))) continue;
            String requested = updates.getString(wireId);
            validateChoice(field, requested);
            return OrientationChoice.parse(requested);
        }
        return null;
    }

    private static String appKey(String field) {
        switch (field) {
            case "Seed": return PlantedConfig.SEED;
            case "Water type": return PlantedConfig.WATER;
            case "Growth speed": return PlantedConfig.SPEED;
            case "Initial age": return PlantedConfig.AGE;
            case "Textures": return PlantedConfig.TEXTURES;
            case "Sway": return PlantedConfig.SWAY;
            case "Hold seconds": return PlantedConfig.HOLD;
            default: throw new IllegalStateException("No app adapter for OAD field " + field);
        }
    }

    private static String currentValue(String field, PlantedConfig config) {
        switch (field) {
            case "Seed": return config.valueOf(PlantedConfig.SEED);
            case "Water type": return PlantedConfig.RANDOM.equals(config.water()) ? "random"
                    : PlantedConfig.FRESHWATER.equals(config.water()) ? "0" : "1";
            case "Growth speed": return Integer.toString(config.speedIndex());
            case "Initial age": return config.valueOf(PlantedConfig.AGE);
            case "Textures": return config.valueOf(PlantedConfig.TEXTURES);
            case "Sway": return config.valueOf(PlantedConfig.SWAY);
            case "Random seed on entry": return Boolean.toString(!config.hasSeed());
            case "Hold seconds": return config.valueOf(PlantedConfig.HOLD);
            default: throw new IllegalStateException("No app adapter for OAD field " + field);
        }
    }

    private static String appValue(String field, String requested) {
        if ("Water type".equals(field)) {
            if ("0".equals(requested)) return PlantedConfig.FRESHWATER;
            if ("1".equals(requested)) return PlantedConfig.SALTWATER;
            if ("random".equals(requested)) return PlantedConfig.RANDOM;
            throw new IllegalArgumentException("Unknown water choice");
        }
        if ("Growth speed".equals(field)) {
            String[] rates = PlantedConfig.speedValues();
            int index;
            try {
                index = Integer.parseInt(requested);
            } catch (NumberFormatException invalid) {
                throw new IllegalArgumentException("Unknown growth speed", invalid);
            }
            if (index < 1 || index > rates.length) throw new IllegalArgumentException("Unknown growth speed");
            return rates[index - 1];
        }
        return requested;
    }

    private static String readAsset(Context context, String name) {
        try (InputStream in = context.getAssets().open(name)) {
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            byte[] buffer = new byte[4096];
            for (int n; (n = in.read(buffer)) > 0; ) bytes.write(buffer, 0, n);
            return new String(bytes.toByteArray(), StandardCharsets.UTF_8);
        } catch (IOException missing) {
            throw new IllegalStateException("assets/" + name + " is missing: the APK must be built "
                    + "after scripts/gen-settings-capabilities.py (task build-planted-level)", missing);
        }
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
