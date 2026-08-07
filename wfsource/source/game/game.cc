//==============================================================================
// game.cc: 
// Copyright ( c ) 1994,1995,1996,1997,1998,1999,2001,2002,2003 World Foundry Group  
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

//=============================================================================
// Description: The WFGame class provides the application framework for the game.
//==============================================================================

// if defined, loads meta-script (and all levels) from cd.iff, otherwise, loads level1.iff
#define DO_CD_IFF

//#define DO_PROFILE

#include "level.hp"
#include "game.hp"
#include <hal/lifecycle.h>
#include <unistd.h>
#if defined(__EMSCRIPTEN__)
#  include <emscripten.h>
#endif
#include <audio/music.hp>
#include <audio/sfx_library.hp>
#include "rest_api.hp"
#include "debug_server.hp"
#include "editor_hook.h"
#include "wfmut_smoke.hpp"
#include "physics_jolt.hp"
#include "oas/matte.ht"
#include "gamestrm.hp"
#include "camera.hp"
#include "sim_constants.hp"   // kMaxSimDeltaSeconds
#include "oas/matte.ht"
#include "matte.hp"
#include "mailbox.hp"
#include <gfx/vmem.hp>
#include <asset/assets.hp>     // AssetManager::LookupTexture (Moon minimap ground-atlas accessor)
#include <streams/asset.hp>    // packedAssetID
#include <cpplib/libstrm.hp>
#if DESIGNER_CHEATS
#include "hscore.h"
#include <cstring>
#endif



//==============================================================================

Level* theLevel;

// Resident ground-atlas accessor for the Moon position-display minimap.
// terrain_texture.tga fills RM0's texture atlas (Room0.ruv: a single
// 0,0,1024,1024 entry) and each VRAM slot is its own GL texture, so the minimap
// samples the whole resident texture (UV 0..1) — the live ground the player is
// standing on — instead of a separate baked minimap.tga. Returns the atlas
// PixelMap, or nullptr if no level is loaded. Lives here (not display.cc)
// because it needs theLevel/AssetManager, mirroring the wf_moon_* game->display
// global pattern. When chunks later share an atlas (Phase 2+), swap UV 0..1 for
// the texture's RMUV sub-rect (theLevel->GetAssetManager().LookupTexture(...).texture).
// See docs/plans/2026-06-04-moon-overhead-map-and-chunk-texture-streaming.md.
const PixelMap* wf_moon_ground_atlas()
{
	if (!theLevel)
		return nullptr;
	packedAssetID rm0(0, packedAssetID::TGA, 0xFFF);   // RM0 ground-atlas slot; LookupTexture keys on Room()
	LookupTextureStruct lt = theLevel->GetAssetManager().LookupTexture("terrain_texture.tga", rm0.ID());
	return &lt.texturePixelMap;
}

// Simulated actor for the "meta-script" run
//const WFGame::LevelActor WFGame::_ActorLevel;

//==============================================================================

WFGame::WFGame( const int nStartingLevel )
	:
	// Memory pool for allocating MsgPort messages
	_msgPortMemPool( MemPoolConstruct( sizeof( SMsg ), MSGPORTPOOLSIZE, HALLmalloc ) ),
	_overrideLevelNum( nStartingLevel ),
	_desiredLevelNum( 0 ),		// default to first level in TOC; overridden by -l flag or shell script
	_curLevel( nullptr ),
	_gameMailboxes( nullptr ),
	_bContinue( true ),
	_deltaTime( Scalar::zero )
{
	DBSTREAM1( cprogress << "WFGame::WFGame" << std::endl; )
	JoltRuntimeInit();


	assert(ValidPtr(_msgPortMemPool));

	extern int _halWindowXPos;
	extern int _halWindowYPos;
	extern int _halWindowWidth;
	extern int _halWindowHeight;
	_display = new (HALLmalloc) Display(10,_halWindowXPos, _halWindowYPos, _halWindowWidth, _halWindowHeight, HALLmalloc);
	assert(ValidPtr(_display));

	_videoMemory = new (HALLmalloc) VideoMemory(*_display);
    assert(ValidPtr(_videoMemory));

//	_viewPort = new (HALLmalloc) ViewPort( *_display, 3001, Scalar( 320, 0 ), Scalar( 240, 0 ), HALLmalloc, 750 );
	_viewPort = new (HALLmalloc) ViewPort( *_display, 3001, Scalar( 320, 0 ), Scalar( 240, 0 ), HALLmalloc, 2000 );
	assert( ValidPtr( _viewPort ) );
	DBSTREAM3( cprogress << "WFGame::WFGame done" << std::endl; )
#if defined( DO_CD_IFF )
	extern const char* gLevelOverridePath;
	if ( gLevelOverridePath == nullptr )
	{
		DBSTREAM1( std::cout <<"Opening cd.iff" << std::endl; )
		_gameFile = ConstructDiskFile( "cd.iff", HALLmalloc );
		assert( ValidPtr( _gameFile ) );
	}
	else
	{
		_gameFile = nullptr;	// -L<path> mode: opened in RunGameScript instead
	}
#endif
}

