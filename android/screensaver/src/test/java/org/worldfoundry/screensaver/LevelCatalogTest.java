package org.worldfoundry.screensaver;

import java.io.FileInputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Random;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Plain-Java checks of LevelCatalog (JUnit is not in the offline Gradle cache). Run with:
 * javac -d out src/main/java/.../LevelCatalog.java src/test/java/.../LevelCatalogTest.java
 * java -cp out org.worldfoundry.screensaver.LevelCatalogTest [manifest [bundle-order]]
 *
 * <p>With a manifest (wflevels/aquarium-menu.manifest) it also reads the real roster; with a
 * bundle-order file (one id per line, the order scripts/build-aquarium-screensaver-levels.py
 * packs the screensaver bundle in) it checks the catalogue order equals the bundle's.
 * docs/plans/2026-11-21-aquarium-menu-and-screensaver-launch.md, Phase 2, Verification 4.
 */
public final class LevelCatalogTest {
    private static int checks;
    private static int failures;

    private static void check(boolean ok, String what) {
        checks++;
        if (!ok) {
            failures++;
            System.out.println("FAIL " + what);
        }
    }

    private static void rejects(String text, String wanted) {
        try {
            LevelCatalog.parse(text, "m");
            check(false, "accepted " + text.trim() + " (wanted an error containing \"" + wanted + "\")");
        } catch (IllegalArgumentException error) {
            check(error.getMessage().contains(wanted) && error.getMessage().startsWith("m"),
                    "error for " + text.trim() + ": \"" + error.getMessage() + "\", wanted \"" + wanted + "\"");
        }
    }

    private static boolean throwsIllegal(Runnable r) {
        try {
            r.run();
            return false;
        } catch (IllegalArgumentException expected) {
            return true;
        }
    }

