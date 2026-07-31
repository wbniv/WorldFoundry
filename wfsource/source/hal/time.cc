//=============================================================================
// time.cc: clock reading funcions
//=============================================================================
// Time Clock API
//
//			SYS_TICKS returns a number of ticks, as a long,
// 					and is used by the Streamer
//
//			SYS_CLOCK returns a number of seconds since reset, as a Scalar
//
//			SYS_CLOCK_RESET resets the clock to zero
//
//=============================================================================

#include <hal/time.hp>

long _nWallClockBaseTime;

//=============================================================================


//=============================================================================


//=============================================================================

#if   defined(__LINUX__) || defined(__ANDROID__)
#include <time.h>
Scalar SYS_CLOCK(void)
{
    long ticks = SYS_TICKS() - _nWallClockBaseTime;  // centiseconds elapsed
    return Scalar::FromFloat((float)ticks / 100.0f);
}
#endif

//=============================================================================

void
SYS_CLOCK_RESET(void)
{
	_nWallClockBaseTime = SYS_TICKS();
}

//=============================================================================