//==============================================================================

WFGame::~WFGame()
{
	DBSTREAM1( cprogress << "WFGame::~WFGame" << std::endl; )

	// Hosts (editor, replay driver) must call UnloadLevel before destructing.
	// Standalone RunLevel always does. Tripping this assert means a level
	// was loaded but never unloaded.
	assert(!_curLevel);
	assert(!_gameMailboxes);

#if defined(DO_CD_IFF)
	if ( _gameFile != nullptr )
	{
		DBSTREAM1( std::cout <<"closing cd.iff" << std::endl; )
		MEMORY_DELETE(HALLmalloc,_gameFile,_DiskFile);
	}
#endif

//#ifdef DO_PROFILE
//	DBSTREAM1( cprogress << "Shutting down profiling" << std::endl; )
//	DELETE_CLASS( testProfile );
//#endif

	// HALLmalloc allocs in WFGame, time order:
	//   1. _msgPortMemPool obj + buffer (member init line 66, via MemPoolConstruct)
	//   2. _display (body line 84)
	//   3. _videoMemory (line 87)
	//   4. _viewPort (line 91)
	//   5. _gameFile (line 99, freed above)
	// LIFO-reverse Free: _gameFile, _viewPort, _videoMemory, _display, then
	// MemPoolDestruct (which Frees _buffer then memPool obj — both LIFO-
	// correct since _buffer was alloc'd just after the obj).
	MEMORY_DELETE(HALLmalloc,_viewPort,ViewPort);
	MEMORY_DELETE(HALLmalloc,_videoMemory,VideoMemory);
	MEMORY_DELETE(HALLmalloc,_display,Display);
	MemPoolDestruct( _msgPortMemPool );
	JoltRuntimeShutdown();
	DBSTREAM1( cprogress << "game destructor finished" << std::endl; )
}

//==============================================================================

struct CHUNKHDR
{
	int32 tag;
	int32 size;
};

//-----------------------------------------------------------------------------

// Set by `-L<path>` on the command line. When non-null, RunGameScript opens
// this single level file directly and skips the cd.iff bundle / SHEL meta
// script entirely. The file must be a complete L<N> chunk (8-byte chunk
// header + ALGN + RAM + ...), exactly as it would appear inside cd.iff.
// Seek to SECTOR_SIZE then puts us at the RAM tag, just like the cd.iff
// path. Build with: `iffcomp { 'L0' [ "level.iff" ] }` or pre-pend the
// 8-byte chunk header by hand.
const char* gLevelOverridePath = nullptr;