    public static void main(String[] args) throws IOException {
        String sample = "# comment\n\ntitle WF Test\nprompt Choose one\n"
                + "level alpha-standalone.iff | Alpha Menu | Alpha\n"
                + "level beta-standalone.iff | Beta Menu\n"
                + "level gamma_two-standalone.iff | Gamma | Gamma Dream\n";
        final LevelCatalog c = LevelCatalog.parse(sample, "sample");
        check(c.ids().equals(Arrays.asList("alpha", "beta", "gamma_two")), "ids in order: " + c.ids());
        check(c.size() == 3, "size " + c.size());
        check("WF Test".equals(c.title()) && "Choose one".equals(c.prompt()), "title and prompt");
        check("Alpha".equals(c.label("alpha")), "third column is the label");
        check("Beta Menu".equals(c.label("beta")), "no third column: the menu name is the label");
        check("Gamma Dream".equals(c.label("gamma_two")), "label gamma_two");
        check(c.indexOf("alpha") == 0 && c.indexOf("beta") == 1 && c.indexOf("gamma_two") == 2, "indexOf");
        check(c.valid("beta") && c.valid(LevelCatalog.RANDOM), "valid accepts an id and random");
        check(!c.valid("delta") && !c.valid("") && !c.valid(null) && !c.valid("alpha-standalone.iff"),
                "valid rejects unknown ids");
        check(throwsIllegal(() -> c.indexOf("delta")), "indexOf of an unknown id throws");
        check(throwsIllegal(() -> c.indexOf(LevelCatalog.RANDOM)), "indexOf of random throws");
        check(throwsIllegal(() -> c.label("delta")), "label of an unknown id throws");
        boolean[] seen = new boolean[3];
        Random rng = new Random(1);
        for (int i = 0; i < 300; i++) seen[c.indexOf(c.chooseRandom(rng))] = true;
        check(seen[0] && seen[1] && seen[2], "chooseRandom reaches every level");
        // choose(): the one-run LEVEL request, else the saved choice (docs/plans/...launch.md, Phase 3).
        Random fixed = new Random(7);
        check("beta".equals(c.choose("beta", "alpha", fixed)), "a requested id wins over the saved one");
        check("alpha".equals(c.choose(null, "alpha", fixed)), "no request: the saved id");
        check(c.valid(c.choose("random", "alpha", fixed)), "request random draws a level");
        check(c.valid(c.choose(null, "random", fixed)), "saved random draws a level");
        boolean[] drawn = new boolean[3];
        for (int i = 0; i < 300; i++) drawn[c.indexOf(c.choose("random", "alpha", fixed))] = true;
        check(drawn[0] && drawn[1] && drawn[2], "choose(random) reaches every level");
        check(throwsIllegal(() -> c.choose("delta", "alpha", new Random(1))), "an unknown request throws");
        check(throwsIllegal(() -> c.choose("", "alpha", new Random(1))), "an empty request throws, not the saved level");
        check(throwsIllegal(() -> c.choose("alpha-standalone.iff", "alpha", new Random(1))), "a file name is not an id");
        try {
            c.choose("delta", "alpha", new Random(1));
        } catch (IllegalArgumentException error) {
            check(error.getMessage().contains("\"delta\""), "the error names the id: " + error.getMessage());
        }
        try {
            c.ids().add("x");
            check(false, "ids() is modifiable");
        } catch (UnsupportedOperationException expected) {
            check(true, "ids() is read-only");
        }
        check(LevelCatalog.parse("level a-standalone.iff | A\r\nlevel b-standalone.iff | B\r\n", "crlf")
                .ids().equals(Arrays.asList("a", "b")), "CRLF lines");

        rejects("title T\n", "no \"level\" lines");
        rejects("level a-standalone.iff\n", "want `level");
        rejects("level a-standalone.iff | A | B | C\n", "want `level");
        rejects("level a-standalone.iff | A |\n", "dream label must be 1 to 60");
        rejects("level a-standalone.iff |  | A\n", "menu name must be 1 to 60");
        rejects("level a.iff | A\n", "level file must be <id>-standalone.iff");
        rejects("level -standalone.iff | A\n", "level file must be");
        rejects("level sub/a-standalone.iff | A\n", "level file must be");
        rejects("level random-standalone.iff | Random\n", "reserved");
        rejects("level a-standalone.iff | A\nlevel a-standalone.iff | A again\n", "listed twice");
        rejects("levle a-standalone.iff | A\n", "unknown keyword");
        rejects("level a-standalone.iff | Wörld\n", "not printable ASCII");
        rejects("level a-standalone.iff | " + new String(new char[61]).replace('\0', 'x') + "\n", "1 to 60");
        rejects("level a-standalone.iff | A\nlevel b-standalone.iff | B\nbogus\n", "m:3");

        if (args.length >= 1) {
            LevelCatalog real = LevelCatalog.read(new FileInputStream(args[0]), args[0]);
            List<String> expected = new ArrayList<>();
            Matcher m = Pattern.compile("(?m)^level\\s+(\\S+)-standalone\\.iff\\s*\\|")
                    .matcher(new String(Files.readAllBytes(Paths.get(args[0])), StandardCharsets.UTF_8));
            while (m.find()) expected.add(m.group(1));
            check(real.ids().equals(expected), "real manifest ids " + real.ids() + " vs " + expected);
            for (String id : real.ids()) check(!real.label(id).isEmpty(), "label of " + id);
            check(!real.valid("aquarium_no_such_tank"), "real catalogue rejects an unknown id");
            if (args.length >= 2) {
                List<String> bundle = new ArrayList<>();
                for (String line : Files.readAllLines(Paths.get(args[1]), StandardCharsets.UTF_8)) {
                    if (!line.trim().isEmpty()) bundle.add(line.trim());
                }
                check(real.ids().equals(bundle), "catalogue order " + real.ids() + " vs bundle order " + bundle);
            }
        }

        System.out.println(checks + " checks, " + failures + " failures");
        if (failures != 0) System.exit(1);
    }
}
