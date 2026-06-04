//==============================================================================
// platform.cc: windows95 specific startup code
// Copyright ( c ) 1997,98,99 World Foundry Group.  
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//==============================================================================
// This program is free software; you can redistribute it and/or
// modify it under the terms of the GNU General Public License
// Version 2 as published by the Free Software Foundation
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program; if not, write to the Free Software
// Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
// or see www.fsf.org

//==============================================================================
// Original Author: Kevin T. Seghetti
//	History:
//			Created 03-07-95 11:45am Kevin T. Seghetti
//=============================================================================
// dependencies

#define _PLATFORM_C

//=============================================================================

// PATH_MAX (used by szAppName below): POSIX puts it in <limits.h> — on macOS
// that pulls it in via <sys/syslimits.h>. On Linux glibc it also arrives
// transitively through <hal/hal.h>, which is why this was historically left
// commented out; but Apple Clang's transitive path doesn't define it, so the
// macOS desktop build needs the explicit include. The fallback covers any
// toolchain that still omits it (some embedded libcs do).
#include <limits.h>
#ifndef PATH_MAX
#define PATH_MAX 4096
#endif

#include <hal/hal.h>			// includes everything
#include <hal/_platfor.h>
#include <hal/_input.h>
#include <hal/sjoystic.h>
#include <hal/salloc.hp>
#include <hal/asset_accessor.hp>
#include <signal.h>
#include <X11/Xlib.h>   // XOpenDisplay/DisplayWidth/Height for -fullscreen screen-size query

// On macOS desktop (.app bundle) use NSBundle to resolve bundled resources;
// on Linux use the POSIX cwd-relative accessor.
#if defined(WF_TARGET_MACOS)
extern "C" AssetAccessor* HALCreateNSBundleAccessor();  // hal/macos/asset_accessor_nsbundle.mm
#else
extern AssetAccessor* HALCreatePosixAssetAccessor();    // asset_accessor_posix.cc
#endif
extern bool bPrintVersion;

//=============================================================================

extern bool bShowWindow;

bool bFullScreen = true;

//=============================================================================

/*static*/ void PIGSInitStartupTask();

SAlloc* stacks;

// main() lives in hal/linux/platform_main.cc (split out 2026-05-18 for editor
// Phase 0b). This file holds engine-needed helpers (_PlatformSpecificInit,
// FatalError, FPEHandler, ParseWindowSwitches) + platform globals shared with
// the engine library; the shell file holds only main, so hosts (editor /
// host-GL e2e test) can link libwfengine.a and supply their own main.

//=============================================================================

int		nMainCmdShow;
char	szAppName[ PATH_MAX ];
int		_halWindowWidth;
int		_halWindowHeight;
int		_halWindowXPos;
int		_halWindowYPos;

#define HALMEM	   	"-halmem="
#define SCRATCHMEM	"-scratchmem="
#define PSXMEM		"-psxmem"


void
ParseWindowSwitches( int __argc, char* __argv[] )
{ // Determine screen/window dimensions
	for ( int i=1; i<__argc; ++i )
	{
		const char szWidth[] = "-width=";
		const char szHeight[] = "-height=";
		const char szXPos[] = "-xpos=";
		const char szYPos[] = "-ypos=";
		const char szWindow[] = "-window";
		const char szFullScreen[] = "-fullscreen";

		if ( 0 )
			;
		else if ( strcmp( __argv[ i ], szWindow ) == 0 )
			bFullScreen = false;
		else if ( strcmp( __argv[ i ], szFullScreen ) == 0 )
		{
			bFullScreen = true;
			// Query actual screen dimensions so the FBO (and recording) match.
			// Only overrides size if -width/-height were not already given.
			if ( _halWindowWidth == 0 )
			{
				::Display* xd = XOpenDisplay(NULL);
				if (xd)
				{
					int s = DefaultScreen(xd);
					_halWindowWidth  = DisplayWidth(xd, s);
					_halWindowHeight = DisplayHeight(xd, s);
					XCloseDisplay(xd);
				}
			}
		}
		else if ( strncmp( __argv[i], szXPos, strlen( szXPos ) ) == 0 )
			_halWindowXPos = atoi( __argv[i] + strlen( szXPos ) );
		else if ( strncmp( __argv[i], szYPos, strlen( szYPos ) ) == 0 )
			_halWindowYPos = atoi( __argv[i] + strlen( szYPos ) );
		else if ( strncmp( __argv[i], szWidth, strlen( szWidth ) ) == 0 )
			_halWindowWidth = atoi( __argv[i] + strlen( szWidth ) );
		else if ( strncmp( __argv[i], szHeight, strlen( szHeight ) ) == 0 )
			_halWindowHeight = atoi( __argv[i] + strlen( szHeight ) );
#if defined( DESIGNER_CHEATS )
		else if ( strncmp( __argv[i], HALMEM, strlen( HALMEM ) ) == 0 )
			cbHalLmalloc = atoi( __argv[i] + strlen( HALMEM ) );
		else if ( strncmp( __argv[i], SCRATCHMEM, strlen( SCRATCHMEM ) ) == 0 )
			cbHalScratchLmalloc = atoi( __argv[i] + strlen( SCRATCHMEM ) );
		else if ( strncmp( __argv[i], PSXMEM, strlen( PSXMEM ) ) == 0 )
		{
			cbHalLmalloc = 1585296;
		}
#endif
	}

	if ( _halWindowHeight )
	{
		if ( _halWindowWidth == 0 )
		{	// Specified the height. Choose width accordingly
			switch ( _halWindowHeight )
			{
				case 200:
				case 240:
					_halWindowWidth = 320;
					break;
				case 384:
					_halWindowWidth = 512;
					break;
				case 400:
				case 480:
					_halWindowWidth = 640;
					break;
				case 600:
					_halWindowWidth = 800;
					break;
				case 768:
					_halWindowWidth = 1024;
					break;
				case 864:
					_halWindowWidth = 1152;
					break;
				case 1024:
					_halWindowWidth = 1200;
					break;
				case 1200:
					_halWindowWidth = 1600;
					break;
				default:
					printf( "Unknown height of %d\n", _halWindowHeight );
			}
		}
	}

	if ( _halWindowWidth == 0 )
	{
		_halWindowWidth = 640;
		_halWindowHeight = 480;
	}

}