void
WFGame::RunGameScript()				// runs the whole game, returns when game (really) over (quit to OS)
{
	DBSTREAM2( cflow << "WFGame::RunGameScript" << std::endl; )

	if ( gLevelOverridePath != nullptr )
	{
		DBSTREAM1( cprogress << "Loading single level from path: " << gLevelOverridePath << std::endl; )
		_DiskFile* diskFile = ConstructDiskFile( const_cast<char*>( gLevelOverridePath ), HALLmalloc );
		assert( ValidPtr( diskFile ) );
		// File is a complete L<N> chunk: header + ALGN + RAM + ... — same
		// layout as inside cd.iff. RAM lands at SECTOR_SIZE.
		diskFile->SeekRandom( DiskFileCD::_SECTOR_SIZE );
#if defined(__EMSCRIPTEN__)
		// v2 (plan Phase 7): hand the level to the browser's frame scheduler
		// instead of spinning a blocking while loop. RunLevelWeb does not return
		// — it unwinds the C stack and the browser drives StepFrame from here on,
		// so the diskFile is freed by WebTick on level-done, not here.
		RunLevelWeb( diskFile );
		// unreachable
#else
		RunLevel( diskFile );
		MEMORY_DELETE( HALLmalloc, diskFile, DiskFile );
#endif
		return;
	}

#if defined(DO_CD_IFF)
	assert(ValidPtr(_gameFile));
	_gameFile->SeekRandom(0);
	// read game file header
	_gameTOC.LoadTOC(*_gameFile,_gameFile->FilePos());
	AssertMsg(_gameTOC.GetName() == IFFTAG('G','A','M','E'),"gametoc name = " << (void*)_gameTOC.GetName());
#define GAMEFILE_SCRIPT 0
#define GAMEFILE_LEVELSTART 1
	const DiskTOC::TOCEntry& tocScriptEntry = _gameTOC.GetTOCEntry(GAMEFILE_SCRIPT);
	_gameFile->SeekForward(tocScriptEntry._offsetInDiskFile);
	assert(tocScriptEntry._size % DiskFileCD::_SECTOR_SIZE == 0);
	char* streamBuffer = new (HALScratchLmalloc) char[tocScriptEntry._size];
	_gameFile->ReadBytes( streamBuffer, tocScriptEntry._size);
 	CHUNKHDR& chdr = *((CHUNKHDR*)streamBuffer);
	assert(chdr.tag = IFFTAG('S','H','E','L'));

	char* scriptMemory = new (HALLmalloc) char[chdr.size];
	assert(ValidPtr(scriptMemory));
	memcpy(scriptMemory,streamBuffer+sizeof(CHUNKHDR),chdr.size);
	HALScratchLmalloc.Free(streamBuffer,tocScriptEntry._size);

	const void* _pScript = (const void*)scriptMemory;
	assert( ValidPtr( _pScript ) );
#else
#error need to write a new static script
	const uint8 pMetaScript[] =
	{
		0x06,0x00,0x00,0x00,0x01,0x00,0x2A,0x01,0x03,0x00,0x00,0x00,
	 	0x01,0x00,0x2C,0x01,0x01,0x00,0x37,0x01,0x00,0x00,0x88,0x13,
		0x00,0x00,0x01,0x00,0x53,0x68,0x65,0x6C,0x6C,0x00,0x00,0x00
	}; //            ^ This is the level number
	const void* _pScript = (const void*)pMetaScript;
#endif
	
	DBSTREAM2( cflow << "WFGame::RunGameScript:construct MetaScript" << std::endl; )
	assert( ValidPtr( _pScript ) );
   GameMailboxes mailboxes(*this);
   SingleMailboxesManager mailboxesManager(mailboxes);
   ScriptInterpreter* interpreter = ScriptInterpreterFactory(mailboxesManager, HALLmalloc);
   assert(ValidPtr(interpreter));
	DBSTREAM1( cprogress << "meta script interpreter created" << std::endl; )

	char* pScript = (char*)_pScript;
	for ( ;; )
	{
		DBSTREAM2( cflow << "WFGame::RunGameScript::loop top" << std::endl; )
      //Scalar data = 
      interpreter->RunScript(pScript,0,3);  // meta script is always Forth (shell.aib)
  		//  cerr << "EvalScript(" << szScript << ")=" << data << endl;
  		//return data;
      
		if(_overrideLevelNum != -1)
			_desiredLevelNum = _overrideLevelNum;

		assert(_desiredLevelNum >= 0);
		assert(_desiredLevelNum < 9999);
		DBSTREAM3( cprogress << "Loading level " << _desiredLevelNum << std::endl; )
#if defined(DO_CD_IFF)

		const DiskTOC::TOCEntry& tocLevelEntry = _gameTOC.GetTOCEntry(GAMEFILE_LEVELSTART+_desiredLevelNum);
//		std::cout << "seeking to level at offset " << tocLevelEntry._offsetInDiskFile+DiskFileCD::_SECTOR_SIZE << std::endl;
		_gameFile->SeekRandom(tocLevelEntry._offsetInDiskFile+DiskFileCD::_SECTOR_SIZE);
		RunLevel(_gameFile);
#else
		char szLevelName[ _MAX_PATH ];
		sprintf( szLevelName, "level%d.iff", _desiredLevelNum );
		_DiskFile* diskFile = CreateDiskFile(szLevelName, HALLmalloc);
		assert(ValidPtr(diskFile));
		RunLevel(diskFile);
		assert(ValidPtr(diskFile));
		MEMORY_DELETE( HALLmalloc, diskFile,DiskFile);
#endif
		if (HALWindowCloseRequested())
			break;
	}
#if defined(DO_CD_IFF)
	HALLmalloc.Free((void*)pScript);
#endif
}

//==============================================================================


//-----------------------------------------------------------------------------

void
WFGame::LoadLevel(_DiskFile* levelFile)
{
    DBSTREAM3( cprogress << "WFGame::LoadLevel (sizeof level = " << sizeof(Level) << std::endl; )
    assert(!_curLevel);
    assert(!_gameMailboxes);

    _gameMailboxes = new (HALLmalloc) GameMailboxes(*this);
    assert( ValidPtr(_gameMailboxes));
    _curLevel = new (HALLmalloc) Level( *this, levelFile, *_viewPort, *_videoMemory, _gameMailboxes );
	DBSTREAM3( cprogress << "new level at address " << _curLevel << ", sizeof " << sizeof(Level) << std::endl; )
	assert( ValidPtr(_curLevel));
	DBSTREAM3( cprogress << "WFGame::LoadLevel done" << std::endl; )

	// Start per-level music: look for level<N>.mid alongside cd.iff.
	if (gMusicPlayer) {
		char midiName[64];
		if (_desiredLevelNum >= 0)
			snprintf(midiName, sizeof(midiName), "level%d.mid", _desiredLevelNum);
		else
			snprintf(midiName, sizeof(midiName), "music.mid");
		// play() silently ignores missing files
		gMusicPlayer->play(midiName);
	}

	// Load Q*bert SFX. Paths are relative to the process cwd (project root).
	// Silently no-ops on levels where these files don't exist (e.g. snowgoons).
	SfxLibrary::Load(0, "wflevels/qbert_practice/sfx/qbert_hop.wav");
	SfxLibrary::Load(1, "wflevels/qbert_practice/sfx/qbert_land.wav");
	SfxLibrary::Load(2, "wflevels/qbert_practice/sfx/qbert_fall.wav");
	SfxLibrary::Load(3, "wflevels/qbert_practice/sfx/qbert_swear.wav");
	SfxLibrary::Load(4, "wflevels/qbert_practice/sfx/qbert_round_clear.wav");
	SfxLibrary::Load(5, "wflevels/qbert_practice/sfx/qbert_kill.wav");
	SfxLibrary::Load(6, "wflevels/qbert_practice/sfx/qbert_disc.wav");

	_bContinue = true;
	_deltaTime = Scalar::zero;
	DBSTREAM1 ( cprogress << "Entering main game loop\n"; );
	RestApi_Start();
	{
		extern int gDebugPort;
		DebugServer_Start(gDebugPort);
	}
}

