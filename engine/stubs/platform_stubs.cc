// platform_stubs.cc — Linux stubs for missing platform functions
// These fill in symbols that exist on Windows but not Linux, or that
// belong to the optional multitasker (never called without DO_MULTITASKING).

#include <cctype>
#include <cstring>
#include <cstdlib>
#include <cstdio>

// strlwr: declared with C++ linkage in pigsys/cf_linux.h
void strlwr(char* s) {
    for (char* p = s; *p; ++p)
        *p = (char)tolower((unsigned char)*p);
}

// strnicmp: case-insensitive strncmp (Windows/BSD, not in POSIX)
extern "C" int strnicmp(const char* a, const char* b, size_t n) {
    return strncasecmp(a, b, n);
}

// szGameName: global game name string expected by savegame/sgin.cc and sgout.cc
char szGameName[] = "WorldFoundry";

// --------------------------------------------------------------------------
// Tasker stubs — needed for link, never called without DO_MULTITASKING
// --------------------------------------------------------------------------
// _procState / SProcState from hal/linux/_procsta.h
// typedef struct _procState { ... } SProcState;
// The mangled function names use the struct tag (_procState), not the typedef.
struct _procState { void* _stackBase; int _stackSize; };
typedef void (voidFunction)(void);

extern "C" void TaskSwitch(void) {
    fprintf(stderr, "TaskSwitch called unexpectedly\n");
    abort();
}

void ProcStateConstruct(_procState* /*self*/, voidFunction* /*routine*/) {
    fprintf(stderr, "ProcStateConstruct called unexpectedly\n");
    abort();
}

void ProcStateDestruct(_procState* /*self*/) {
    fprintf(stderr, "ProcStateDestruct called unexpectedly\n");
    abort();
}

// MessagePortAttachTask — C++ linkage, takes opaque handles
struct _MessagePort;
struct _Task;
void MessagePortAttachTask(_MessagePort* /*port*/, _Task* /*task*/) {
    fprintf(stderr, "MessagePortAttachTask called unexpectedly\n");
    abort();
}
