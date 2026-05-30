//==============================================================================
// main.cc:
// Copyright (c) 1994,1995,1996,1997,1999,2000,2001,2002,2003 World Foundry Group  
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
// Description: The main entry point of game engine
// Original Author: Ann Mei Chang
//==============================================================================

#define _MAIN_CC

#include <pigsys/pigsys.hp>
#include "game.hp"
#include "version.hp"
#include <hal/lifecycle.h>
#include <gfx/display.hp>
#include <gfx/vmem.hp>

#if defined(__LINUX__) || defined(__ANDROID__)
	char szOadDir[ _MAX_PATH ];
#endif


#include "level.hp"
#include <cstdlib>


#include <pigsys/pigsys.hp>
#include <cpplib/libstrm.hp>

#include "gamestrm.hp"

//==============================================================================

int  gDebugPort = 7777;                 // default-on; --debug-port N overrides, --debug-port 0 disables
char gDebugBind[256] = "127.0.0.1";    // bind address; set by --debug-bind ADDR
int  gFrameStepSmokeCount = 0;          // >0 = run --frame-step-smoke=N path
bool gWfmutSmoke          = false;      // true = run --wfmut-smoke path
bool gWfmutThreadTest     = false;      // true = run --wfmut-thread-test (X5 death-test)
int  gFrameStepCycles = 1;              // --cycles=N: how many Load/Unload cycles to run
// Always defined: rooms.cc/level.cc reference it unconditionally as a runtime
// guard. Only ever set true under --editor, which is itself WF_ENABLE_EDITOR-gated,
// so in the game build it stays false (guards behave exactly as before the editor work).
bool gEditorMode = false;               // --editor: wf-edit drives the engine via RunEditor
#if DO_TEST_CODE
int  gDebugPrintActors = 0;             // 1 = print idx/mesh/mobility/pos per actor at construction (debug builds only)
#endif

// theGame global removed 2026-05-18 (Phase 0b WFGame de-globaling). WFGame
// is now instantiated in PIGSMain (see below) and passed by reference to Level;
// other engine code that needs WFGame state goes through Level's parent ref.
//
// gSoundEnabled / gCDEnabled also removed 2026-05-18 — write-only globals
// (set by -sound / -cd CLI flags, never read anywhere). The corresponding
// CLI flag handlers below were also dropped. Audio is governed by gMusicPlayer
// (audio/linux/music.cc) and gSoundDevice (audio/linux/device.cc) instead.

#if defined(DESIGNER_CHEATS)
bool bRecordVideo = false;
int  wf_hud_score = 0;
int  wf_hud_timer = 0;
int  wf_hud_lives = 0;
int  wf_hud_game_over = 0;
int  wf_hud_entering_initials = 0;
char wf_hud_initials[4] = {'A','A','A','\0'};
int  wf_hud_initials_pos = 0;
#endif

bool bPerspectiveCorrection = false;
bool bRenderZs = false;
bool bRenderZb = !bRenderZs;

bool bLinearMalloc = false;

#if defined(DO_PROFILE)
bool bProfileMemLoad = false;
bool bProfileMainLoop = true;
#endif
bool printFrameRate = false;

// Fake value for simulating a constant framerate (for debugging only!)
Scalar FakeFrameRate = SCALAR_CONSTANT(0);				// can't use this in global space ->Scalar::zero;

bool bUsePrepreparedModels = true;	// -Tpsx should change this
bool bShowWindow = true;

#if defined(JOYSTICK_RECORDER)
#pragma message("INCLUDING JOYSTICK RECORDER CODE")
bool bJoyPlayback = false;		// Set true to enable joystick playback
std::ifstream* joystickInputFile;	// istream for joystick data
#endif


const char szRate[] = "rate";

#if SW_DBSTREAM > 0

