//==============================================================================
// hal/macos/platform_main.cc — macOS desktop executable entry point for wf_game.
//
// macOS desktop boots like Linux ("Linux-minus-X11"), NOT like iOS: a thin
// main() that calls HALStart() on the main thread — no UIApplicationMain, no
// engine pthread. The window itself is opened later, by Display (see
// hal/macos/display_macos.cc), when gWindowed is set.
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
#include <cstdio>
#include <cstring>

extern char szAppName[];
extern void ParseWindowSwitches(int, char**);
extern bool gWindowed;   // game/main.cc (--windowed)

// Finder and LaunchServices (`open wf_game.app`) start the bundle with no
// arguments; macOS before 10.9 appended one -psn_X_Y process-serial argument.
// Every CI and scripted run passes flags (-L, --frame-step-smoke, ...), so "no
// arguments" identifies a double-click launch without guessing at the parent.
static bool
LaunchedWithoutArguments(int argc, char* argv[])
{
	for (int i = 1; i < argc; ++i)
		if (strncmp(argv[i], "-psn_", 5) != 0)
			return false;
	return true;
}

int
main(int argc, char* argv[])
{
	// First thing: a terminate dumps the real cause instead of masking the assert.
	Sys_InstallTerminateHandler("wf_game");
	sys_init(&argc, &argv);

	assert(argv[0]);
	strcpy(argv[0], szAppName);

	// A double-clicked bundle must open a window. --windowed is opt-in for the
	// headless CI runs, but with no arguments nobody can pass it, and the
	// offscreen fallback would leave a process running with no window, no menu
	// and no way to quit it short of Force Quit.
	if (LaunchedWithoutArguments(argc, argv))
	{
		gWindowed = true;
		std::printf("macos: launched with no arguments (Finder / LaunchServices): windowed\n");
		std::fflush(stdout);
	}

	ParseWindowSwitches(argc, argv);

	HALStart(argc, argv, HAL_MAX_TASKS, HAL_MAX_MESSAGES, HAL_MAX_PORTS);
	return 0;
}
