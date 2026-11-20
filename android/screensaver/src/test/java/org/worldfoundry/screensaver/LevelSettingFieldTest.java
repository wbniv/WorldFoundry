package org.worldfoundry.screensaver;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;

/**
 * Plain-Java checks of LevelSettingField (JUnit is not in the offline Gradle cache). Run with:
 * javac -d out src/main/java/.../LevelSettingField.java src/test/java/.../LevelSettingFieldTest.java
 * java -cp out org.worldfoundry.screensaver.LevelSettingFieldTest
 */
public final class LevelSettingFieldTest {
    private static int checks;
    private static int failures;

    private static void check(boolean ok, String what) {
        checks++;
        if (!ok) {
            failures++;
            System.out.println("FAIL " + what);
        }
    }

    private static boolean rejects(LevelSettingField field, String value) {
        try {
            field.validate(value);
            return false;
        } catch (IllegalArgumentException expected) {
            return true;
        }
    }

    private static LevelSettingField choice(String key, String... labels) {
        String[] ids = new String[labels.length];
        for (int i = 0; i < ids.length; i++) ids[i] = Integer.toString(i);
        return new LevelSettingField(key, key, "choice", "1", 0, 0, Arrays.asList(ids), Arrays.asList(labels));
    }

    public static void main(String[] args) {
        // The wire ids the coordinator and the phone use.
        String[][] ids = {{"Chocolate-chip stars", "chocolate-chip-stars"}, {"Red Fromia", "red-fromia"},
                {"Sand-sifting stars", "sand-sifting-stars"}, {"Brittle stars", "brittle-stars"},
                {"Cushion stars", "cushion-stars"}, {"Speed", "speed"}, {"Glass climbing", "glass-climbing"},
                {"Caustics", "caustics"}, {"Seed", "seed"}, {"  Odd  --  Key!! ", "odd-key"}};
        for (String[] pair : ids) check(LevelSettingField.slug(pair[0]).equals(pair[1]), "slug " + pair[0]);
        check(choice("Speed", "Slow", "Normal", "Fast").wireId("sea-stars.").equals("sea-stars.speed"), "wire id");
        check(LevelSettingField.slug("").isEmpty(), "empty key");

        // A choice accepts only its option ids.
        LevelSettingField speed = choice("Speed", "Slow", "Normal", "Fast");
        for (String ok : new String[] {"0", "1", "2"}) check(speed.validate(ok).equals(ok), "choice " + ok);
        for (String bad : new String[] {"3", "-1", "Slow", "01", "1.0", " 1", "", "99999999999999999999"}) {
            check(rejects(speed, bad), "choice rejects '" + bad + "'");
        }
        check(rejects(speed, null), "choice rejects null");
        check(speed.display("2").equals("Fast") && speed.display("9").equals("9"), "display");

        // A count: 0..4.
        LevelSettingField chips = new LevelSettingField("Chocolate-chip stars", "Chocolate-chip stars", "choice", "2",
                0, 0, Arrays.asList("0", "1", "2", "3", "4"), Arrays.asList("0", "1", "2", "3", "4"));
        check(chips.validate("4").equals("4") && rejects(chips, "5"), "count range");

        // Seed: a whole number 0..2147483647, canonical.
        List<String> none = Collections.emptyList();
        LevelSettingField seed = new LevelSettingField("Seed", "Seed", "integer", "0", 0, 2147483647L, none, none);
        check(seed.validate("0").equals("0"), "seed 0");
        check(seed.validate("4242").equals("4242"), "seed 4242");
        check(seed.validate("2147483647").equals("2147483647"), "seed max");
        for (String bad : new String[] {"2147483648", "-1", "+5", "007", " 7", "7 ", "1e3", "1.5", "0x10", "",
                "9999999999999999999", "٣"}) {
            check(rejects(seed, bad), "seed rejects '" + bad + "'");
        }

        // The constructor refuses what it cannot serve.
        boolean refused = false;
        try {
            new LevelSettingField("X", "X", "text", "", 0, 0, none, none);
        } catch (IllegalArgumentException expected) {
            refused = true;
        }
        check(refused, "unsupported type refused");
        refused = false;
        try {
            new LevelSettingField("X", "X", "choice", "0", 0, 0, Arrays.asList("0", "1"), Arrays.asList("only"));
        } catch (IllegalArgumentException expected) {
            refused = true;
        }
        check(refused, "mismatched options refused");

        System.out.println(checks + " checks, " + failures + " failures");
        if (failures != 0) System.exit(1);
    }
}
