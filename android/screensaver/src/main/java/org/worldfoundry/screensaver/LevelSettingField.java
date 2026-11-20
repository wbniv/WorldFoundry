package org.worldfoundry.screensaver;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Locale;

/**
 * One setting of a level's settings object, as the capabilities asset generated from the
 * object's OAD describes it (scripts/gen-settings-capabilities.py). Pure Java, so a plain JVM can
 * test it. Nothing here knows which level the field belongs to: the Dream's phone form and its
 * launch overrides work the same for any level whose settings object has an asset.
 */
final class LevelSettingField {
    static final String CHOICE = "choice";
    static final String INTEGER = "integer";

    /** The OAD field key, exactly as the engine's launch overrides name it ("Red Fromia"). */
    final String key;
    final String label;
    final String type;
    /** The level's own default (from the OAD), as a string. */
    final String defaultValue;
    final long minimum;
    final long maximum;
    final List<String> optionIds;
    final List<String> optionLabels;

    LevelSettingField(String key, String label, String type, String defaultValue,
                      long minimum, long maximum, List<String> optionIds, List<String> optionLabels) {
        if (!CHOICE.equals(type) && !INTEGER.equals(type)) {
            throw new IllegalArgumentException("Unsupported setting type " + type);
        }
        if (optionIds.size() != optionLabels.size()) {
            throw new IllegalArgumentException("Option ids and labels differ in length");
        }
        this.key = key;
        this.label = label;
        this.type = type;
        this.defaultValue = defaultValue;
        this.minimum = minimum;
        this.maximum = maximum;
        this.optionIds = Collections.unmodifiableList(new ArrayList<>(optionIds));
        this.optionLabels = Collections.unmodifiableList(new ArrayList<>(optionLabels));
    }

    /** "Chocolate-chip stars" becomes "chocolate-chip-stars": letters, digits and hyphens. */
    static String slug(String key) {
        StringBuilder out = new StringBuilder();
        boolean pendingHyphen = false;
        for (char c : key.toLowerCase(Locale.ROOT).toCharArray()) {
            if ((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9')) {
                if (pendingHyphen && out.length() > 0) out.append('-');
                pendingHyphen = false;
                out.append(c);
            } else {
                pendingHyphen = true;
            }
        }
        return out.toString();
    }

    /** The id the coordinator and the phone use: {@code prefix + slug(key)}. */
    String wireId(String prefix) { return prefix + slug(key); }

    /**
     * The canonical string for a requested value, or IllegalArgumentException. A choice must be
     * one of its option ids. An integer must be plain digits inside its range: no sign, no
     * spaces, no leading zeros, so "007" and "-1" are refused rather than guessed at.
     */
    String validate(String requested) {
        if (requested == null || requested.isEmpty()) {
            throw new IllegalArgumentException(label + ": empty value");
        }
        if (CHOICE.equals(type)) {
            if (!optionIds.contains(requested)) {
                throw new IllegalArgumentException(label + ": " + requested + " is not an option");
            }
            return requested;
        }
        for (int i = 0; i < requested.length(); i++) {
            char c = requested.charAt(i);
            if (c < '0' || c > '9') throw new IllegalArgumentException(label + ": not a whole number");
        }
        if (requested.length() > 1 && requested.charAt(0) == '0') {
            throw new IllegalArgumentException(label + ": leading zero");
        }
        if (requested.length() > 18) throw new IllegalArgumentException(label + ": out of range");
        long value = Long.parseLong(requested);
        if (value < minimum || value > maximum) {
            throw new IllegalArgumentException(label + ": " + value + " is outside " + minimum + ".." + maximum);
        }
        return Long.toString(value);
    }

    /** The label of a choice's current id, for display; the raw value for an integer. */
    String display(String value) {
        int at = optionIds.indexOf(value);
        return at >= 0 ? optionLabels.get(at) : value;
    }
}
