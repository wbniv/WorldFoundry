package org.worldfoundry.screensaver;

import java.math.BigDecimal;
import java.util.Locale;
import java.util.regex.Pattern;

/**
 * Validated Planted Tank parameters. Pure Java (no Android types) so it runs under plain javac.
 *
 * <p>Instances are immutable. Each {@code with*} method returns a new config or throws
 * {@link IllegalArgumentException} with a short message that is safe to show to the user.
 * Getters return the effective value (the default when the key was never set);
 * {@link #toLine()} lists only the keys that were set explicitly, so the native side applies
 * its own defaults to the rest: water random, a fresh seed per tank, speed 1, hold 120,
 * age 0, textures and sway on.
 */
final class PlantedConfig {
    static final String WATER = "water";
    static final String SEED = "seed";
    static final String SPEED = "speed";
    static final String HOLD = "hold";
    static final String AGE = "age";
    static final String TEXTURES = "textures";
    static final String SWAY = "sway";

    /** Every accepted key, in the order {@link #toLine()} writes them. */
    static final String[] KEYS = { WATER, SEED, SPEED, HOLD, AGE, TEXTURES, SWAY };

    static final String FRESHWATER = "freshwater";
    static final String SALTWATER = "saltwater";
    static final String RANDOM = "random";

    static final long SEED_MAX = 4294967295L;
    static final long HOLD_MAX = 86400L;
    static final double AGE_MAX = 240.0;

    static final String DEFAULT_WATER = RANDOM;
    static final double DEFAULT_SPEED = 1.0;
    static final long DEFAULT_HOLD = 120L;

    /** The engine's growth speed table, index 0 is paused. Index 3 is 1x. */
    private static final double[] ENGINE_SPEEDS = { 0.0, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0 };

    private static final Pattern DIGITS = Pattern.compile("\\d{1,19}");
    private static final Pattern DECIMAL = Pattern.compile("\\d+(\\.\\d+)?");

    private final String water;
    private final Long seed;
    private final Double speed;
    private final Long hold;
    private final Double age;
    private final Boolean textures;
    private final Boolean sway;

    private PlantedConfig(String water, Long seed, Double speed, Long hold, Double age,
                          Boolean textures, Boolean sway) {
        this.water = water;
        this.seed = seed;
        this.speed = speed;
        this.hold = hold;
        this.age = age;
        this.textures = textures;
        this.sway = sway;
    }

    /** A config with nothing set explicitly. */
    static PlantedConfig defaults() {
        return new PlantedConfig(null, null, null, null, null, null, null);
    }

    static boolean isKey(String key) {
        for (String known : KEYS) {
            if (known.equals(key)) return true;
        }
        return false;
    }

    // ---- getters (effective values) ----

    String water() { return water == null ? DEFAULT_WATER : water; }
    boolean hasSeed() { return seed != null; }
    /** The explicit seed; only meaningful when {@link #hasSeed()}. */
    long seed() { return seed == null ? 0L : seed; }
    double speed() { return speed == null ? DEFAULT_SPEED : speed; }
    /** The engine's growth speed index for {@link #speed()}: 1 is 0.25x, 3 is 1x, 6 is 8x. */
    int speedIndex() { return indexOfSpeed(speed()); }
    long hold() { return hold == null ? DEFAULT_HOLD : hold; }
    double age() { return age == null ? 0.0 : age; }
    boolean textures() { return textures == null ? true : textures; }
    boolean sway() { return sway == null ? true : sway; }

    /** Index into the engine's speed table (0 paused, 0.25, 0.5, 1, 2, 4, 8), or -1. */
    static int indexOfSpeed(double value) {
        for (int i = 0; i < ENGINE_SPEEDS.length; i++) {
            if (ENGINE_SPEEDS[i] == value) return i;
        }
        return -1;
    }

    /** Every water value {@link #withWater} accepts in canonical form. */
    static String[] waterValues() { return new String[] { RANDOM, FRESHWATER, SALTWATER }; }

    /** Every speed {@link #withSpeed} accepts, in canonical text (paused is not one). */
    static String[] speedValues() {
        String[] values = new String[ENGINE_SPEEDS.length - 1];
        for (int i = 1; i < ENGINE_SPEEDS.length; i++) values[i - 1] = number(ENGINE_SPEEDS[i]);
        return values;
    }

    // ---- validation ----

    /**
     * Sets one key from a string, a Number, or (for textures and sway) a Boolean, as an
     * Intent extra or a saved preference would supply it.
     */
    PlantedConfig with(String key, Object value) {
        if (key == null || !isKey(key)) {
            throw new IllegalArgumentException("unknown setting \"" + key + "\"; known: "
                    + String.join(", ", KEYS));
        }
        switch (key) {
            case WATER: return withWater(value);
            case SEED: return withSeed(value);
            case SPEED: return withSpeed(value);
            case HOLD: return withHold(value);
            case AGE: return withAge(value);
            case TEXTURES: return withTextures(value);
            default: return withSway(value);
        }
    }

    PlantedConfig withWater(Object value) {
        String text = value instanceof String ? ((String) value).trim().toLowerCase(Locale.ROOT) : "";
        String canonical;
        switch (text) {
            case "freshwater": case "fresh": canonical = FRESHWATER; break;
            case "saltwater": case "salt": canonical = SALTWATER; break;
            case "random": canonical = RANDOM; break;
            default:
                throw new IllegalArgumentException(
                        "water must be freshwater, saltwater or random");
        }
        return new PlantedConfig(canonical, seed, speed, hold, age, textures, sway);
    }

