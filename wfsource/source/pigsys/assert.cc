//===========================================================================*/
// assert.cc
//===========================================================================*/

#include "pigsys.hp"
#include <cstdio>
#include <cstring>
#include <cstdlib>
#undef abort

#pragma message( "TODO: HAL should probably provide an interface to the debugger [very simple to start with--like is it there?]" )

//===========================================================================*/
// define a method for triggering the debugger
// when a debugger is present.



enum { ASSERT_IGNORE=0, ASSERT_ABORT, ASSERT_DEBUG };

void
_sys_assert( int, const char* expr, const char* file, int line )
{
#if defined(__EMSCRIPTEN__)
	// On the web, exit(-1) under -sEXIT_RUNTIME=0 unwinds to an opaque wasm
	// "null function" trap that blanks the canvas with no readable cause — far
	// worse than a loud, non-fatal console warning that names expr/file/line and
	// lets the app keep running. So on web a firing assert WARNS and CONTINUES
	// (native keeps the fatal exit below). Throttle so a per-frame assert can't
	// flood the console. See docs/plans/2026-06-12-wf-edit-in-the-browser.md.
	static int s_assertCount = 0;
	if ( ++s_assertCount == 25 )
		printf( "[wf assert] further assertion messages suppressed on web\n" );
	if ( s_assertCount > 24 )
		return;
#endif
	char szLineNumber[ 15 ];
	snprintf( szLineNumber, 15, "%d", line );
	printf( "+- ASSERTION FAILED ----------------------------------------------------------+\n" );
	if ( expr )
		printf( "|%-77s|\n", expr );
	printf( "|in file \"%s\" on line %s%*s|\n",	file, szLineNumber, 58-strlen(file)-strlen(szLineNumber), "" );
    printf( "+-----------------------------------------------------------------------------+\n" );

#if defined(__EMSCRIPTEN__)
	return;   // web: non-fatal — warn + continue (see above)
#else
	exit( -1 );
#endif
}

//===========================================================================*/
