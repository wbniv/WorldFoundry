@*============================================================================
@* settings.inc: the base of every settings holder (a Settings is an Actor)
@*============================================================================
@*
@* A settings holder is a standard object type whose fields are level options
@* edited at runtime (docs/plans/2026-10-16-runtime-object-editing.md, M1).
@* It inherits Settings by including this file in place of actor.inc:
@*
@*	TYPEHEADER(Planted Tank Settings,PlantedTankSettings)
@*		@include settings.inc
@*		PROPERTY_SHEET_HEADER(...)
@*
@* This file is an include only. Never register a type named Settings in
@* objects.mac: runtime diagnostics use their own actor.
@*
@* The defaults below must come before actor.inc, because actor.inc and the
@* blocks it includes take each one only when it isn't defined yet. They make
@* a holder of values that never renders and never moves, like Target: no
@* mesh, no mass, invisible.
@*
@* Fields every settings holder comes to share go after actor.inc, in their
@* own property sheet. Adding one changes the struct of every settings type,
@* so do it only before a level that uses one is shipped.
@*============================================================================

@ifndef(DEFAULT_MASS)(@define DEFAULT_MASS 0)
@ifndef(DEFAULT_VISIBILITY)(@define DEFAULT_VISIBILITY 0)
@ifndef(DEFAULT_MODEL_TYPE)(@define DEFAULT_MODEL_TYPE 3)

	@include actor.inc

@*============================================================================
