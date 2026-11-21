package org.worldfoundry.screensaver;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Random;

/**
 * The levels of one screensaver package, read from its level manifest (the same file cdpack packs
 * the menu bundle from; for the Aquarium, wflevels/aquarium-menu.manifest, copied into the flavor's
 * assets as {@link #ASSET} by Gradle). Generic: any package with a manifest of this format uses it.
 *
 * <p>Format, one entry per line: {@code # comment}, blank, {@code title <text>},
 * {@code prompt <text>}, {@code level <id>-standalone.iff | <menu name> [| <dream label>]}. Text is
 * printable ASCII, 1 to 60 characters (cdpack's rule). A level's id is its file name without
 * {@code -standalone.iff}; its label is the Dream label, or the menu name when there is none. The
 * order is the bundle's level order, so {@link #indexOf} is the level's index in the bundle.
 *
 * <p>Plain Java (no Android imports) so LevelCatalogTest runs with javac alone.
 * docs/plans/2026-11-21-aquarium-menu-and-screensaver-launch.md, Phase 2.
 */
final class LevelCatalog {
    /** The asset name a flavor's Gradle copy gives its manifest. */
    static final String ASSET = "levels.manifest";
    /** The saved-choice value that draws a level when the Dream starts. Never a level id. */
    static final String RANDOM = "random";
    static final String SUFFIX = "-standalone.iff";
    private static final int MAX_TEXT = 60;

    /** Opens the manifest; Android passes its asset, the test a file. */
    interface Source {
        InputStream open() throws IOException;
    }

    private static LevelCatalog shared;

    private final String title;
    private final String prompt;
    private final List<String> ids;
    private final List<String> labels;

    private LevelCatalog(String title, String prompt, List<String> ids, List<String> labels) {
        this.title = title;
        this.prompt = prompt;
        this.ids = Collections.unmodifiableList(ids);
        this.labels = Collections.unmodifiableList(labels);
    }

    /** The process's catalogue, read once from {@code source} on first use. A bad manifest throws. */
    static synchronized LevelCatalog shared(Source source) {
        if (shared == null) {
            try {
                shared = read(source.open(), ASSET);
            } catch (IOException error) {
                throw new IllegalStateException("cannot read the level catalogue " + ASSET, error);
            }
        }
        return shared;
    }

    /** Parse a whole manifest stream (closed afterwards). */
    static LevelCatalog read(InputStream in, String origin) throws IOException {
        try {
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            byte[] buffer = new byte[4096];
            for (int n; (n = in.read(buffer)) > 0; ) bytes.write(buffer, 0, n);
            return parse(new String(bytes.toByteArray(), StandardCharsets.UTF_8), origin);
        } finally {
            in.close();
        }
    }

    /** Parse manifest text; a malformed line throws IllegalArgumentException naming origin:line. */
    static LevelCatalog parse(String text, String origin) {
        String title = "World Foundry";
        String prompt = "Choose a game";
        List<String> ids = new ArrayList<>();
        List<String> labels = new ArrayList<>();
        String[] lines = text.split("\r?\n", -1);
        for (int n = 0; n < lines.length; n++) {
            String where = origin + ":" + (n + 1);
            String line = lines[n].trim();
            if (line.isEmpty() || line.startsWith("#")) continue;
            int space = indexOfWhitespace(line);
            String key = space < 0 ? line : line.substring(0, space);
            String rest = space < 0 ? "" : line.substring(space).trim();
            if ("title".equals(key)) {
                title = checkText(where, "title", rest);
            } else if ("prompt".equals(key)) {
                prompt = checkText(where, "prompt", rest);
            } else if ("level".equals(key)) {
                String[] fields = rest.split("\\|", -1);
                if (fields.length < 2 || fields.length > 3) {
                    throw new IllegalArgumentException(
                            where + ": want `level <id>" + SUFFIX + " | <menu name> [| <dream label>]`");
                }
                String file = fields[0].trim();
                if (!file.endsWith(SUFFIX) || file.length() == SUFFIX.length()
                        || file.indexOf('/') >= 0 || file.indexOf('\\') >= 0) {
                    throw new IllegalArgumentException(
                            where + ": level file must be <id>" + SUFFIX + " beside the manifest, got \"" + file + "\"");
                }
                String id = file.substring(0, file.length() - SUFFIX.length());
                if (RANDOM.equals(id)) {
                    throw new IllegalArgumentException(where + ": \"" + RANDOM + "\" is reserved, not a level id");
                }
                if (ids.contains(id)) {
                    throw new IllegalArgumentException(where + ": level \"" + id + "\" is listed twice");
                }
                String name = checkText(where, "menu name", fields[1].trim());
                String label = fields.length == 3 ? checkText(where, "dream label", fields[2].trim()) : name;
                ids.add(id);
                labels.add(label);
            } else {
                throw new IllegalArgumentException(
                        where + ": unknown keyword \"" + key + "\" (want title, prompt or level)");
            }
        }
        if (ids.isEmpty()) throw new IllegalArgumentException(origin + ": no \"level\" lines");
        return new LevelCatalog(title, prompt, ids, labels);
    }

    private static int indexOfWhitespace(String s) {
        for (int i = 0; i < s.length(); i++) {
            if (Character.isWhitespace(s.charAt(i))) return i;
        }
        return -1;
    }

    private static String checkText(String where, String what, String s) {
        if (s.isEmpty() || s.length() > MAX_TEXT) {
            throw new IllegalArgumentException(where + ": " + what + " must be 1 to " + MAX_TEXT
                    + " characters, got " + s.length() + ": \"" + s + "\"");
        }
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c < ' ' || c > '~') {
                throw new IllegalArgumentException(where + ": " + what + " has a character that is not printable ASCII: \"" + s + "\"");
            }
        }
        return s;
    }

    String title() { return title; }

    String prompt() { return prompt; }

    /** The level ids, in bundle order. */
    List<String> ids() { return ids; }

    int size() { return ids.size(); }

    /** A level id, or {@link #RANDOM}. */
    boolean valid(String id) {
        return RANDOM.equals(id) || ids.contains(id);
    }

    /** The level's index in the bundle; an id the catalogue does not hold throws. */
    int indexOf(String id) {
        int index = ids.indexOf(id);
        if (index < 0) throw new IllegalArgumentException("unknown level \"" + id + "\"");
        return index;
    }

    /** The level's Dream label; an id the catalogue does not hold throws. */
    String label(String id) {
        return labels.get(indexOf(id));
    }

    /**
     * The level one run plays. {@code requested} is the one-run LEVEL extra (null when absent): an id,
     * {@link #RANDOM}, or an unknown id, which throws IllegalArgumentException naming it (no
     * fallback). With no request the saved choice ({@code saved}, an id or {@link #RANDOM}) decides.
     * Random is resolved here, once. Writes nothing; the saved choice is the caller's.
     */
    String choose(String requested, String saved, Random rng) {
        String wanted = requested != null ? requested : saved;
        if (RANDOM.equals(wanted)) return chooseRandom(rng);
        if (!ids.contains(wanted)) {
            throw new IllegalArgumentException("unknown level \"" + wanted + "\" (the catalogue holds " + ids + ")");
        }
        return wanted;
    }

    /** One level drawn uniformly. */
    String chooseRandom(Random rng) {
        return ids.get(rng.nextInt(ids.size()));
    }
}
