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
	char szLineNumber[ 15 ];
	snprintf( szLineNumber, 15, "%d", line );
	printf( "+- ASSERTION FAILED ----------------------------------------------------------+\n" );
	if ( expr )
		printf( "|%-77s|\n", expr );
	printf( "|in file \"%s\" on line %s%*s|\n",	file, szLineNumber, 58-strlen(file)-strlen(szLineNumber), "" );
    printf( "+-----------------------------------------------------------------------------+\n" );



	exit( -1 );
}

//===========================================================================*/