//-----------------------------------------------------------------------------

void
WFGame::UnloadLevel()
{
	DBSTREAM3( cprogress << "WFGame::UnloadLevel" << std::endl; )
	assert(_curLevel);
	assert(_gameMailboxes);

	// Flush any in-flight ordertable renderings before tearing down the level.
	// (Previously the trailing pair of PageFlips at the end of RunLevel.)
	_display->PageFlip();
	_display->PageFlip();

	RestApi_Stop();
	DebugServer_Stop();
	if (gMusicPlayer) gMusicPlayer->stop();
	SfxLibrary::Clear();

	// Level must be destroyed before _gameMailboxes — the level's
	// _scratchMailboxes holds a parent pointer to it.
	MEMORY_DELETE(HALLmalloc,_curLevel,Level);
	_curLevel = nullptr;
	MEMORY_DELETE(HALLmalloc,_gameMailboxes,GameMailboxes);
	_gameMailboxes = nullptr;
}

//-----------------------------------------------------------------------------

bool
WFGame::LevelDone() const
{
	// Treat "no level loaded" as done — callers can poll between
	// UnloadLevel and a future LoadLevel without crashing.
	return !_curLevel || _curLevel->done();
}

//-----------------------------------------------------------------------------

void
WFGame::SmokeRunFrameStep(int frames, int cycles)
{
	extern const char* gLevelOverridePath;
	AssertMsg(gLevelOverridePath, "--frame-step-smoke requires -L<level-path>");
	assert(cycles >= 1);

	DBSTREAM1(cprogress << "SmokeRunFrameStep: opening " << gLevelOverridePath
	                    << " (frames=" << frames << " cycles=" << cycles << ")" << std::endl;)
	_DiskFile* df = ConstructDiskFile(const_cast<char*>(gLevelOverridePath), HALLmalloc);
	assert(ValidPtr(df));

	for (int cycle = 0; cycle < cycles; ++cycle) {
		DBSTREAM1(cprogress << "SmokeRunFrameStep: cycle " << (cycle+1) << "/" << cycles << std::endl;)
		// File is a complete L<N> chunk; RAM lands at SECTOR_SIZE
		// (matches RunGameScript's -L path). Re-seek each cycle.
		df->SeekRandom(DiskFileCD::_SECTOR_SIZE);

		LoadLevel(df);
		DBSTREAM1(cprogress << "SmokeRunFrameStep: LoadLevel done, stepping " << frames << " frames" << std::endl;)

		for (int i = 0; i < frames && !HALWindowCloseRequested() && ContinueRequested(); ++i) {
			Scalar dt;
			FrameResult r = StepFrame(true, &dt);
			if (r == FrameResult::Done) {
				DBSTREAM1(cprogress << "SmokeRunFrameStep: level done at frame " << i << std::endl;)
				break;
			}
		}

		UnloadLevel();
	}

	MEMORY_DELETE(HALLmalloc, df, _DiskFile);
	DBSTREAM1(cprogress << "SmokeRunFrameStep: complete" << std::endl;)
}

//-----------------------------------------------------------------------------

#if defined(WF_DEBUG_BRIDGE) || defined(WF_ENABLE_EDITOR)
int
WFGame::RunWfmutSmoke()
{
	extern const char* gLevelOverridePath;
	AssertMsg(gLevelOverridePath, "--wfmut-smoke requires -L<level-path>");

	DBSTREAM1(cprogress << "RunWfmutSmoke: opening " << gLevelOverridePath << std::endl;)
	_DiskFile* df = ConstructDiskFile(const_cast<char*>(gLevelOverridePath), HALLmalloc);
	assert(ValidPtr(df));
	df->SeekRandom(DiskFileCD::_SECTOR_SIZE);

	LoadLevel(df);
	int failures = wfmut::RunSmokeTests(*_curLevel);
	UnloadLevel();

	MEMORY_DELETE(HALLmalloc, df, _DiskFile);
	DBSTREAM1(cprogress << "RunWfmutSmoke: " << failures << " failures" << std::endl;)
	return failures;
}

