// scripting_pforth.cc — pForth backend for forth_engine namespace.
//
// Compiled in when WF_FORTH_ENGINE_PFORTH is defined (via build_game.sh).
// Sigil: `\` — handled by ScriptRouter before dispatch here.
//
// *** Why this file uses internal pforth headers ***
//
// pForth's public API (pforth.h) is batch-oriented: pfDoForth() initialises,
// runs, then tears down the interpreter in a single call. There is no public
// "eval a string in a persistent session" entry point. For WF's per-frame
// RunScript pattern we need a persistent session, which requires:
//
//   1. Persistent init — manually replicate pfDoForth's setup phase
//      (pfCreateTask / pfSetCurrentTask / pfBuildDictionary) WITHOUT the
//      teardown phase.  pfInit() is a file-static in pf_core.c so we
//      duplicate its 10-line body using pf_guts.h globals.
//
//   2. String eval — pfDoForth routes interactive input through pfQuit()
//      (a blocking stdin loop) and file input through pfIncludeFile(). To
//      feed a C string we use fmemopen(3) (POSIX.1-2008) to wrap the string
//      as a FILE* and pass it to ffIncludeFile() (declared in pfcompil.h).
//
//   3. Stack result — POP_DATA_STACK and DATA_STACK_DEPTH macros from
//      pf_guts.h give direct access to gCurrentTask's data stack.
//
// pf_all.h pulls in every internal pforth header. It is wrapped in
// extern "C" to suppress C++ name-mangling for the C linkage symbols.
//
// Bridge mechanism: pforth C-Glue (pf_cglue.c / pf_cglue.h).
// - CustomFunctionTable[] holds the C function pointers.
// - CompileCustomFunctions() registers named Forth words that call them.
// - pfcustom.c is compiled with -DPF_USER_CUSTOM=1 to suppress its default
//   test implementations; this file provides the WF implementations instead.
//
// Cell type: cell_t = intptr_t (64-bit on x86-64). Float mailbox values on
// PC dev are truncated to integer. Correct on the real fixed-point target.

#ifdef WF_FORTH_ENGINE_PFORTH

#include "scripting_forth.hp"

extern "C" {
// pf_all.h includes pforth.h (public) plus all internal headers:
// pf_guts.h (globals, DATA_STACK_DEPTH, POP/PUSH_DATA_STACK),
// pfcompil.h (ffInterpret, ffIncludeFile, ffFindC),
// pf_cglue.h (CreateGlueToC, CustomFunctionTable, CompileCustomFunctions),
// pf_io.h   (FileStream = FILE on POSIX).
#include <pf_all.h>
}

#include <scripting/scriptinterpreter.hp>
#include <mailbox/mailbox.hp>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <unistd.h>   // getcwd, chdir

// ---------------------------------------------------------------------------
// Module state

static PForthTask        g_task        = nullptr;
static PForthDictionary  g_dic         = nullptr;
static MailboxesManager* g_mgr         = nullptr;
static int               g_curObj      = 0;

// Path to pforth's system.fth (set at Init; needed for full Forth library).
static std::string       g_system_fth_path;

// ---------------------------------------------------------------------------
// C-Glue bridge functions
//
// These are registered via CompileCustomFunctions / CreateGlueToC. The CFunc
// typedefs (CFunc0, CFunc1, CFunc2) in pf_cglue.h expect cell_t parameters
// and cell_t return values.

// read-mailbox: ( idx -- val )
static cell_t wf_pforth_read_mailbox(cell_t idx)
{
    if (!g_mgr) return 0;
    Mailboxes& mb = g_mgr->LookupMailboxes(g_curObj);
    return (cell_t)(intptr_t)mb.ReadMailbox((int)idx).AsFloat();
}

// write-mailbox: ( val idx -- ) — returns 0 (C_RETURNS_VOID, result ignored)
static cell_t wf_pforth_write_mailbox(cell_t idx, cell_t val)
{
    if (g_mgr) {
        Mailboxes& mb = g_mgr->LookupMailboxes(g_curObj);
        mb.WriteMailbox((int)idx, Scalar::FromFloat((float)(intptr_t)val));
    }
    return 0;
}

