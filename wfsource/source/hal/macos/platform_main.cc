//==============================================================================
// hal/macos/platform_main.cc — macOS desktop executable entry point for wf_game.
//
// macOS desktop boots like Linux ("Linux-minus-X11"), NOT like iOS: a thin
// main() that calls HALStart() on the main thread — no UIApplicationMain, no
// engine pthread. The renderer is a true no-op for this bring-up, so there is
// no window to create here.
//
// Mirrors hal/linux/platform_main.cc. The engine-needed helpers
// (_PlatformSpecificInit, FatalError, ParseWindowSwitches, _halWindow*
// globals) are reused verbatim from hal/linux/platform_init.cc (portable POSIX,
// listed explicitly in the macOS arm of CMakeLists.txt); this file holds only
// main() and stays in WF_PLATFORM_SHELL_SOURCES so hosts can link wfengine and
// supply their own main.
//
// NB: the Linux shell's `#if DEBUG strlwr(szAppName)` is intentionally dropped.
// strlwr is a non-standard (DOS/Windows-era) extension WF reimplements in
// pigsys/linux/strlwr.cc; the lowercasing is cosmetic and unneeded headless.
//==============================================================================

#include <hal/hal.h>
#include <hal/_platfor.h>
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

	ParseWindowSwitches(argc, argv);

	HALStart(argc, argv, HAL_MAX_TASKS, HAL_MAX_MESSAGES, HAL_MAX_PORTS);
	return 0;
}