int
WFGame::RunWfmutThreadTest()
{
	extern const char* gLevelOverridePath;
	AssertMsg(gLevelOverridePath, "--wfmut-thread-test requires -L<level-path>");

	_DiskFile* df = ConstructDiskFile(const_cast<char*>(gLevelOverridePath), HALLmalloc);
	assert(ValidPtr(df));
	df->SeekRandom(DiskFileCD::_SECTOR_SIZE);

	LoadLevel(df);
	// Expected to abort inside the off-thread wfmut call (X5 guard). If it
	// returns, the guard didn't fire (non-assertion build).
	int r = wfmut::RunThreadGuardDeathTest(*_curLevel);
	UnloadLevel();

	MEMORY_DELETE(HALLmalloc, df, _DiskFile);
	return r;
}
#endif // WF_DEBUG_BRIDGE || WF_ENABLE_EDITOR

//-----------------------------------------------------------------------------

#if defined(WF_ENABLE_EDITOR)
namespace {
	EditorBuildCallback   sEditorBuild   = nullptr;
	EditorPresentCallback sEditorPresent = nullptr;
	void*                 sEditorCtx     = nullptr;
}

extern "C" void
SetEditorFrameCallbacks( EditorBuildCallback build, EditorPresentCallback present, void* ctx )
{
	sEditorBuild   = build;
	sEditorPresent = present;
	sEditorCtx     = ctx;
}

void
WFGame::RunEditor()
{
	extern const char* gLevelOverridePath;
	AssertMsg(gLevelOverridePath, "--editor requires -L<level-path>");

	_DiskFile* df = ConstructDiskFile(const_cast<char*>(gLevelOverridePath), HALLmalloc);
	assert(ValidPtr(df));
	df->SeekRandom(DiskFileCD::_SECTOR_SIZE);

	LoadLevel(df);
	DBSTREAM1( cprogress << "RunEditor: level loaded, entering editor loop" << std::endl; )

	// Editor owns cadence + the swap. Each iteration: the editor builds its UI
	// and applies pending edits to the engine (build), THEN StepFrame renders
	// the now-up-to-date scene into the back buffer (do_swap=false), THEN the
	// editor composites its overlay and swaps (present). Build-before-render is
	// what makes a same-frame edit visible the same frame. Loop until build
	// returns false (window closed); a null build makes this a no-op loop body.
	for (;;) {
		Scalar dt;
		if (!sEditorBuild || !sEditorBuild(sEditorCtx))
			break;
		StepFrame(false, &dt);
		if (sEditorPresent)
			sEditorPresent(sEditorCtx);
	}

	UnloadLevel();
	MEMORY_DELETE(HALLmalloc, df, _DiskFile);
	DBSTREAM1( cprogress << "RunEditor: complete" << std::endl; )
}
#endif // WF_ENABLE_EDITOR

//-----------------------------------------------------------------------------

