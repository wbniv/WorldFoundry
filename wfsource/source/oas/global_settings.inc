@*============================================================================
@* global_settings.inc: the settings every level offers, declared once
@*============================================================================
@*
@* Every settings holder (a type that includes settings.inc) ends with
@*	@include global_settings.inc
@* just before TYPEFOOTER, so each *Settings type (and the minimal LevelSettings
@* holder a level without its own places) carries these fields LAST. A new
@* global setting is two edits: one line here, and one row in the engine's table,
@* wfsource/source/game/global_settings.cc, that says what the field does.
@* tests/test_global_level_settings.py fails if a holder forgets the include.
@* docs/plans/2026-11-22-global-level-settings.md.
@*
@* The sheet is last, so adding a line never moves a field a level already uses:
@* a level built earlier keeps working and simply lacks the new field until it is
@* rebuilt. The phone capability assets are regenerated with the level
@* (scripts/gen-settings-capabilities.py).
@*
@* Help strings must not contain commas: prep splits macro arguments on them.
@*============================================================================

	PROPERTY_SHEET_HEADER(Display,0)
@*	--------------------------------
	TYPEENTRYBOOLEAN(Show framerate,,0,SHOW_AS_CHECKBOX|SHOW_AS_LIVE,"Show the frames per second overlay")
	PROPERTY_SHEET_FOOTER