    PlantedConfig withSeed(Object value) {
        long parsed = wholeNumber(value, SEED_MAX,
                "seed must be a whole number from 0 to 4294967295");
        return new PlantedConfig(water, parsed, speed, hold, age, textures, sway);
    }

    PlantedConfig withSpeed(Object value) {
        double parsed = decimal(value, Double.NaN);
        if (parsed == 0.0) {
            throw new IllegalArgumentException(
                    "speed 0 is paused and the tank would never finish; use 0.25, 0.5, 1, 2, 4 or 8");
        }
        if (indexOfSpeed(parsed) < 0) {
            throw new IllegalArgumentException("speed must be 0.25, 0.5, 1, 2, 4 or 8");
        }
        return new PlantedConfig(water, seed, parsed, hold, age, textures, sway);
    }

    PlantedConfig withHold(Object value) {
        long parsed = wholeNumber(value, HOLD_MAX,
                "hold must be a whole number of seconds from 0 to 86400");
        return new PlantedConfig(water, seed, speed, parsed, age, textures, sway);
    }

    PlantedConfig withAge(Object value) {
        double parsed = decimal(value, AGE_MAX);
        return new PlantedConfig(water, seed, speed, hold, parsed, textures, sway);
    }

    PlantedConfig withTextures(Object value) {
        return new PlantedConfig(water, seed, speed, hold, age, bool(value, TEXTURES), sway);
    }

    PlantedConfig withSway(Object value) {
        return new PlantedConfig(water, seed, speed, hold, age, textures, bool(value, SWAY));
    }

    /** Parses a non-negative whole number no larger than {@code max}; Float and Double are rejected. */
    private static long wholeNumber(Object value, long max, String message) {
        long parsed;
        if (value instanceof Long || value instanceof Integer
                || value instanceof Short || value instanceof Byte) {
            parsed = ((Number) value).longValue();
        } else if (value instanceof String && DIGITS.matcher(((String) value).trim()).matches()) {
            try {
                parsed = Long.parseLong(((String) value).trim());
            } catch (NumberFormatException tooBig) {
                throw new IllegalArgumentException(message);
            }
        } else {
            throw new IllegalArgumentException(message);
        }
        if (parsed < 0 || parsed > max) throw new IllegalArgumentException(message);
        return parsed;
    }

    /**
     * Parses a finite non-negative decimal. When {@code max} is a number the value must not
     * exceed it and the failure message is the age message; with NaN as {@code max} there is
     * no range check (the caller checks against a table).
     */
    private static double decimal(Object value, double max) {
        String message = Double.isNaN(max) ? "speed must be 0.25, 0.5, 1, 2, 4 or 8"
                : "age must be a number from 0 to 240";
        double parsed;
        if (value instanceof Float) {
            parsed = Double.parseDouble(value.toString());
        } else if (value instanceof Number && !(value instanceof java.math.BigInteger)
                && !(value instanceof BigDecimal)) {
            parsed = ((Number) value).doubleValue();
        } else if (value instanceof String && DECIMAL.matcher(((String) value).trim()).matches()) {
            parsed = Double.parseDouble(((String) value).trim());
        } else {
            throw new IllegalArgumentException(message);
        }
        if (Double.isNaN(parsed) || Double.isInfinite(parsed) || parsed < 0
                || (!Double.isNaN(max) && parsed > max)) {
            throw new IllegalArgumentException(message);
        }
        return parsed;
    }

    private static boolean bool(Object value, String key) {
        if (value instanceof Boolean) return (Boolean) value;
        if (value instanceof String) {
            String text = ((String) value).trim().toLowerCase(Locale.ROOT);
            if (text.equals("true")) return true;
            if (text.equals("false")) return false;
        }
        throw new IllegalArgumentException(key + " must be true or false");
    }

    // ---- serialisation ----

    /** The canonical text of one key's effective value, as stored and shown. */
    String valueOf(String key) {
        switch (key) {
            case WATER: return water();
            case SEED: return hasSeed() ? Long.toString(seed) : RANDOM;
            case SPEED: return number(speed());
            case HOLD: return Long.toString(hold());
            case AGE: return number(age());
            case TEXTURES: return Boolean.toString(textures());
            case SWAY: return Boolean.toString(sway());
            default: throw new IllegalArgumentException("unknown setting \"" + key + "\"");
        }
    }

    /** True when the key was set explicitly rather than left at its default. */
    boolean isSet(String key) {
        switch (key) {
            case WATER: return water != null;
            case SEED: return seed != null;
            case SPEED: return speed != null;
            case HOLD: return hold != null;
            case AGE: return age != null;
            case TEXTURES: return textures != null;
            case SWAY: return sway != null;
            default: return false;
        }
    }

    /** {@code key=value;key=value} for the native call, explicitly set keys only. */
    String toLine() {
        StringBuilder line = new StringBuilder();
        for (String key : KEYS) {
            if (!isSet(key)) continue;
            if (line.length() > 0) line.append(';');
            line.append(key).append('=').append(valueOf(key));
        }
        return line.toString();
    }

    /** Whole numbers print without a fraction: 1, 0.25, 30.5. */
    private static String number(double value) {
        return BigDecimal.valueOf(value).stripTrailingZeros().toPlainString();
    }

    @Override public String toString() { return toLine(); }
}
