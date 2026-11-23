package org.worldfoundry.screensaver;

import android.content.Context;
import android.content.SharedPreferences;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * The Dream's saved choices for one level's settings object, driven by the capabilities asset
 * that scripts/gen-settings-capabilities.py generates from the object's OAD. Not specific to any
 * level: Sea Stars is the first user. The phone and coordinator see the fields through
 * {@link TankSettingsProvider}; at launch {@link #overrides()} becomes the engine's launch
 * overrides (schema + OAD field key + value), which it applies when the level loads.
 *
 * <p>Only what the user changed is saved and sent, so every other value is the level's own
 * default from its OAD and cannot drift from it.
 */
final class LevelSettings {
    static final String SEA_STARS_ASSET = "sea-stars-settings.json";
    static final String SEA_STARS_PREFS = "sea-stars";
    static final String SEA_STARS_PREFIX = "sea-stars.";
    /** The tank id in {@link TankChoice} whose level carries this settings object. */
    static final String SEA_STARS_TANK = "aquarium_sea_stars";
    private static final String SEA_STARS_TITLE = "Sea Stars";

    private final String schema;
    private final String prefix;
    private final String title;
    private final List<LevelSettingField> fields;
    private final SharedPreferences prefs;

    private LevelSettings(String schema, String prefix, String title, List<LevelSettingField> fields,
                          SharedPreferences prefs) {
        this.schema = schema;
        this.prefix = prefix;
        this.title = title;
        this.fields = Collections.unmodifiableList(fields);
        this.prefs = prefs;
    }

    /** Sea Stars' settings; empty (no fields) in a flavor whose APK carries no asset. */
    static LevelSettings seaStars(Context context) {
        SharedPreferences prefs = context.getSharedPreferences(SEA_STARS_PREFS, Context.MODE_PRIVATE);
        try {
            JSONObject owner = new JSONObject(readAsset(context, SEA_STARS_ASSET))
                    .getJSONArray("objects").getJSONObject(0);
            return new LevelSettings(owner.getString("type"), SEA_STARS_PREFIX, SEA_STARS_TITLE,
                    parse(owner.getJSONArray("settings")), prefs);
        } catch (IOException | JSONException absent) {
            return new LevelSettings("", SEA_STARS_PREFIX, SEA_STARS_TITLE,
                    new ArrayList<LevelSettingField>(), prefs);
        }
    }

    private static List<LevelSettingField> parse(JSONArray settings) throws JSONException {
        List<LevelSettingField> out = new ArrayList<>();
        for (int i = 0; i < settings.length(); i++) {
            JSONObject s = settings.getJSONObject(i);
            if (s.getBoolean("readonly")) continue;      // read-only fields are never offered
            List<String> ids = new ArrayList<>();
            List<String> labels = new ArrayList<>();
            JSONArray options = s.optJSONArray("options");
            for (int n = 0; options != null && n < options.length(); n++) {
                ids.add(options.getJSONObject(n).getString("id"));
                labels.add(options.getJSONObject(n).getString("label"));
            }
            out.add(new LevelSettingField(s.getString("key"), s.getString("label"), s.getString("type"),
                    s.getString("value"),
                    s.has("minimum") ? Long.parseLong(s.getString("minimum")) : 0L,
                    s.has("maximum") ? Long.parseLong(s.getString("maximum")) : 0L, ids, labels));
        }
        return out;
    }

    private static String readAsset(Context context, String name) throws IOException {
        try (InputStream in = context.getAssets().open(name)) {
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] buffer = new byte[4096];
            for (int n; (n = in.read(buffer)) > 0; ) out.write(buffer, 0, n);
            return new String(out.toByteArray(), StandardCharsets.UTF_8);
        }
    }

    String schema() { return schema; }
    List<LevelSettingField> fields() { return fields; }

    /** The saved choice, or the level's own default. */
    String valueOf(LevelSettingField field) {
        String saved = prefs.getString(field.key, null);
        return saved == null ? field.defaultValue : saved;
    }

    private LevelSettingField byWireId(String wireId) {
        for (LevelSettingField field : fields) {
            if (field.wireId(prefix).equals(wireId)) return field;
        }
        throw new IllegalArgumentException("Unknown setting " + wireId);
    }

    /** The current value of the field with this wire id (saved choice or default). */
    String currentValue(String wireId) { return valueOf(byWireId(wireId)); }

    /** True for the ids this object serves (the provider routes on it). */
    boolean owns(String wireId) { return wireId != null && wireId.startsWith(prefix); }

    /** Validate and save one value; IllegalArgumentException saves nothing. Choosing the level's own default clears the choice. */
    boolean set(String wireId, String requested) {
        LevelSettingField field = byWireId(wireId);
        String value = field.validate(requested);
        SharedPreferences.Editor editor = prefs.edit();
        if (value.equals(field.defaultValue)) editor.remove(field.key);
        else editor.putString(field.key, value);
        return editor.commit();
    }

    boolean reset() { return prefs.edit().clear().commit(); }

    /** The user's changed values by OAD field key: what the engine's launch overrides take. */
    Map<String, String> overrides() {
        Map<String, String> out = new LinkedHashMap<>();
        for (LevelSettingField field : fields) {
            String saved = prefs.getString(field.key, null);
            if (saved == null) continue;
            try {
                out.put(field.key, field.engineValue(field.validate(saved)));   // a stale or hand-edited value is dropped
            } catch (IllegalArgumentException stale) {
                // Not an option or out of range any more: the level's default applies.
            }
        }
        return out;
    }

    /** The provider's entries (schema 1 shape: id, type, label, value, options or range). */
    JSONArray capabilityEntries() throws JSONException {
        JSONArray out = new JSONArray();
        for (LevelSettingField field : fields) {
            JSONObject entry = new JSONObject().put("id", field.wireId(prefix))
                    .put("type", field.type).put("label", title + ": " + field.label)
                    .put("value", valueOf(field));
            if (LevelSettingField.CHOICE.equals(field.type)) {
                JSONArray options = new JSONArray();
                for (int i = 0; i < field.optionIds.size(); i++) {
                    options.put(new JSONObject().put("id", field.optionIds.get(i))
                            .put("label", field.optionLabels.get(i)));
                }
                entry.put("options", options);
            } else if (LevelSettingField.INTEGER.equals(field.type)) {
                entry.put("minimum", Long.toString(field.minimum)).put("maximum", Long.toString(field.maximum));
            }   // a boolean has neither options nor a range
            out.put(entry);
        }
        return out;
    }
}
