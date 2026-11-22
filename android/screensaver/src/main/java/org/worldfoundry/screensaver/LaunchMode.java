package org.worldfoundry.screensaver;

/**
 * What the TV launcher activity ({@link AquariumActivity}) does with the intent that started it.
 * Pure: no Android types, so the plain-Java LaunchModeTest covers every row.
 * docs/plans/2026-11-21-one-aquarium-app.md, "How the app tells the two modes apart".
 *
 * <ul>
 *   <li>{@code LEVEL} extra present (a catalogue id or {@code random}): {@link Kind#PLAY_LEVEL}, the
 *       one-run start of {@link LevelLaunch}; an id the catalogue does not hold is refused there
 *       (log, toast, finish, nothing saved), never replaced by the menu or the saved tank.</li>
 *   <li>{@code DREAM} extra present: {@link Kind#PLAY_SAVED}, the screensaver's content.</li>
 *   <li>Neither: a plain MAIN start by the launcher or a person, {@link Kind#MENU}.</li>
 * </ul>
 *
 * The Dream ({@link AquariumDreamService}) and {@link ScreensaverPreviewActivity} never consult this
 * class: they keep calling {@link LevelLaunch#startChosen}, so they cannot reach the menu.
 */
final class LaunchMode {
    enum Kind { MENU, PLAY_SAVED, PLAY_LEVEL }

    static final LaunchMode MENU = new LaunchMode(Kind.MENU, null);
    static final LaunchMode PLAY_SAVED = new LaunchMode(Kind.PLAY_SAVED, null);

    final Kind kind;
    /** The requested level for {@link Kind#PLAY_LEVEL} (not yet checked against the catalogue); else null. */
    final String level;

    private LaunchMode(Kind kind, String level) {
        this.kind = kind;
        this.level = level;
    }

    /**
     * @param level the {@code LEVEL} extra as text, or null when the intent has none. A value of
     *              another type arrives as its text, so it is refused as an unknown id rather than
     *              silently ignored.
     * @param dream whether the intent carries the {@code DREAM} extra, whatever its value.
     */
    static LaunchMode forLauncherActivity(String level, boolean dream) {
        if (level != null) return new LaunchMode(Kind.PLAY_LEVEL, level);
        if (dream) return PLAY_SAVED;
        return MENU;
    }

    @Override
    public String toString() {
        return kind == Kind.PLAY_LEVEL ? "PLAY_LEVEL(" + level + ")" : kind.name();
    }
}