WFGame::FrameResult
WFGame::StepFrame(bool do_swap, Scalar* out_dt)
{
	assert(_curLevel);

	// v2 web (plan Phase 7): no per-frame yield here — the browser calls
	// WebTick once per animation frame and the canvas presents when WebTick
	// returns. (v1 yielded via emscripten_sleep(0) under ASYNCIFY; removed with
	// the loop inversion.) Suspend on web is handled by pausing the main loop
	// (emscripten_pause_main_loop in the visibility callback), so the suspended
	// branch below is only reached on Android/Linux.

	if ( HALIsSuspended() )
	{
		// Platform has backgrounded us (Android onPause). Skip render +
		// PageFlip to avoid touching a torn-down GL context; pump platform
		// events so APP_CMD_RESUME actually reaches HALNotifyResume and
		// unsticks us. Linux never enters this branch — HALIsSuspended()
		// is always false there.
		HALPumpSuspendedEvents();
		usleep(16000);
		if (out_dt) *out_dt = Scalar::zero;
		return FrameResult::Suspended;
	}

	RestApi_DrainQueue();
	DebugServer_DrainQueue(*_curLevel);
	assert(HALScratchLmalloc.Empty());
	// The game debug streams (gamestrm.cc) hit a cross-TU static-init-order issue
	// on web — cframeinfo's streambuf isn't wired when the first write runs, so
	// operator<< calls a null streambuf vtable slot ("null function" wasm trap).
	// This per-frame DBSTREAM1 also violates dbstrm.hp's own "nothing in the game
	// loop" contract for DBSTREAM1, and writes to a null sink (no output), so skip
	// it on web. See docs/plans/2026-06-12-wf-edit-in-the-browser.md.
#if !defined(__EMSCRIPTEN__)
	DBSTREAM1( cframeinfo << char(12) << std::endl << "Frame Info:" << std::endl; )
#endif
	DBSTREAM2( cflow << "Top of WFGame::update" << std::endl; )


#if defined(DESIGNER_CHEATS)
	if ( PIGSUserAborted() )
	{
		DBSTREAM1( cwarn << "Level Aborted" << std::endl; )
		_bContinue = false;
		while(PIGSUserAborted())
			;						// wait for buttons to be released
	}
#endif

	assert( ValidPtr(_curLevel ));
	_curLevel->Validate();
	DBSTREAM2( cflow << "WFGame::update: curLevel->Update" << std::endl; )
	if ( !DebugServer_IsPaused() )
		_curLevel->update(_deltaTime);
	DBSTREAM2( cflow << "WFGame::update: render scene" << std::endl; )

	if(_curLevel->camera() && _curLevel->camera()->ValidView())
	{
		_display->RenderBegin();
		_curLevel->RenderScene();
		RestApi_RenderBoxes();
		_display->RenderEnd();
	}
#if DO_ASSERTIONS
	else if(_curLevel->camera())
		AssertMsg(_curLevel->LevelClock().Current() < SCALAR_CONSTANT(10),"No Valid View after 10 seconds");
#endif

	DebugServer_BroadcastState(*_curLevel);
	DebugServer_BroadcastPerf(_deltaTime.AsFloat() * 1000.0f,
	                          _curLevel->GetObjectList().Size());
	DebugServer_BroadcastMailboxes(*_curLevel);
	DBSTREAM2( cflow << "WFGame::update: page flip" << std::endl; )
#if DESIGNER_CHEATS
		{
			extern int wf_hud_score, wf_hud_timer, wf_hud_lives, wf_hud_game_over;
			extern int wf_hud_entering_initials, wf_hud_initials_pos;
			extern char wf_hud_initials[4];
			// Moon Site 01 position-display HUD overlay — see docs/plans/2026-05-31-position-display-hud-overlay-on-the-moon-level-tex.md
			extern int   wf_moon_overlay_enabled;
			extern float wf_moon_player_x_m, wf_moon_player_y_m, wf_moon_player_z_m;
			extern float wf_moon_player_heading_rev;
			// Moon lander launch sequence — see docs/plans/2026-06-02-moon-lander-launch-sequence.md
			extern int   wf_moon_launch_phase;
			extern float wf_moon_launch_t_minus;
			// Site 01 lunar-descent game — see the MOON_LDR_* block in mailbox.inc
			extern int   wf_moon_ldr_active, wf_moon_ldr_state, wf_moon_ldr_thrust;
			extern float wf_moon_ldr_alt, wf_moon_ldr_vz, wf_moon_ldr_vx, wf_moon_ldr_vy;
			extern float wf_moon_ldr_fuel, wf_moon_ldr_range2;
			extern float wf_moon_ldr_impact_vz, wf_moon_ldr_impact_nz;
			Mailboxes& mb = _curLevel->GetMailboxes();
			wf_hud_score     = mb.ReadMailbox(70).WholePart();
			wf_hud_timer     = mb.ReadMailbox(71).WholePart();
			wf_hud_lives     = mb.ReadMailbox(72).WholePart();
			wf_hud_game_over = mb.ReadMailbox(420).WholePart();
			wf_moon_overlay_enabled     = mb.ReadMailbox(1875).WholePart();
			wf_moon_player_x_m          = mb.ReadMailbox(1876).AsFloat();
			wf_moon_player_y_m          = mb.ReadMailbox(1877).AsFloat();
			wf_moon_player_z_m          = mb.ReadMailbox(1878).AsFloat();
			wf_moon_player_heading_rev  = mb.ReadMailbox(1879).AsFloat();
			wf_moon_launch_phase        = mb.ReadMailbox(1881).WholePart();
			wf_moon_launch_t_minus      = mb.ReadMailbox(1882).AsFloat();
			wf_moon_ldr_active          = mb.ReadMailbox(EMAILBOX_MOON_LDR_ACTIVE).WholePart();
			wf_moon_ldr_state           = mb.ReadMailbox(EMAILBOX_MOON_LDR_STATE).WholePart();
			wf_moon_ldr_thrust          = mb.ReadMailbox(EMAILBOX_MOON_LDR_THRUST).WholePart();
			wf_moon_ldr_alt             = mb.ReadMailbox(EMAILBOX_MOON_LDR_ALT).AsFloat();
			wf_moon_ldr_vz              = mb.ReadMailbox(EMAILBOX_MOON_LDR_VZ).AsFloat();
			wf_moon_ldr_vx              = mb.ReadMailbox(EMAILBOX_MOON_LDR_VX).AsFloat();
			wf_moon_ldr_vy              = mb.ReadMailbox(EMAILBOX_MOON_LDR_VY).AsFloat();
			wf_moon_ldr_fuel            = mb.ReadMailbox(EMAILBOX_MOON_LDR_FUEL).AsFloat();
			wf_moon_ldr_range2          = mb.ReadMailbox(EMAILBOX_MOON_LDR_RANGE2).AsFloat();
			wf_moon_ldr_impact_vz       = mb.ReadMailbox(EMAILBOX_MOON_LDR_IMPACT_VZ).AsFloat();
			wf_moon_ldr_impact_nz       = mb.ReadMailbox(EMAILBOX_MOON_LDR_IMPACT_NZ).AsFloat();

			// High-score initials entry — triggered on fresh game-over edge.
			// Joystick bits from mb 1910 (JUSTPRESSED, already edge-detected):
			//   0x0800 UP   → prev letter
			//   0x1000 DOWN → next letter
			//   0x2000 RIGHT → advance / confirm last char
			//   0x4000 LEFT  → back one position
			static int s_prev_game_over = 0;
			static int s_initials_pos = 0;
			static char s_initials[4] = {'A','A','A','\0'};

			// GO_HOLD_TIMER (mb 591): C++ decrements each frame; Forth won't
			// restart while > 0.  GO_BLOCK (mb 590): set 1 while initials entry
			// is live so Forth ignores joystick for restart entirely.
			{
				int hold = mb.ReadMailbox(591).WholePart();
				if (hold > 0)
					mb.WriteMailbox(591, Scalar(hold - 1, 0));
			}

			if (wf_hud_game_over && !s_prev_game_over)
			{
				// Arm 3 s minimum hold regardless of whether score qualifies.
				mb.WriteMailbox(591, Scalar(180, 0));
				HScore_Load();
				if (HScore_IsHigh(wf_hud_score))
				{
					s_initials_pos = 0;
					s_initials[0] = s_initials[1] = s_initials[2] = 'A';
					wf_hud_entering_initials = 1;
					mb.WriteMailbox(590, Scalar(1, 0));  // block Forth restart
				}
			}
			s_prev_game_over = wf_hud_game_over;

			if (wf_hud_entering_initials)
			{
				int joy = mb.ReadMailbox(1910).WholePart();
				if (joy & 0x0800)  // UP: prev letter
					s_initials[s_initials_pos] = (s_initials[s_initials_pos] - 'A' + 25) % 26 + 'A';
				if (joy & 0x1000)  // DOWN: next letter
					s_initials[s_initials_pos] = (s_initials[s_initials_pos] - 'A' + 1) % 26 + 'A';
				if (joy & 0x2000)  // RIGHT: advance / confirm
				{
					if (s_initials_pos < 2)
					{
						s_initials_pos++;
					}
					else
					{
						HScore_Insert(wf_hud_score, mb.ReadMailbox(425).WholePart(), s_initials);
						HScore_Save();
						wf_hud_entering_initials = 0;
						s_initials_pos = 0;
						mb.WriteMailbox(590, Scalar(0, 0));   // unblock Forth restart
						mb.WriteMailbox(591, Scalar(180, 0)); // 3 s to view updated table
					}
				}
				if ((joy & 0x4000) && s_initials_pos > 0)  // LEFT: back
					s_initials_pos--;

				memcpy(wf_hud_initials, s_initials, 4);
				wf_hud_initials_pos = s_initials_pos;
			}
		}
#endif
	_deltaTime = do_swap ? _display->PageFlip() : _display->MeasureDelta();

	// Host stalls (editor paused on a modal, breakpoint hit, GL hiccup)
	// would otherwise hand the next StepFrame a multi-second deltaTime.
	// PageFlip / MeasureDelta already cap at 1/5 s (200 ms); StepFrame
	// tightens to 100 ms which lines up with Jolt's substep tolerance
	// (project_variable_tick_rate_loadbearing). Standalone wf_game
	// rarely trips this — only on real stalls — so its behaviour is
	// unchanged in practice. Editor-as-host needs the tighter cap to
	// stay simulable across pauses.
	if (_deltaTime > kMaxSimDeltaSeconds)
		_deltaTime = kMaxSimDeltaSeconds;

	DBSTREAM2( cflow << "WFGame::update: done" << std::endl; )

	assert(HALScratchLmalloc.Empty());		// make sure everyone remembered to free their scratch memory

	if (out_dt) *out_dt = _deltaTime;
	return _curLevel->done() ? FrameResult::Done : FrameResult::Rendered;
}

