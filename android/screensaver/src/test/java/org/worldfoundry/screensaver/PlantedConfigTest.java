package org.worldfoundry.screensaver;

/**
 * Plain-Java checks of PlantedConfig (JUnit is not in the offline Gradle cache). Run with:
 * javac -d out src/main/java/.../PlantedConfig.java src/test/java/.../PlantedConfigTest.java
 * java -cp out org.worldfoundry.screensaver.PlantedConfigTest
 */
public final class PlantedConfigTest {
    private static int checks;
    private static int failures;

    private static void check(boolean ok, String what) {
        checks++;
        if (!ok) {
            failures++;
            System.out.println("FAIL " + what);
        }
    }

    private static void accepts(String key, Object value, String line) {
        try {
            String got = PlantedConfig.defaults().with(key, value).toLine();
            check(line.equals(got), key + "=" + value + " -> \"" + got + "\", wanted \"" + line + "\"");
        } catch (IllegalArgumentException error) {
            check(false, key + "=" + value + " was rejected: " + error.getMessage());
        }
    }

    private static void rejects(String key, Object value, String message) {
        try {
            PlantedConfig config = PlantedConfig.defaults().with(key, value);
            check(false, key + "=" + value + " was accepted as \"" + config.toLine() + "\"");
        } catch (IllegalArgumentException error) {
            check(error.getMessage().contains(message),
                    key + "=" + value + " message \"" + error.getMessage() + "\" lacks \"" + message + "\"");
        }
    }