// ---------------------------------------------------------------------------
// pForth C-Glue hooks (symbols referenced by pforth kernel / pf_cglue.c)
//
// pfcustom.c is compiled with -DPF_USER_CUSTOM=1 which suppresses its
// default bodies, so this file must provide these three symbols.

extern "C" {

// CustomFunctionTable: indexed by CreateGlueToC / CallUserFunction.
CFunc0 CustomFunctionTable[] = {
    (CFunc0)wf_pforth_read_mailbox,
    (CFunc0)wf_pforth_write_mailbox,
};

// Called at startup on platforms without BSS init; no-op for standard Linux.
Err LoadCustomFunctionTable(void)
{
    CustomFunctionTable[0] = (CFunc0)wf_pforth_read_mailbox;
    CustomFunctionTable[1] = (CFunc0)wf_pforth_write_mailbox;
    return 0;
}

// Called during dictionary build to compile the named Forth glue words.
// Parameters: name (UPPER CASE), index into CustomFunctionTable, return mode,
//             number of cell_t parameters popped from the stack.
Err CompileCustomFunctions(void)
{
    Err err;
    int i = 0;
    err = CreateGlueToC("READ-MAILBOX",  i++, C_RETURNS_VALUE, 1);
    if (err < 0) return err;
    err = CreateGlueToC("WRITE-MAILBOX", i++, C_RETURNS_VOID,  2);
    return err;
}

} // extern "C"

// ---------------------------------------------------------------------------
// forth_engine namespace — public plug interface

