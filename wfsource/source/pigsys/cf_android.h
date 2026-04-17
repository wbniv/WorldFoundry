//=============================================================================
// cf_android.h: Configuration for Android (arm64-v8a, API 21+)
//=============================================================================

#ifndef _CF_ANDROID_H
#define _CF_ANDROID_H

#if defined( __cplusplus )
// The NDK may define ANDROID as an integer macro; use ordinal to avoid collision.
const MachineType gHostMachineType = static_cast<MachineType>(1); // MACHINE_ANDROID ordinal; NDK #define ANDROID 1 collides with enum name
#endif

#define WF_BIG_ENDIAN       0
#define _BOOL_IS_DEFINED_   1

#ifndef __ANDROID__
#define __ANDROID__
#endif

#include <stddef.h>
#include <linux/limits.h>   // PATH_MAX

#define _MAX_PATH PATH_MAX
#define DIRECTORY_SEPARATOR '/'

// Android bionic provides strlwr-equivalent behaviour; define as no-op for now
// (strings from assets are already lower-case in the WF pipeline).
inline void strlwr(char* s) {
    for (; *s; ++s) *s = (*s >= 'A' && *s <= 'Z') ? (*s | 0x20) : *s;
}

START_EXTERN_C
#include <stdio.h>
END_EXTERN_C

// Define __LINUX__ so that all downstream legacy platform guards
// (#if defined(__LINUX__), #if !defined(__LINUX__)) work correctly on Android.
// Android shares the same POSIX/little-endian characteristics as the Linux port.
// This must come AFTER the platform-selection logic in pigsys.hp (which uses
// __ANDROID__ to pick this file over cf_linux.h).
#ifndef __LINUX__
#define __LINUX__
#endif

//=============================================================================
#endif // !defined(_CF_ANDROID_H)
//=============================================================================