void
usage( int argc, char* argv[] )
{
   (void) argc;
   (void) argv;
	std::cout << "Usage : " << __GAME__ << " {switches} <level #>" << std::endl;
	std::cout << "Switches:" << std::endl;
	std::cout << "\t-p<stream initial><stream output>, where:" << std::endl;
	std::cout << "\t\t<stream initial> can be any of:" << std::endl;
	std::cout << "\t\t\tw=warnings (defaults to standard err)" << std::endl;
	std::cout << "\t\t\te=errors (defaults to standard err)" << std::endl;
	std::cout << "\t\t\tf=fatal (defaults to standard err)" << std::endl;
	std::cout << "\t\t\ts=statistics (defaults to null)" << std::endl;
	std::cout << "\t\t\tp=progress (defaults to null)" << std::endl;
	std::cout << "\t\t\td=debugging  (defaults to null)" << std::endl;
	std::cout << "\t\t<stream output> can be any of:" << std::endl;
	std::cout << "\t\t\tn=null, no output is produced" << std::endl;
	std::cout << "\t\t\ts=standard out" << std::endl;
	std::cout << "\t\t\te=standard err" << std::endl;
	std::cout << "\t\t\tm#=monochrome dispay, # = which window" << std::endl;
	std::cout << "\t\t\tf<filename>=output to filename" << std::endl;
	std::cout << "\t-s<stream initial><stream output>, where:" << std::endl;
	std::cout << "\t\t<stream initial> can be any of:" << std::endl;

#define STREAMENTRY(stream,where,initial,helptext) std::cout << "\t\t\t" << initial << "=" << helptext << std::endl;
#define EXTERNSTREAMENTRY(stream,where,initial,helptext) std::cout << "\t\t\t" << initial << "=" << helptext << std::endl;
#include "gamestrm.inc"
#undef STREAMENTRY
#undef EXTERNSTREAMENTRY

	std::cout << "\t\t<stream output> (same as above)" << std::endl;

	std::cout << "\t-l<stream initial><stream output>, where:" << std::endl;
	std::cout << "\t\t<stream initial> can be any of:" << std::endl;
#define STREAMENTRY(stream,where,initial,helptext) std::cout << "\t\t\t" << initial << "=" << helptext << std::endl;
#include <libstrm.inc>
#undef STREAMENTRY
	std::cout << "\t\t<stream output> (same as above)" << std::endl;

    std::cout << "\t-paranoid\tPerform insanely slow error checks" << std::endl;
    std::cout << "\t-record_video\tRecord gameplay to output.mp4 via ffmpeg" << std::endl;
    std::cout << "\t--vram-width N\t\tTotal VRAM box width  (default " << Display::VRAMWidth  << ")" << std::endl;
    std::cout << "\t--vram-height N\t\tTotal VRAM box height (default " << Display::VRAMHeight << ")" << std::endl;
    std::cout << "\t--vram-slot-width N\tTransient texture slot width  (default " << VideoMemory::VRAMTransientWidth  << ")" << std::endl;
    std::cout << "\t--vram-slot-height N\tTransient texture slot height (default " << VideoMemory::VRAMTransientHeight << ")" << std::endl;
    std::cout << "\t-zs\t\tZ-Sorted" << std::endl;
    std::cout << "\t-zb\t\tZ-Buffered" << std::endl;
	std::cout << "\t-nologo\t\tDon't display company logos" << std::endl;
//			std::cout << "\t-framerate\tPrint framerate" << std::endl;
	std::cout << "\t-" << szRate << "N\t\tSimulate a frame rate of N Hz" << std::endl;
	std::cout << "\t-profmemload\tProfile memory usage during load" << std::endl;
	std::cout << "\t-profmainloop\tProfile cpu usage during main game loop" << std::endl;
	std::cout << "\t-lmalloc\tUse linear malloc() instead of C runtime malloc()" << std::endl;
	std::cout << "\t-sound\t\tEnable Sound" << std::endl;
	std::cout << "\t-cd\t\tenable CD" << std::endl;
#if defined(JOYSTICK_RECORDER)
	std::cout << "\t-joy<filename>\tPlay back joystick input from <filename>" << std::endl;
#endif
#if DO_DEBUGGING_INFO
	std::cout << "\t-breaktime<time>\tcause debugger break at time <time>" << std::endl;
#endif
	DBSTREAM1( std::cout << "CALLING PIGSExit()" << std::endl; )
	PIGSExit();
}

#endif

//==============================================================================
// command line parsing
// returns index of first argv which doesn't contain a '-' switch