namespace forth_engine {

void Init(MailboxesManager& mgr)
{
    g_mgr    = &mgr;
    g_curObj = 0;

    // Locate system.fth relative to this executable's source layout.
    // PFORTH_FTH_DIR is injected by build_game.sh as a -D define.
    // Fallback: look adjacent to the vendor directory.
#ifdef PFORTH_FTH_DIR
    g_system_fth_path = PFORTH_FTH_DIR "/system.fth";
#else
    g_system_fth_path = "";  // will skip system.fth load; only primitives available
#endif

    // ---- Replicate pfInit() (file-static in pf_core.c, cannot be called directly) ----
    // Mirror the exact body of pfInit from pf_core.c:94-116.
    gCurrentTask       = nullptr;
    gCurrentDictionary = nullptr;
    gNumPrimitives     = 0;
    gLocalCompiler_XT  = 0;
    gVarContext        = (cell_t)NULL;
    gVarState          = 0;
    gVarByeCode        = 0;
    gVarEcho           = 0;
    gVarTraceLevel     = 0;
    gVarReturnCode     = 0;
    gIncludeIndex      = 0;
    gVarBase           = 10;                  // decimal numeric base — important
    gDepthAtColon      = DEPTH_AT_COLON_INVALID;
    gVarTraceStack     = 1;
    pfInitMemoryAllocator();                  // no-op unless PF_NO_MALLOC defined

    // Suppress banners/prompts — gVarQuiet is set via pfSetQuiet() normally;
    // write directly since we're doing manual init.
    gVarQuiet = 1;

    // PF_DEFAULT_HEADER_SIZE / PF_DEFAULT_CODE_SIZE are file-scoped #defines
    // in pf_core.c (120000 / 300000 bytes respectively). Replicate here.
#ifndef PF_DEFAULT_HEADER_SIZE
#define PF_DEFAULT_HEADER_SIZE (120000)
#endif
#ifndef PF_DEFAULT_CODE_SIZE
#define PF_DEFAULT_CODE_SIZE   (300000)
#endif

    // ---- Create task and dictionary ----
    g_task = pfCreateTask(512, 512);
    if (!g_task) {
        fprintf(stderr, "pforth: pfCreateTask failed\n");
        return;
    }
    pfSetCurrentTask(g_task);

    // pfBuildDictionary creates the primitive word set (C-level opcodes).
    g_dic = pfBuildDictionary(PF_DEFAULT_HEADER_SIZE, PF_DEFAULT_CODE_SIZE);
    if (!g_dic) {
        fprintf(stderr, "pforth: pfBuildDictionary failed\n");
        pfDeleteTask(g_task);
        g_task = nullptr;
        return;
    }

    // Compile WF mailbox bridge words into the dictionary.
    if (CompileCustomFunctions() < 0) {
        fprintf(stderr, "pforth: CompileCustomFunctions failed\n");
    }

    // Alias lower-case names (pForth names are case-insensitive; CREATE
    // stores upper-case; users may write either case in scripts).
    // These aliases are compiled as thin wrappers.
    // (No-op if case-insensitive lookup already handles them.)

    // Load system.fth to add higher-level words (IF/ELSE/THEN, DO/LOOP,
    // EVALUATE, string words, etc.). Without this only primitives are available.
    //
    // system.fth uses `include loadp4th.fth` (a bare filename, no path),
    // which pforth resolves relative to the current working directory.
    // Temporarily chdir to the fth/ directory so all nested includes work,
    // then restore the original cwd.
    if (!g_system_fth_path.empty()) {
        char orig_cwd[4096] = {};
        getcwd(orig_cwd, sizeof(orig_cwd));

        // Extract the directory part of g_system_fth_path.
        std::string fth_dir = g_system_fth_path.substr(0, g_system_fth_path.rfind('/'));
        if (!fth_dir.empty())
            chdir(fth_dir.c_str());

        ThrowCode r = pfIncludeFile("system.fth");  // bare name, relative to fth_dir

        if (orig_cwd[0])
            chdir(orig_cwd);

        if (r != 0)
            fprintf(stderr, "pforth: warning — system.fth load returned %ld\n", (long)r);
    } else {
        fprintf(stderr, "pforth: PFORTH_FTH_DIR not set — running without system.fth\n");
    }
}

void Shutdown()
{
    if (g_dic) {
        pfDeleteDictionary(g_dic);
        g_dic = nullptr;
    }
    if (g_task) {
        pfDeleteTask(g_task);
        g_task = nullptr;
    }
    g_mgr    = nullptr;
    g_curObj = 0;
}

void AddConstantArray(IntArrayEntry* entryList)
{
    if (!g_task) return;
    // Eval each constant as `N CONSTANT FOO` via ffInterpret + TIB.
    // pForth names are upper-case; scripts may use either case.
    char buf[256];
    for (IntArrayEntry* p = entryList; p->name; p++) {
        // Write the constant definition into the TIB and interpret it.
        int len = snprintf(buf, sizeof(buf), "%d constant %s\n", p->value, p->name);
        memcpy(gCurrentTask->td_TIB, buf, (size_t)len + 1);
        gCurrentTask->td_SourcePtr = gCurrentTask->td_TIB;
        gCurrentTask->td_SourceNum = len;
        gCurrentTask->td_IN        = 0;
        ThrowCode r = ffInterpret();
        if (r != 0)
            fprintf(stderr, "pforth: failed to define constant %s: %ld\n", p->name, (long)r);
    }
}

void DeleteConstantArray(IntArrayEntry* /*entryList*/)
{
    // pForth dictionary is append-only; constants persist.
}

float RunScript(const char* src, int objectIndex)
{
    if (!g_task || !src || !*src) return 0.0f;

    g_curObj = objectIndex;

    // Skip the `\ wf` sigil line. pForth understands `\` as a line comment
    // word (defined in system.fth). If system.fth was loaded it works; if
    // not, stripping manually is safer.
    while (*src && *src != '\n') ++src;
    if (*src == '\n') ++src;
    if (!*src) return 0.0f;

    // Wrap the script string as a FILE* using fmemopen (POSIX.1-2008).
    // ffIncludeFile manages its own TIB + include-frame state, so multiple
    // nested includes are handled correctly.
    size_t len = strlen(src);
    // fmemopen needs a mutable buffer; copy to avoid const-cast.
    std::string buf(src, len);
    buf += "\n";  // ensure final newline so the last line is parsed
    FILE* mf = fmemopen(buf.data(), buf.size(), "r");
    if (!mf) {
        fprintf(stderr, "pforth: fmemopen failed\n");
        return 0.0f;
    }

    ThrowCode r = ffIncludeFile(mf);  // also closes mf
    if (r != 0) {
        fprintf(stderr, "pforth error %ld: %.120s\n", (long)r, src);
        return 0.0f;
    }

    // Return TOS as float if stack is non-empty.
    if (DATA_STACK_DEPTH > 0) {
        cell_t top = POP_DATA_STACK;
        return (float)(intptr_t)top;
    }
    return 0.0f;
}

} // namespace forth_engine

#endif // WF_FORTH_ENGINE_PFORTH
