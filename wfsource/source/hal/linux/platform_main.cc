//==============================================================================
// platform_main.cc — Linux executable entry point for wf_game.
//
// Split out of platform.cc 2026-05-18 (editor Phase 0b sub-task 3): everything
// the engine library needs from platform.cc (FatalError, _PlatformSpecificInit,
// FPEHandler, ParseWindowSwitches, _halWindow* globals) lives in
// platform_init.cc and compiles into libwfengine.a; this file holds only
// main() and stays in WF_PLATFORM_SHELL_SOURCES, so hosts (the upcoming
// collaborative editor, the host-GL e2e test) can link wfengine and supply
// their own main without colliding with wf_game's.
//==============================================================================

#include <hal/hal.h>
#include <hal/_platfor.h>
#include <cassert>
#include <cstring>

extern char szAppName[];
extern void ParseWindowSwitches(int, char**);
extern bool bPrintVersion;

int
main(int argc, char* argv[])
{
	sys_init(&argc, &argv);

	assert(argv[0]);
	strcpy(argv[0], szAppName);              // kts 4/10/99 8:52
#if DEBUG
	strlwr(szAppName);
#endif

	ParseWindowSwitches(argc, argv);
#if defined(DESIGNER_CHEATS)
	if (bPrintVersion)
		printf("cbHalLmalloc = %ld, cbHalScratchLmalloc = %ld\n",
		       cbHalLmalloc, cbHalScratchLmalloc);
#endif

	HALStart(argc, argv, HAL_MAX_TASKS, HAL_MAX_MESSAGES, HAL_MAX_PORTS);
	return 0;
}