//-----------------------------------------------------------------------------

void
WFGame::RunLevel(_DiskFile* levelFile)
{
	LoadLevel(levelFile);

	while ( !LevelDone() && ContinueRequested() && !HALWindowCloseRequested() )
	{
		StepFrame(true);
	}

#pragma message ("KTS: write code to handle lives and restarting same level, etc.")
	DBSTREAM1( std::cout << ", _bContinue = " << _bContinue << ", _curLevel->done() = " << _curLevel->done() << std::endl; )

	UnloadLevel();
}

//==============================================================================

#if defined(__EMSCRIPTEN__)
//-----------------------------------------------------------------------------
// v2 web main loop (plan Phase 7). One WFGame is live for the page, so a
// file-static back-pointer is enough for the C-ABI emscripten callback to reach
// it. This replaces RunLevel's blocking while loop + per-frame ASYNCIFY yield.

namespace {
	WFGame*    s_webGame      = nullptr;
	_DiskFile* s_webLevelFile = nullptr;
	void WebMainLoopThunk() { assert(s_webGame); s_webGame->WebTick(); }
}

void
WFGame::RunLevelWeb(_DiskFile* levelFile)
{
	s_webGame      = this;
	s_webLevelFile = levelFile;     // kept alive (chunk streaming) until WebTick unloads
	LoadLevel(levelFile);

	// fps=0 → requestAnimationFrame cadence; simulate_infinite_loop=1 throws the
	// Emscripten 'unwind' to escape the C stack and keep the runtime alive with
	// NO ASYNCIFY. This call never returns; the browser now drives WebTick, so
	// the HALStart/PIGSMain teardown after us is intentionally skipped (the page
	// owns process lifetime — same as any emscripten_set_main_loop app).
	emscripten_set_main_loop(WebMainLoopThunk, 0, 1);
}