int
ParseCommandLine(int argc, char** argv)
{
	int index;
	for( index=1; index < argc && argv[index] && ((*argv[index] == '-') || (*argv[index] == '/')); index++)
	{
#if 0
#endif

		DBSTREAM1( std::cout << argv[index] << std::endl; )

		if ( 0 )
			;
		else if ( argv[index][1] == 'L' && argv[index][2] != 0 )
		{
			extern const char* gLevelOverridePath;
			gLevelOverridePath = argv[index] + 2;
			DBSTREAM1( cprogress << "Level override path: " << gLevelOverridePath << std::endl; )
		}
		else if ( strncmp( argv[index]+1, "-debug-port", 11 ) == 0 && argv[index+1] )
		{
			gDebugPort = atoi( argv[index+1] );
			++index;
			DBSTREAM1( cprogress << "Debug bridge port: " << gDebugPort << std::endl; )
		}
		else if ( strncmp( argv[index]+1, "-debug-bind", 11 ) == 0 && argv[index+1] )
		{
			strncpy( gDebugBind, argv[index+1], sizeof(gDebugBind) - 1 );
			gDebugBind[sizeof(gDebugBind)-1] = '\0';
			++index;
			DBSTREAM1( cprogress << "Debug bridge bind: " << gDebugBind << std::endl; )
		}
		else if ( strncmp( argv[index]+1, "-frame-step-smoke=", 18 ) == 0 )
		{
			gFrameStepSmokeCount = atoi( argv[index] + 1 + 18 );
			DBSTREAM1( cprogress << "Frame-step API smoke: " << gFrameStepSmokeCount << " frames" << std::endl; )
		}
		else if ( strcmp( argv[index]+1, "-wfmut-smoke" ) == 0 )
		{
			gWfmutSmoke = true;
			DBSTREAM1( cprogress << "wfmut smoke enabled" << std::endl; )
		}
		else if ( strcmp( argv[index]+1, "-wfmut-thread-test" ) == 0 )
		{
			gWfmutThreadTest = true;
			DBSTREAM1( cprogress << "wfmut cross-thread death-test enabled" << std::endl; )
		}
		else if ( strncmp( argv[index]+1, "-cycles=", 8 ) == 0 )
		{
			gFrameStepCycles = atoi( argv[index] + 1 + 8 );
			AssertMsg(gFrameStepCycles >= 1, "--cycles=N requires N>=1");
			DBSTREAM1( cprogress << "Frame-step API cycles: " << gFrameStepCycles << std::endl; )
		}
#if defined(WF_ENABLE_EDITOR)
		else if ( strcmp( argv[index]+1, "-editor" ) == 0 )
		{
			gEditorMode = true;
			DBSTREAM1( cprogress << "Editor mode (wf-edit drives RunEditor)" << std::endl; )
		}
#endif
#if DO_TEST_CODE
		else if ( strcmp( argv[index]+1, "-debug-print-actors" ) == 0 )
		{
			gDebugPrintActors = 1;
			DBSTREAM1( cprogress << "Debug print actors enabled" << std::endl; )
		}
#endif
		else if ( strncmp( argv[index]+1, (char*)szRate, strlen( szRate ) ) == 0)
		{
		    int value = atoi( argv[index] + strlen( szRate ) + 1 );
          FakeFrameRate = Scalar::one / Scalar(value,0);
			FakeFrameRate = SCALAR_CONSTANT(0.05);
			DBSTREAM1( cerror << "Fake clock delta = " << FakeFrameRate << std::endl; )
		}
#if defined(DESIGNER_CHEATS)
        else if ( strcmp( argv[index]+1, "record_video" ) == 0 )
            bRecordVideo = true;
#endif
        // Runtime VRAM overrides — must be applied before Display/VideoMemory
        // is constructed below. See
        // docs/plans/2026-05-30-runtime-vram-cli-overrides.md.
        else if ( strncmp( argv[index]+1, "-vram-width=", 12 ) == 0 )
            Display::VRAMWidth  = atoi( argv[index] + 13 );
        else if ( strncmp( argv[index]+1, "-vram-height=", 13 ) == 0 )
            Display::VRAMHeight = atoi( argv[index] + 14 );
        else if ( strncmp( argv[index]+1, "-vram-slot-width=", 17 ) == 0 )
            VideoMemory::VRAMTransientWidth  = atoi( argv[index] + 18 );
        else if ( strncmp( argv[index]+1, "-vram-slot-height=", 18 ) == 0 )
            VideoMemory::VRAMTransientHeight = atoi( argv[index] + 19 );
		else if ( strcmp( argv[index]+1, "zb" ) == 0 )
		{
			bRenderZb = true;
			bRenderZs = false;
		}
		else if ( strcmp( argv[index]+1, "zs" ) == 0 )
		{
			bRenderZs = true;
			bRenderZb = false;
		}
#if defined(JOYSTICK_RECORDER)
		else if ( memcmp( argv[index]+1, "joy", 3 ) == 0 )
		{
			AssertMsg( strlen(argv[index]+1) > 3, "The -joy option requires a filename" );
			bJoyPlayback = true;
			joystickInputFile = new (HALLmalloc) std::ifstream(argv[index]+4);
			AssertMsg( joystickInputFile->good(), "Unable to open file <" << argv[index]+4 << "> for joystick input" );
		}
#endif
#if defined(DO_PROFILE)
		else if ( strcmp( argv[index]+1, "profmemload" ) == 0 )
			bProfileMemLoad = true;
		else if ( strcmp( argv[index]+1, "profmainloop" ) == 0 )
			bProfileMainLoop = true;
#endif
#if DO_DEBUGGING_INFO
		else if ( memcmp( argv[index]+1, "breaktime=", 10 ) == 0 )
		{
			AssertMsg( strlen(argv[index]+1) > 10, "The -breaktime= option requires a time" );
			extern Scalar WALL_CLOCK_BREAKPOINT_VALUE;
#if defined(SCALAR_TYPE_FIXED)
         int32 value = atoi( argv[index] + 1 + 10 );
        WALL_CLOCK_BREAKPOINT_VALUE = Scalar::FromFixed32(value);
#elif defined(SCALAR_TYPE_FLOAT) || defined(SCALAR_TYPE_DOUBLE)
         double value;
         sscanf(argv[index] + 1 + 10, "%lf",&value);
         WALL_CLOCK_BREAKPOINT_VALUE = Scalar::FromDouble(value);
#else
#error SCALAR TYPE not defined
#endif

		}
#endif
#if DEBUG > 0
        else if ( strcmp( argv[index]+1, "lmalloc" ) == 0 )
            bLinearMalloc = true;
        // -sound and -cd CLI flags removed 2026-05-18 — they set gSoundEnabled
        // / gCDEnabled which had no readers. Use the audio-specific globals in
        // audio/linux/{music,device}.cc to control audio behaviour instead.
#endif
#if SW_DBSTREAM > 0
		else if ( tolower( *( argv[index]+1 ) ) == 'p' )
			RedirectStandardStream(argv[index]+2);
		else if ( tolower( *( argv[index]+1 ) ) == 's' )
			RedirectGameStream(argv[index]+2);
		else if ( tolower( *( argv[index]+1 ) ) == 'l' )
			RedirectLibraryStream(argv[index]+2);
#endif

// kts: printframerate should be removed from release
#if defined(DESIGNER_CHEATS)
		else if ( tolower( *( argv[index]+1 ) ) == 'f' )
		{
			  printFrameRate = true;
			  DBSTREAM1( std::cout << "PrintFrameRate on" << std::endl; )
	 	}
#endif
#if SW_DBSTREAM > 0
		else if ( *( argv[index]+1 ) == 'h' )
	  	{
			usage( argc, argv );
         sys_exit(1);
  		}
#endif		// SW_DBSTREAM > 0
#if DO_ASSERTIONS
		else
			DBSTREAM1( cerror << "game Error: Unrecognized command line switch \"" <<
				*(argv[index]+1) << "\"" << std::endl );
#endif
	 }

	return(index);
	}