    public static void main(String[] args) {
        PlantedConfig none = PlantedConfig.defaults();
        check(none.toLine().isEmpty(), "defaults serialise to an empty line");
        check(none.water().equals("random"), "default water random");
        check(!none.hasSeed(), "default seed absent");
        check(none.speed() == 1.0 && none.speedIndex() == 3, "default speed 1x is engine index 3");
        check(none.hold() == 120, "default hold 120");
        check(none.age() == 0.0 && none.textures() && none.sway(), "developer defaults");

        // water
        accepts("water", "freshwater", "water=freshwater");
        accepts("water", "saltwater", "water=saltwater");
        accepts("water", "random", "water=random");
        accepts("water", "fresh", "water=freshwater");
        accepts("water", "salt", "water=saltwater");
        accepts("water", " SaltWater ", "water=saltwater");
        for (String bad : new String[] {"", "sea", "brackish", "freshwaters"}) {
            rejects("water", bad, "water must be freshwater, saltwater or random");
        }
        rejects("water", 3, "water must be");
        rejects("water", null, "water must be");

        // seed
        accepts("seed", "0", "seed=0");
        accepts("seed", "713", "seed=713");
        accepts("seed", "4294967295", "seed=4294967295");
        accepts("seed", 4294967295L, "seed=4294967295");
        accepts("seed", 713, "seed=713");
        String seedMessage = "seed must be a whole number from 0 to 4294967295";
        rejects("seed", "4294967296", seedMessage);
        rejects("seed", 4294967296L, seedMessage);
        rejects("seed", "99999999999999999999999", seedMessage);
        rejects("seed", "-1", seedMessage);
        rejects("seed", -1L, seedMessage);
        rejects("seed", "1.5", seedMessage);
        rejects("seed", 1.0f, seedMessage);
        rejects("seed", "abc", seedMessage);
        rejects("seed", "", seedMessage);
        rejects("seed", "0x10", seedMessage);
        PlantedConfig seeded = none.withSeed(4294967295L);
        check(seeded.hasSeed() && seeded.seed() == 4294967295L, "seed stored as a long");

        // speed
        String[] speeds = {"0.25", "0.5", "1", "2", "4", "8"};
        int[] indexes = {1, 2, 3, 4, 5, 6};
        for (int i = 0; i < speeds.length; i++) {
            accepts("speed", speeds[i], "speed=" + speeds[i]);
            check(none.withSpeed(speeds[i]).speedIndex() == indexes[i], "speed index of " + speeds[i]);
        }
        accepts("speed", "1.0", "speed=1");
        accepts("speed", "2.00", "speed=2");
        accepts("speed", 0.25f, "speed=0.25");
        accepts("speed", 8, "speed=8");
        accepts("speed", 0.5d, "speed=0.5");
        check(PlantedConfig.indexOfSpeed(0.0) == 0, "engine index 0 is paused");
        check(PlantedConfig.indexOfSpeed(3.0) == -1, "3 is not an engine speed");
        String paused = "speed 0 is paused";
        rejects("speed", "0", paused);
        rejects("speed", 0, paused);
        rejects("speed", 0.0f, paused);
        rejects("speed", "0.0", paused);
        String speedMessage = "speed must be 0.25, 0.5, 1, 2, 4 or 8";
        for (String bad : new String[] {"3", "16", "0.3", "-1", "-0.5", "abc", "", "NaN", "Infinity", "1e1"}) {
            rejects("speed", bad, "speed");
        }
        rejects("speed", "3", speedMessage);
        rejects("speed", 1.1f, speedMessage);
        rejects("speed", Double.NaN, speedMessage);
        rejects("speed", Float.POSITIVE_INFINITY, speedMessage);

        // hold
        accepts("hold", "0", "hold=0");
        accepts("hold", "120", "hold=120");
        accepts("hold", 86400, "hold=86400");
        accepts("hold", "86400", "hold=86400");
        String holdMessage = "hold must be a whole number of seconds from 0 to 86400";
        rejects("hold", "86401", holdMessage);
        rejects("hold", 86401, holdMessage);
        rejects("hold", "-1", holdMessage);
        rejects("hold", -5, holdMessage);
        rejects("hold", "1.5", holdMessage);
        rejects("hold", 1.5f, holdMessage);
        rejects("hold", "two", holdMessage);

        // developer keys
        accepts("age", "0", "age=0");
        accepts("age", "30.5", "age=30.5");
        accepts("age", "240", "age=240");
        accepts("age", 12.0f, "age=12");
        accepts("age", 0.1f, "age=0.1");
        String ageMessage = "age must be a number from 0 to 240";
        rejects("age", "240.5", ageMessage);
        rejects("age", 241.0f, ageMessage);
        rejects("age", "-1", ageMessage);
        rejects("age", "NaN", ageMessage);
        rejects("age", Float.NaN, ageMessage);
        rejects("age", "soon", ageMessage);
        accepts("textures", "true", "textures=true");
        accepts("textures", "false", "textures=false");
        accepts("textures", Boolean.FALSE, "textures=false");
        accepts("sway", "FALSE", "sway=false");
        accepts("sway", Boolean.TRUE, "sway=true");
        rejects("textures", "yes", "textures must be true or false");
        rejects("sway", "1", "sway must be true or false");
        rejects("sway", 1, "sway must be true or false");

        // unknown keys: there are no seahorses, label or cycles parameters
        for (String unknown : new String[] {"seahorses", "label", "cycles", "Water", "", "tank"}) {
            rejects(unknown, "1", "unknown setting \"" + unknown + "\"");
        }
        rejects(null, "1", "unknown setting");
        rejects("label", "1", "known: water, seed, speed, hold, age, textures, sway");

        // toLine: only explicit keys, fixed order, absent seed stays absent
        PlantedConfig mixed = none.withSway("false").withWater("salt").withHold("30").withSpeed("2");
        check("water=saltwater;speed=2;hold=30;sway=false".equals(mixed.toLine()),
                "toLine order: " + mixed.toLine());
        check(!mixed.toLine().contains("seed"), "absent seed not listed");
        check("water=freshwater;seed=713;speed=0.25;hold=0;age=12.5;textures=false;sway=true".equals(
                none.withSway("true").withTextures("false").withAge("12.5").withHold("0")
                        .withSpeed("0.25").withSeed("713").withWater("fresh").toLine()),
                "toLine with every key");
        check(mixed.valueOf("seed").equals("random"), "absent seed reads as random");
        check(mixed.valueOf("speed").equals("2") && mixed.valueOf("hold").equals("30"), "valueOf");
        check(mixed.withWater("random").toLine().startsWith("water=random;"), "explicit random is listed");

        // a rejection leaves the original untouched (immutability)
        PlantedConfig base = none.withWater("salt");
        try { base.withSeed("x"); } catch (IllegalArgumentException expected) { }
        check("water=saltwater".equals(base.toLine()), "rejection leaves the base config unchanged");

        System.out.println(checks + " checks, " + failures + " failures");
        if (failures != 0) System.exit(1);
    }
}
