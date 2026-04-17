//============================================================================
// hal.cc: startup code/entry point for HAL
//============================================================================
// Documentation:
//
//	Abstract:
//		Boots the PIGS operating system, contains HalMain
//		actual main is in each platform specific platform.cc, since some
//		OS's (like Windows) don't call main, they enter elsewhere
//
//	History:
//		Created 01-11-95 01:17pm Kevin T. Seghetti
//
//============================================================================
// dependencies

#define _PIGS_C

#include <hal/hal.h>
#include <hal/_platfor.h>
#if defined(WF_ENABLE_STEAM)
#  include <hal/linux/steam.h>
#endif
#include <hal/linux/audio.h>
#include <hal/_input.h>
#include <hal/sjoystic.h>
#include <hal/diskfile.hp>

//============================================================================

static void PIGSInitStartupTask();

LMalloc* _HALLmalloc;
LMalloc* _HALScratchLmalloc;
DMalloc* _HALDmalloc;
int32 cbHalLmalloc = 3500000;
int32 cbHalScratchLmalloc = 180000;

//============================================================================
// main HAL entry point, starts up PIGS system, including tasker & timers
// pass in argc & argv so that PIGSMain will have them
// this portion of the startup code has the entire machine, the tasker is not
//	running yet
//----------------------------------------------------------------------------

void
HALStart(int argc, char** argv, int maxTasks,int maxMessages, int maxPorts)
{
//	printf("HAL Argv Dump: argc = %d\n",argc);
//	for(int argvIndex=0;argvIndex < argc; argvIndex++)
//		printf("  %d: <%s>\n",argvIndex,argv[argvIndex]);

//#if !FINAL_RELEASE
//	for ( int idxArg=0; idxArg<argc; ++idxArg )
//	{
//		//printf( "argv[%d] = %s\n", idxArg, argv[idxArg] );
//		if ( strcmp( argv[ idxArg ], "-nocd" ) == 0 )
//			bInitCd = false;
//	}
//#endif

	_PlatformSpecificInit( argc, argv, maxTasks, maxMessages,  maxPorts );
	assert(ValidPtr(_HALLmalloc));
	{
		LMalloc __scratchLMalloc(*_HALLmalloc,cbHalScratchLmalloc MEMORY_NAMED( COMMA "HalScratchLMalloc" ) );
		_HALScratchLmalloc = &__scratchLMalloc;
		assert(ValidPtr(_HALScratchLmalloc));
		HalInitFileSubsystem();
		_InitJoystickInterface();					// setup joystick code
#if defined(WF_ENABLE_STEAM)
		_InitSteam();
#endif
		_InitAudio();
		PIGSMain( __argc, __argv );

		_TermAudio();
		_TermJoystickInterface();
#if defined(WF_ENABLE_STEAM)
		_TermSteam();
#endif
	}
	_PlatformSpecificUnInit();
}

//----------------------------------------------------------------------------
// this portion of the startup code runs as a task

void
PIGSInitStartupTask()
{
	PIGSMain( __argc,__argv );				// call game code, when returns, game is over
	PIGSExit();
}

//============================================================================
// shut down multi-tasker and call exit

void
PIGSExit()
{
#if DO_TEST_CODE
	printf("Tasker shutting down\n");
#endif
}

//============================================================================

bool
PIGSUserAborted()				// returns true if user has aborted game
{
	return(_JoystickUserAbort());
}

//============================================================================

#if DO_DEBUGGING_INFO
void
breakpoint()
	{
	}
extern "C" { extern int bDebugger; }							// kts used to enable int3 in assert
#endif

//==============================================================================