void
WFGame::WebTick()
{
	// Same termination predicate as RunLevel's while condition; on the web -L
	// path there is no next level, so we stop (the last frame stays presented).
	if ( LevelDone() || !ContinueRequested() || HALWindowCloseRequested() )
	{
		emscripten_cancel_main_loop();
		UnloadLevel();
		if (s_webLevelFile)
		{
			MEMORY_DELETE(HALLmalloc, s_webLevelFile, DiskFile);
			s_webLevelFile = nullptr;
		}
		return;
	}
	StepFrame(true);                // browser composites the canvas when this returns
}
#endif // __EMSCRIPTEN__

#if defined(__EMSCRIPTEN__) && defined(WF_ENABLE_EDITOR)
//-----------------------------------------------------------------------------
// Web editor main loop. The browser owns cadence, so RunEditor's blocking
// for(;;) is inverted into a per-frame callback (same shape as RunLevelWeb).
// build → StepFrame(false) → present is preserved (the zero-latency local-edit
// invariant). engine/wf_edit/main.cc registers the build/present callbacks via
// SetEditorFrameCallbacks before HALStart, exactly as the native editor does.

namespace {
	WFGame*    s_webEditorGame = nullptr;
	_DiskFile* s_webEditorDf   = nullptr;
	void WebEditorLoopThunk() { assert(s_webEditorGame); s_webEditorGame->WebTickEditor(); }
}

void
WFGame::RunEditorWeb()
{
	extern const char* gLevelOverridePath;
	AssertMsg(gLevelOverridePath, "--editor requires -L<level-path>");

	_DiskFile* df = ConstructDiskFile(const_cast<char*>(gLevelOverridePath), HALLmalloc);
	assert(ValidPtr(df));
	df->SeekRandom(DiskFileCD::_SECTOR_SIZE);
	LoadLevel(df);

	s_webEditorGame = this;
	s_webEditorDf   = df;     // kept alive until WebTickEditor unloads

	// Never returns; the browser drives WebTickEditor each animation frame. The
	// HALStart / main() teardown after us is intentionally skipped (the page
	// owns process lifetime) — same as RunLevelWeb.
	emscripten_set_main_loop(WebEditorLoopThunk, 0, 1);
}

void
WFGame::WebTickEditor()
{
	Scalar dt;
	if (!sEditorBuild || !sEditorBuild(sEditorCtx))
	{
		emscripten_cancel_main_loop();
		UnloadLevel();
		if (s_webEditorDf)
		{
			MEMORY_DELETE(HALLmalloc, s_webEditorDf, _DiskFile);
			s_webEditorDf = nullptr;
		}
		return;
	}
	StepFrame(false, &dt);
	if (sEditorPresent)
		sEditorPresent(sEditorCtx);
}
#endif // __EMSCRIPTEN__ && WF_ENABLE_EDITOR

//==============================================================================

Scalar
WFGame::ReadSystemMailbox( int boxnum ) const
{
    RangeCheck(EMAILBOX_PERSISTENT_START,boxnum,EMAILBOX_PERSISTENT_MAX);

	switch(boxnum)
	{
		case EMAILBOX_LEVEL_TO_RUN:
			return Scalar( _desiredLevelNum, 0 );

		default:
			assert(0);
	};

	assert(0);
	return Scalar::zero;
}

//=============================================================================

void
WFGame::WriteSystemMailbox( int boxnum, Scalar value )
{
    RangeCheck(EMAILBOX_PERSISTENT_SYSTEM_START,boxnum,EMAILBOX_PERSISTENT_SYSTEM_MAX);

    switch(boxnum)
    {
        case EMAILBOX_LEVEL_TO_RUN:
            _desiredLevelNum = value.WholePart();
            DBSTREAM1( cscripting << "set desired level to " << _desiredLevelNum << std::endl; )
            break;
        default:
            AssertMsg(0, "WFGame::WriteSystemMailbox( " << boxnum << ", " << value << " )" );
    }
}

//=============================================================================
