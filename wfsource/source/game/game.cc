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
#include <audio/music.hp>
#include <audio/sfx_library.hp>
#include "rest_api.hp"
#include "debug_server.hp"
#include "physics_jolt.hp"
#include "oas/matte.ht"
#include "gamestrm.hp"
#include "camera.hp"
#include "oas/matte.ht"
#include "matte.hp"
#include "mailbox.hp"
#include <gfx/vmem.hp>
#include <cpplib/libstrm.hp>
#if DESIGNER_CHEATS
#include "hscore.h"
#include <cstring>
#endif



//==============================================================================

Level* theLevel;

// Simulated actor for the "meta-script" run
//const WFGame::LevelActor WFGame::_ActorLevel;

//==============================================================================

WFGame::WFGame( const int nStartingLevel )
	:
	// Memory pool for allocating MsgPort messages
	_msgPortMemPool( MemPoolConstruct( sizeof( SMsg ), MSGPORTPOOLSIZE, HALLmalloc ) ),
	_overrideLevelNum( nStartingLevel ),
	_desiredLevelNum( 0 )		// default to first level in TOC; overridden by -l flag or shell script
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

	MemPoolDestruct( _msgPortMemPool );

	MEMORY_DELETE(HALLmalloc,_viewPort,ViewPort);
	MEMORY_DELETE(HALLmalloc,_videoMemory,VideoMemory);
	MEMORY_DELETE(HALLmalloc,_display,Display);
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
		RunLevel( diskFile );
		MEMORY_DELETE( HALLmalloc, diskFile, DiskFile );
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
WFGame::RunLevel(_DiskFile* levelFile)
{
    DBSTREAM3( cprogress << "WFGame::RunLevel (sizeof level = " << sizeof(Level) << std::endl; )
    GameMailboxes gmb(*this);
    Level* _curLevel = new (HALLmalloc) Level( levelFile, *_viewPort, *_videoMemory, &gmb );
	DBSTREAM3( cprogress << "new level at address " << _curLevel << ", sizeof " << sizeof(Level) << std::endl; )
	assert( ValidPtr(_curLevel));
	DBSTREAM3( cprogress << "WFGame::loadLevel done" << std::endl; )

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

	Scalar deltaTime = Scalar::zero;
	bool _bContinue = true;
	DBSTREAM1 ( cprogress << "Entering main game loop\n"; );
	RestApi_Start();
	{
		extern int gDebugPort;
		DebugServer_Start(gDebugPort);
	}

	while ( !_curLevel->done() && _bContinue && !HALWindowCloseRequested() )
	{
		if ( HALIsSuspended() )
		{
			// Platform has backgrounded us (Android onPause). Skip render +
			// PageFlip to avoid touching a torn-down GL context; pump platform
			// events so APP_CMD_RESUME actually reaches HALNotifyResume and
			// unsticks us. Linux never enters this branch — HALIsSuspended()
			// is always false there.
			HALPumpSuspendedEvents();
			usleep(16000);
			continue;
		}

		RestApi_DrainQueue();
		DebugServer_DrainQueue(*_curLevel);
		assert(HALScratchLmalloc.Empty());
		DBSTREAM1( cframeinfo << char(12) << std::endl << "Frame Info:" << std::endl; )
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
			_curLevel->update(deltaTime);
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
		DebugServer_BroadcastPerf(deltaTime.AsFloat() * 1000.0f,
		                          _curLevel->GetObjectList().Size());
		DebugServer_BroadcastMailboxes(*_curLevel);
		DBSTREAM2( cflow << "WFGame::update: page flip" << std::endl; )
#if DESIGNER_CHEATS
		{
			extern int wf_hud_score, wf_hud_timer, wf_hud_lives, wf_hud_game_over;
			extern int wf_hud_entering_initials, wf_hud_initials_pos;
			extern char wf_hud_initials[4];
			Mailboxes& mb = _curLevel->GetMailboxes();
			wf_hud_score     = mb.ReadMailbox(70).WholePart();
			wf_hud_timer     = mb.ReadMailbox(71).WholePart();
			wf_hud_lives     = mb.ReadMailbox(72).WholePart();
			wf_hud_game_over = mb.ReadMailbox(420).WholePart();

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
		deltaTime = _display->PageFlip();
		DBSTREAM2( cflow << "WFGame::update: done" << std::endl; )

		assert(HALScratchLmalloc.Empty());		// make sure everyone remembered to free their scratch memory
	}
	_display->PageFlip();			    // insure no pending ordertable renderings
	_display->PageFlip();


#pragma message ("KTS: write code to handle lives and restarting same level, etc.")
	DBSTREAM1( std::cout << ", _bContinue = " << _bContinue << ", _curLevel->done() = " << _curLevel->done() << std::endl; )

	RestApi_Stop();
	DebugServer_Stop();
	if (gMusicPlayer) gMusicPlayer->stop();
	SfxLibrary::Clear();
	MEMORY_DELETE(HALLmalloc,_curLevel,Level);
	_curLevel = NULL;
}

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
