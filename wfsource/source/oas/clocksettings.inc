@*============================================================================
@* clocksettings.inc: the Clock property sheet every clock's settings type shares
@*============================================================================
@*
@* Plan docs/plans/2026-11-21-tide-harbour-clock.md, D13 and Q9: every clock
@* level carries one settings object built the same way, and the fields all
@* clocks share live here, in their own sheet. A clock's settings type includes
@* this file after settings.inc, then adds its own sheet:
@*
@*	TYPEHEADER(Tide Harbour Settings,TideHarbourSettings)
@*		@include settings.inc
@*		@include clocksettings.inc
@*		PROPERTY_SHEET_HEADER(Tide Harbour,0)
@*
@* settings.inc itself is not touched: a field there would change the struct of
@* every settings type, clocks or not. A field added here changes every clock's
@* settings type, so append only, before a clock that uses it ships.
@*
@* Camera drift is the burn-in guard (Minute Machine's D10, Tide Harbour's D10):
@* Slow, the default, moves the camera a few degrees over ten minutes.
@*
@* Help strings must not contain commas: prep splits macro arguments on them.
@*============================================================================

	PROPERTY_SHEET_HEADER(Clock,1)
@*	------------------------------
	TYPEENTRYINT32(Camera drift,,0,1,0,"Slow|Off",SHOW_AS_RADIOBUTTONS|SHOW_AS_LIVE,"The camera drifts slowly so no pixel sits still on the screen; Off holds it still")
	PROPERTY_SHEET_FOOTER