void
PIGSMain( int argc, char* * argv )
{

//	ERR_SET_LOG(3);

	AssertMsg( true & 1, "True must have low bit set [required for bitfield memory optimization]" );


	DBSTREAM1( std::cout << __GAME__ << " v" << (char*)szVersion; )

	DBSTREAM1( std::cout << ", Built:" << (char*)szDate << "," << (char*)szTime << " by " << szBuildUser << std::endl; )
	int commandIndex = ParseCommandLine(argc,argv);


#if defined(JOYSTICK_RECORDER)
	// check for conflicting time-related options
	if (FakeFrameRate != Scalar::zero)
		AssertMsg( !bJoyPlayback, "-joy and -rate options can't be used at the same time." );
	if(bJoyPlayback)
		printf("Playing back joystick file\n");
#endif

#pragma message ("kts: should not read level from command line (leave until profiling is done!)")
	int nStartingLevel = -1;
	if (argc-commandIndex > 0)
		nStartingLevel = atoi( argv[ commandIndex ] );
	DBSTREAM1( std::cout << "argc = " << argc << ", commandIndex = " << commandIndex << std::endl; )
	DBSTREAM1( cver << "Level=" << nStartingLevel << std::endl; )

#if 0
#endif

#pragma message( "System streams should be in HAL [framework]" )
#if SW_DBSTREAM > 0
	cerror << "cerror:" << std::endl;
	cwarn << "cwarn:" << std::endl;
	cstats << "cstats:" << std::endl;
	cprogress << "cprogress:" << std::endl;
	cdebug << "cdebug:" << std::endl;

	cflow << "cflow:" << std::endl;
	cmovement << "cmovement:" << std::endl;
	cactor << "cactor:" << std::endl;
	clevel << "clevel:" << std::endl;
	ctool << "ctool:" << std::endl;
	ccamera << "ccamera:" << std::endl;
	cmem << "cmem:" << std::endl;
#endif
#if SW_DBSTREAM > 0
	DBSTREAM1( cver << __GAME__ " Ver " << (char*)szVersion << ", Built:" << (char*)szDate << "," << (char*)szTime << " by " << szBuildUser << std::endl; )
	DBSTREAM1( cver << "DBSTREAMS "; )
#	ifdef DO_PROFILE
	cver << "PROFILE ";
#	endif
#endif

	DBSTREAM1( cprogress << "main::constructing the game" << std::endl; )
   WFGame* game = new (HALLmalloc) WFGame( nStartingLevel );
	assert( ValidPtr( game ) );

	int wfmutFailures = 0;
	if (gFrameStepSmokeCount > 0)
	{
		DBSTREAM1( cprogress << "main::frame-step API smoke (" << gFrameStepSmokeCount
		                     << " frames × " << gFrameStepCycles << " cycles)" << std::endl; )
		game->SmokeRunFrameStep( gFrameStepSmokeCount, gFrameStepCycles );
	}
#if defined(WF_DEBUG_BRIDGE) || defined(WF_ENABLE_EDITOR)
	else if (gWfmutSmoke)
	{
		DBSTREAM1( cprogress << "main::wfmut smoke" << std::endl; )
		wfmutFailures = game->RunWfmutSmoke( );
	}
	else if (gWfmutThreadTest)
	{
		DBSTREAM1( cprogress << "main::wfmut cross-thread death-test" << std::endl; )
		game->RunWfmutThreadTest( );   // expected to abort inside the guard
	}
#endif
#if defined(WF_ENABLE_EDITOR)
	else if (gEditorMode)
	{
		DBSTREAM1( cprogress << "main::editor mode (RunEditor)" << std::endl; )
		game->RunEditor( );
	}
#endif
	else
	{
		if (gWfmutSmoke)
		{
			std::fprintf(stderr,
			    "wf_game: --wfmut-smoke requires WF_DEBUG_BRIDGE or WF_ENABLE_EDITOR build\n");
			std::_Exit(2);
		}
		DBSTREAM1( cprogress << "main::running game script" << std::endl; )
		game->RunGameScript( );
	}

	DBSTREAM1( cprogress << "Game over: shutting down the game" << std::endl; )

	// WFGame destruction needs the GL context + X window alive — Display's
	// destructor calls into mesa's window-close path (XSetInputFocus, etc.)
	// which segfaults if HALCloseWindow ran first. Tear down WFGame, then
	// close the window.
	MEMORY_DELETE(HALLmalloc,game,WFGame);

	HALCloseWindow();

#if defined(JOYSTICK_RECORDER)
	if (bJoyPlayback)
		MEMORY_DELETE( HALLmalloc, joystickInputFile, ifstream );
#endif

	DBSTREAM1( cprogress << "Calling PIGSExit()" << std::endl; )
	if (gWfmutSmoke && wfmutFailures != 0)
	{
		// Smoke wants a non-zero exit code so CI / scripts can detect failure.
		// Skip PIGSExit's normal cleanup-and-return path; std::_Exit avoids
		// running global destructors that the engine isn't designed to tolerate
		// after HALCloseWindow.
		std::_Exit(wfmutFailures);
	}
	PIGSExit();
}

//==============================================================================
