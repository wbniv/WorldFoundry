//==============================================================================
// platform_main.cc — web (Emscripten) executable entry point for wf_game.
//
// Mirrors hal/linux/platform_main.cc: only main() lives here; the
// engine-needed helpers (FatalError, _PlatformSpecificInit, ParseWindowSwitches,
// _halWindow* globals) come from hal/linux/platform_init.cc, which the web
// build reuses verbatim (see the Emscripten extra-sources block in
// CMakeLists.txt and docs/plans/2026-06-11-web-canvas-port.md D2/P1.5).
//
// argv arrives from the page via Module.arguments (e.g. ['-L',
// '/moon_site01.iff']). v1 runs the engine's blocking main loop under
// ASYNCIFY — StepFrame yields to the browser once per frame; v2 replaces
// this with emscripten_set_main_loop (plan Phase 7).
//==============================================================================

#include <hal/hal.h>
#include <hal/_platfor.h>
#include <emscripten.h>
#include <cassert>
#include <cstring>

extern char szAppName[];
extern void ParseWindowSwitches(int, char**);

int
main(int argc, char* argv[])
{
	sys_init(&argc, &argv);

	assert(argv[0]);
	strcpy(argv[0], szAppName);
#if DEBUG
	strlwr(szAppName);
#endif

	ParseWindowSwitches(argc, argv);

	// Persistent saves (hi-scores): mount IDBFS at /save and kick an async
	// populate from IndexedDB. v1 blocked here under ASYNCIFY until the populate
	// finished; v2 dropped ASYNCIFY (plan Phase 7), so we no longer block — the
	// syncfs(true) runs in the background and typically completes well before a
	// demo level reads hi-scores. Writes still persist (syncfs(false) on save);
	// only a hi-score *read* in the first ~tens of ms of a cold page-load could
	// miss prior data. (A future tightening could mount in the shell at page
	// load, before the click-to-start, so it's always populated by boot.)
	EM_ASM(
		try {
			try { FS.mkdir('/save'); } catch (e) {}
			FS.mount(IDBFS, {}, '/save');
			FS.syncfs(true, function (err) {
				if (err) console.error('save mount syncfs:', err);
			});
		} catch (e) {
			// No IndexedDB (e.g. headless node, private-mode quirks) — run
			// without persistent saves rather than failing the boot.
			console.error('IDBFS unavailable, saves disabled:', e);
		}
	);

	HALStart(argc, argv, HAL_MAX_TASKS, HAL_MAX_MESSAGES, HAL_MAX_PORTS);
	return 0;
}