// main() moved to platform_main.cc; see file header for rationale.

//=============================================================================

void* halMemory;

#if 0
void FPEHandler __PMT((int sig, siginfo_t *siginfo, void *undefined))
#else
void FPEHandler (int sig)
#endif
{
    // kts figure out how to return max int
    printf("FPEHandler, I got a signal %d\n",sig);
    printf("This should not have happened, the divide code in math/linux/scalar.hpi is supposed to prevent it!\n");
#if 0
    printf("siginfo = %p\n",siginfo);
    printf("undefined = %p\n",undefined);

    if(siginfo)
    {
        printf("si_signo = %d\n", siginfo->si_signo);
        printf("si_errno = %d\n", siginfo->si_errno);
        printf("si_code = %d\n", siginfo->si_code);
        printf("si_addr = %p\n", siginfo->si_addr);
    }
    printf("Someone figure out how to set ax to maxint and proceed\n");
#endif
// kts: don't run normal shutdown from an interrupt, just bail
#undef exit
    exit(5);
}

//==============================================================================

void
_PlatformSpecificInit(int /*argc*/, char** /*argv*/, int /*maxTasks*/,int /*maxMessages*/, int /*maxPorts*/)
{
    // install div 0/int overflow handler
#if 0
    struct sigaction act;
    act.sa_sigaction = FPEHandler;
    sigemptyset(&act.sa_mask);
    act.sa_flags = SA_SIGINFO;
    sigaction(SIGFPE,&act, 0); 
#else
    struct sigaction act;
    act.sa_handler = FPEHandler;
    sigemptyset(&act.sa_mask);
    act.sa_flags = 0;
    sigaction(SIGFPE,&act, 0); 
#endif

//	halMemory = malloc(HALLMALLOC_SIZE);
	halMemory = malloc( cbHalLmalloc );
	ValidatePtr(halMemory);
	_HALLmalloc = new LMalloc(halMemory, cbHalLmalloc MEMORY_NAMED( COMMA "HalLMalloc" )	);
	assert(ValidPtr(_HALLmalloc));

	_HALDmalloc = new (*_HALLmalloc)DMalloc( *_HALLmalloc, HAL_DMALLOC_SIZE MEMORY_NAMED( COMMA "HALDmalloc"));
	ValidatePtr(_HALDmalloc);

#if defined(WF_TARGET_MACOS)
	HALSetAssetAccessor(HALCreateNSBundleAccessor());
#else
	HALSetAssetAccessor(HALCreatePosixAssetAccessor());
#endif
}

//=============================================================================

void
_PlatformSpecificUnInit(void)
{
	if (stacks) { delete stacks; stacks = NULL; }
	MEMORY_DELETE((*_HALLmalloc),_HALDmalloc,DMalloc);
	delete _HALLmalloc;
	free(halMemory);
}

//=============================================================================

void
FatalError( const char* string )
{
	printf("Fatal Error: %s",string);
	exit(1);
}

//=============================================================================
