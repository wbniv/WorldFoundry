package org.worldfoundry.screensaver;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * What the "use for screensaver" chooser shows and sends, for any World Foundry screensaver pack:
 * the pack's roster (its levels.manifest, read by {@link LevelCatalog}) and the value its settings
 * provider has stored. Nothing here knows which pack it serves; every name comes from the roster.
 * docs/plans/2026-11-27-screensaver-chooser.md, "Critical files" and Will's decisions (D4: no Random
 * row; nothing chosen still means Random, which Undo can restore).
 *
 * <p>Plain Java (no Android imports) so ChooserModelTest runs with javac alone. The activity asks
 * this class what each press sends, sends it through the provider, and reports the provider's
 * answer back with {@link #chosen} or {@link #undone}; nothing is assumed saved before then.
 */
final class ChooserModel {
    /** The provider setting every pack's settings provider accepts for its level choice, beside its own id. */
    static final String SETTING = "level";
    /** The provider method that answers the stored choice ({@code level}, and {@code stored} when one is saved). */
    static final String GET_METHOD = "getLevel";
    /** The provider method that saves {@code <setting>:<id>}. */
    static final String SET_METHOD = "setSetting";
    /** The result key holding the raw saved value, before a missing level reads as Random. */
    static final String STORED = "stored";
    static final String RANDOM = LevelCatalog.RANDOM;

    private final String setting;
    private final List<String> ids;
    private final List<String> labels;
    private String stored;
    private String undoValue;
    private String undoRow;

    ChooserModel(String setting, List<String> ids, List<String> labels, String stored) {
        if (setting == null || setting.isEmpty()) throw new IllegalArgumentException("no setting id");
        if (ids.isEmpty() || ids.size() != labels.size()) throw new IllegalArgumentException("ids and labels must match");
        this.setting = setting;
        this.ids = Collections.unmodifiableList(new ArrayList<>(ids));
        this.labels = Collections.unmodifiableList(new ArrayList<>(labels));
        this.stored = stored;
    }

    /** The rows of a roster, in its order, under its Dream labels. */
    static ChooserModel of(LevelCatalog roster, String setting, String stored) {
        List<String> labels = new ArrayList<>();
        for (String id : roster.ids()) labels.add(roster.label(id));
        return new ChooserModel(setting, roster.ids(), labels, stored);
    }

    int size() { return ids.size(); }

    String id(int row) { return ids.get(row); }

    String label(int row) { return labels.get(row); }

    int indexOf(String id) { return ids.indexOf(id); }

    String labelOf(String id) {
        int row = ids.indexOf(id);
        return row < 0 ? null : labels.get(row);
    }

    /** The raw stored value: an id, {@code random}, an id the roster no longer holds, or null when nothing was ever saved. */
    String stored() { return stored; }

    /** The saved level when it is one of the rows; null when nothing is chosen or the saved level is missing. */
    String saved() {
        return stored != null && ids.contains(stored) ? stored : null;
    }

    /** True when no level is chosen, so the screensaver draws one at random (nothing saved, or {@code random}). */
    boolean random() {
        return stored == null || RANDOM.equals(stored);
    }

    /** The stored id when the roster no longer holds it (the screensaver then plays Random); otherwise null. */
    String missing() {
        return stored != null && !RANDOM.equals(stored) && !ids.contains(stored) ? stored : null;
    }

    boolean isSaved(int row) { return ids.get(row).equals(saved()); }

    /** The row focus starts on: the saved level, else the first. */
    int initialFocus() {
        int row = saved() == null ? -1 : ids.indexOf(saved());
        return row < 0 ? 0 : row;
    }

    /** The provider argument that saves {@code value}: {@code <setting>:<value>}. */
    String argument(String value) {
        return setting + ":" + value;
    }

    /**
     * What OK (or a tap) on a row sends: the setSetting argument, or null when that level is already
     * saved and nothing should be written. An id that is not a row throws.
     */
    String choose(String id) {
        if (!ids.contains(id)) throw new IllegalArgumentException("not a row: \"" + id + "\"");
        return id.equals(saved()) ? null : argument(id);
    }

    /**
     * The provider saved {@code id}. Undo then restores what was in effect before: the previous level,
     * or Random when nothing was chosen. A missing level cannot be restored (the provider refuses
     * it), so after one there is no Undo.
     */
    void chosen(String id) {
        if (!ids.contains(id)) throw new IllegalArgumentException("not a row: \"" + id + "\"");
        undoValue = missing() != null ? null : (saved() != null ? saved() : RANDOM);
        undoRow = undoValue == null ? null : id;
        stored = id;
    }

    /** The row carrying Undo, or null. */
    String undoRow() { return undoRow; }

    /** The value Undo restores (a level id or {@code random}), or null when there is no Undo. */
    String undoValue() { return undoValue; }

    /** What Undo sends, or null when there is none. */
    String undoArgument() {
        return undoValue == null ? null : argument(undoValue);
    }

    /** The provider saved the Undo value: it is in effect again, and Undo goes away. */
    void undone() {
        if (undoValue == null) throw new IllegalStateException("nothing to undo");
        stored = undoValue;
        undoValue = null;
        undoRow = null;
    }

    /** Restores an Undo kept across a configuration change; ignored unless it is still meaningful. */
    void restoreUndo(String value, String row) {
        if (value != null && row != null && row.equals(saved()) && (RANDOM.equals(value) || ids.contains(value))) {
            undoValue = value;
            undoRow = row;
        }
    }

    /**
     * The provider was read again (back from a preview, or after another app saved a value). If the
     * stored value changed underneath, the Undo no longer describes the last change, so it goes.
     */
    void refresh(String newStored) {
        boolean same = newStored == null ? stored == null : newStored.equals(stored);
        if (!same) {
            undoValue = null;
            undoRow = null;
        }
        stored = newStored;
    }
}
