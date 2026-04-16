// scripting_stub.cc — ScriptRouter: neutral sigil dispatcher + per-engine plugs.
//
// ScriptRouter owns the lifecycle of all compiled-in scripting engines as peers:
//   Lua 5.4 (+ optional Fennel sub-dispatch, handled inside lua_engine)
//   JavaScript  (QuickJS or JerryScript, via scripting_js.hp)
//   WebAssembly (wasm3 or WAMR; exactly one selected by WF_WASM_ENGINE)
//   Wren        (via scripting_wren.hp)
//   Forth       (zForth/ficl/…, via scripting_forth.hp)
//
// None of these engines is the "parent" of any other. Sigil dispatch lives
// here in ScriptRouter::RunScript; each engine only sees scripts intended
// for it. ScriptInterpreterFactory returns a ScriptRouter.

#include <scripting/scriptinterpreter.hp>
#include <math/scalar.hp>
#include "scripting_forth.hp"
#include "scripting_wren.hp"
#include "scripting_js.hp"
#include "scripting_wasm3.hp"
#include "scripting_wamr.hp"
#include "physics_jolt.hp"

extern "C" {
#include <lua.h>
#include <lualib.h>
#include <lauxlib.h>
}

#include <cstdio>
#include <unordered_map>

//=============================================================================
// Base-class implementations (formerly in scripting/scriptinterpreter.cc)

ScriptInterpreter::ScriptInterpreter(MailboxesManager& manager)
    : _mailboxesManager(manager)
{
}

ScriptInterpreter::~ScriptInterpreter()
{
}

void ScriptInterpreter::Validate()
{
}

void ScriptInterpreter::AddConstantArray(IntArrayEntry* /*entryList*/)
{
}

void ScriptInterpreter::DeleteConstantArray(IntArrayEntry* /*entryList*/)
{
}

//=============================================================================
// NullInterpreter — no-op fallback.

class NullInterpreter : public ScriptInterpreter
{
public:
    NullInterpreter(MailboxesManager& mgr) : ScriptInterpreter(mgr) {}
    ~NullInterpreter() {}

    Scalar RunScript(const void* /*script*/, int /*objectIndex*/, int /*language*/) override
    {
        return Scalar::FromFloat(0.0f);
    }
};

//=============================================================================
// Constant arrays — shared across all engines via AddConstantArray broadcast.

static IntArrayEntry mailboxIndexArray[] =
{
#define Comment(val)
#define MAILBOXENTRY(name,value)  { "INDEXOF_" #name, value },
#include <mailbox/mailbox.inc>
    { NULL, 0 }
};
#undef MAILBOXENTRY
#undef Comment

static IntArrayEntry joystickArray[] =
{
    { "JOYSTICK_BUTTON_UP",    2048 },
    { "JOYSTICK_BUTTON_DOWN",  4096 },
    { "JOYSTICK_BUTTON_RIGHT", 8192 },
    { "JOYSTICK_BUTTON_LEFT",  16384 },
    { "JOYSTICK_BUTTON_A", 1 },
    { "JOYSTICK_BUTTON_B", 2 },
    { "JOYSTICK_BUTTON_C", 4 },
    { "JOYSTICK_BUTTON_D", 8 },
    { "JOYSTICK_BUTTON_E", 16 },
    { "JOYSTICK_BUTTON_F", 32 },
    { "JOYSTICK_BUTTON_G", 64 },
    { "JOYSTICK_BUTTON_H", 128 },
    { "JOYSTICK_BUTTON_I", 256 },
    { "JOYSTICK_BUTTON_J", 512 },
    { "JOYSTICK_BUTTON_K", 1024 },
    { NULL, 0 }
};

//=============================================================================
// lua_engine — Lua 5.4 plug (+ optional Fennel sub-dispatch).
//
// Internal to this TU; not exposed via any header. ScriptRouter calls these
// five functions directly. Fennel lives here because it compiles to Lua and
// shares the lua_State; it is not a peer engine at the router level.

namespace lua_engine {

// --------------------------------------------------------------------------
// State

static lua_State*  gL              = nullptr;
static int         gCurrentObject  = 0;
static int         gFennelEvalRef     = LUA_NOREF;
static int         gFennelCompileRef  = LUA_NOREF;
static MailboxesManager* gMailboxes = nullptr;
// Compilation cache: script pointer → registry ref of compiled lua_Function.
// Keys are raw pointers into the level IFF block (stable for level lifetime).
static std::unordered_map<const char*, int> gScriptRefs;
// Per-actor environment tables: objectIndex → registry ref.
// Each actor gets its own _ENV that chains to shared globals via __index,
// so INDEXOF_* constants and read_mailbox/write_mailbox remain visible while
// actor-local writes stay isolated.
static std::unordered_map<int, int> gActorEnvRefs;
// Per-actor live coroutine threads: objectIndex → registry ref of lua_State*.
// Present only while the coroutine is suspended (LUA_YIELD). Cleared on
// LUA_OK (finished) or error.
static std::unordered_map<int, int> gActorThreadRefs;

// --------------------------------------------------------------------------
// C closures — read_mailbox / write_mailbox

static int lua_read_mailbox(lua_State* L)
{
    long mailbox  = static_cast<long>(luaL_checkinteger(L, 1));
    int  actorIdx = gCurrentObject;
    if (lua_gettop(L) >= 2)
        actorIdx = static_cast<int>(luaL_checkinteger(L, 2));
    Mailboxes& mb = gMailboxes->LookupMailboxes(actorIdx);
    Scalar v = mb.ReadMailbox(mailbox);
#ifdef WF_SCRIPT_DEBUG
    std::fprintf(stderr, "  lua read_mailbox(%ld, actor=%d) -> %g\n",
                 mailbox, actorIdx, (double)v.AsFloat());
#endif
    lua_pushnumber(L, v.AsFloat());
    return 1;
}

static int lua_write_mailbox(lua_State* L)
{
    long   mailbox  = static_cast<long>(luaL_checkinteger(L, 1));
    double value    = luaL_checknumber(L, 2);
    int    actorIdx = gCurrentObject;
    if (lua_gettop(L) >= 3)
        actorIdx = static_cast<int>(luaL_checkinteger(L, 3));
    Mailboxes& mb = gMailboxes->LookupMailboxes(actorIdx);
#ifdef WF_SCRIPT_DEBUG
    std::fprintf(stderr, "  lua write_mailbox(%ld, %g, actor=%d)\n",
                 mailbox, value, actorIdx);
#endif
    mb.WriteMailbox(mailbox, Scalar::FromFloat(static_cast<float>(value)));
    return 0;
}

#ifdef WF_ENABLE_FENNEL
extern "C" const char         kFennelSource[];
extern "C" const unsigned int kFennelSourceLen;
#endif

// --------------------------------------------------------------------------
// Public plug interface

void Init(MailboxesManager& mgr)
{
    gMailboxes = &mgr;
    gL = luaL_newstate();

    // Open only safe standard libraries — io and os are excluded.
    // package is included because Fennel uses package.loaded for module
    // registration; without it Fennel fails to initialise.
    static const luaL_Reg kSafeLibs[] = {
        { LUA_GNAME,        luaopen_base      },
        { LUA_LOADLIBNAME,  luaopen_package   },
        { LUA_STRLIBNAME,   luaopen_string    },
        { LUA_MATHLIBNAME,  luaopen_math      },
        { LUA_TABLIBNAME,   luaopen_table     },
        { LUA_UTF8LIBNAME,  luaopen_utf8      },
        { LUA_COLIBNAME,    luaopen_coroutine },
        { NULL, NULL }
    };
    for (const luaL_Reg* lib = kSafeLibs; lib->func; lib++) {
        luaL_requiref(gL, lib->name, lib->func, 1);
        lua_pop(gL, 1);
    }

    lua_pushcfunction(gL, lua_read_mailbox);
    lua_setglobal(gL, "read_mailbox");

    lua_pushcfunction(gL, lua_write_mailbox);
    lua_setglobal(gL, "write_mailbox");

#ifdef WF_ENABLE_FENNEL
    if (luaL_loadbuffer(gL, kFennelSource, kFennelSourceLen, "fennel.lua") != LUA_OK
        || lua_pcall(gL, 0, 1, 0) != LUA_OK) {
        std::fprintf(stderr, "fennel: load failed: %s\n", lua_tostring(gL, -1));
        lua_pop(gL, 1);
    } else {
        lua_getfield(gL, -1, "eval");
        gFennelEvalRef = luaL_ref(gL, LUA_REGISTRYINDEX);
        lua_getfield(gL, -1, "compileString");
        gFennelCompileRef = luaL_ref(gL, LUA_REGISTRYINDEX);
        lua_pop(gL, 1);  // pop fennel module
        std::fprintf(stderr, "fennel: loaded (%u bytes embedded)\n", kFennelSourceLen);
    }
#endif
}

// Return the registry ref for objectIndex's environment table, creating it
// on first use. The env table has a metatable with __index = _G so that
// shared globals (INDEXOF_*, read_mailbox, etc.) fall through, while
// actor-local writes stay in the per-actor table.
static int GetOrCreateActorEnv(int objectIndex)
{
    auto it = gActorEnvRefs.find(objectIndex);
    if (it != gActorEnvRefs.end())
        return it->second;

    lua_newtable(gL);               // env table
    lua_newtable(gL);               // metatable
    lua_pushglobaltable(gL);
    lua_setfield(gL, -2, "__index");
    lua_setmetatable(gL, -2);
    int ref = luaL_ref(gL, LUA_REGISTRYINDEX);
    gActorEnvRefs[objectIndex] = ref;
    return ref;
}

// Resume an active coroutine thread for objectIndex.
// Reads the yield/return value from the thread stack.
// Clears the thread ref from gActorThreadRefs on LUA_OK or error.
static float ResumeThread(int objectIndex, int threadRef, lua_State* thread)
{
    int nresults = 0;
    int status = lua_resume(thread, gL, 0, &nresults);
    double result = 0.0;

    if (status == LUA_YIELD) {
        if (nresults > 0 && lua_isnumber(thread, -1))
            result = lua_tonumber(thread, -1);
        lua_settop(thread, 0);
    } else if (status == LUA_OK) {
        if (nresults > 0 && lua_isnumber(thread, -1))
            result = lua_tonumber(thread, -1);
        lua_settop(thread, 0);
        luaL_unref(gL, LUA_REGISTRYINDEX, threadRef);
        gActorThreadRefs.erase(objectIndex);
    } else {
        std::fprintf(stderr, "lua coroutine error (actor %d): %s\n",
                     objectIndex, lua_tostring(thread, -1));
        lua_settop(thread, 0);
        luaL_unref(gL, LUA_REGISTRYINDEX, threadRef);
        gActorThreadRefs.erase(objectIndex);
    }
    return static_cast<float>(result);
}

// After a successful lua_pcall, inspect the top-of-stack return value.
// If it is a coroutine thread, store it and do the first resume.
// Otherwise treat it as a number (or 0 if not numeric).
static float HandlePCallResult(int objectIndex)
{
    if (lua_gettop(gL) > 0 && lua_type(gL, -1) == LUA_TTHREAD) {
        lua_State* thread = lua_tothread(gL, -1);
        int threadRef = luaL_ref(gL, LUA_REGISTRYINDEX);  // pops thread from gL
        gActorThreadRefs[objectIndex] = threadRef;
        return ResumeThread(objectIndex, threadRef, thread);
    }
    double result = (lua_gettop(gL) > 0 && lua_isnumber(gL, -1))
                    ? lua_tonumber(gL, -1) : 0.0;
    lua_settop(gL, 0);
    return static_cast<float>(result);
}

void Shutdown()
{
    if (gL) {
        for (auto& kv : gScriptRefs)
            luaL_unref(gL, LUA_REGISTRYINDEX, kv.second);
        for (auto& kv : gActorEnvRefs)
            luaL_unref(gL, LUA_REGISTRYINDEX, kv.second);
        for (auto& kv : gActorThreadRefs)
            luaL_unref(gL, LUA_REGISTRYINDEX, kv.second);
        lua_close(gL);
        gL = nullptr;
    }
    gScriptRefs.clear();
    gActorEnvRefs.clear();
    gActorThreadRefs.clear();
    gMailboxes = nullptr;
    gFennelEvalRef    = LUA_NOREF;
    gFennelCompileRef = LUA_NOREF;
}

void AddConstantArray(IntArrayEntry* entryList)
{
    for (IntArrayEntry* p = entryList; p->name; p++) {
        lua_pushinteger(gL, p->value);
        lua_setglobal(gL, p->name);
    }
}

void DeleteConstantArray(IntArrayEntry* entryList)
{
    for (IntArrayEntry* p = entryList; p->name; p++) {
        lua_pushnil(gL);
        lua_setglobal(gL, p->name);
    }
}

float RunScript(const char* src, int objectIndex)
{
    gCurrentObject = objectIndex;
    if (!src || !*src) return 0.0f;

    // If this actor has a live coroutine, resume it instead of re-calling.
    {
        auto tit = gActorThreadRefs.find(objectIndex);
        if (tit != gActorThreadRefs.end()) {
            lua_rawgeti(gL, LUA_REGISTRYINDEX, tit->second);
            lua_State* thread = lua_tothread(gL, -1);
            lua_pop(gL, 1);
            return ResumeThread(objectIndex, tit->second, thread);
        }
    }

#ifdef WF_ENABLE_FENNEL
    if (gFennelCompileRef != LUA_NOREF) {
        const char* p = src;
        while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n') p++;
        if (*p == ';') {
            // Fennel path: compile to Lua once, cache by pointer, then call
            // exactly like the Lua path (with per-actor _ENV).
            int fenRef;
            auto fit = gScriptRefs.find(src);
            if (fit != gScriptRefs.end()) {
                fenRef = fit->second;
            } else {
                lua_rawgeti(gL, LUA_REGISTRYINDEX, gFennelCompileRef);
                lua_pushstring(gL, src);
                if (lua_pcall(gL, 1, 1, 0) != LUA_OK) {
                    std::fprintf(stderr, "fennel compile error: %s\n  script: %.120s\n",
                                 lua_tostring(gL, -1), src);
                    lua_pop(gL, 1);
                    return 0.0f;
                }
                // Stack top: Lua source string from fennel.compileString
                size_t luaSrcLen;
                const char* luaSrc = lua_tolstring(gL, -1, &luaSrcLen);
                if (luaL_loadbuffer(gL, luaSrc, luaSrcLen, src) != LUA_OK) {
                    std::fprintf(stderr, "fennel→lua load error: %s\n",
                                 lua_tostring(gL, -1));
                    lua_pop(gL, 2);  // error + lua src string
                    return 0.0f;
                }
                lua_remove(gL, -2);  // pop lua src string; keep function
                fenRef = luaL_ref(gL, LUA_REGISTRYINDEX);
                gScriptRefs[src] = fenRef;
            }

            lua_rawgeti(gL, LUA_REGISTRYINDEX, fenRef);
            int envRef = GetOrCreateActorEnv(objectIndex);
            lua_rawgeti(gL, LUA_REGISTRYINDEX, envRef);
            lua_setupvalue(gL, -2, 1);
            if (lua_pcall(gL, 0, 1, 0) != LUA_OK) {
                std::fprintf(stderr, "fennel error: %s\n  script: %.120s\n",
                             lua_tostring(gL, -1), src);
                lua_pop(gL, 1);
                return 0.0f;
            }
            return HandlePCallResult(objectIndex);
        }
    }
#endif

    // Look up or compile the script.
    int fnRef;
    auto it = gScriptRefs.find(src);
    if (it != gScriptRefs.end()) {
        fnRef = it->second;
    } else {
        if (luaL_loadstring(gL, src) != LUA_OK) {
            std::fprintf(stderr, "lua compile error: %s\n  script: %.120s\n",
                         lua_tostring(gL, -1), src);
            lua_pop(gL, 1);
            return 0.0f;
        }
        fnRef = luaL_ref(gL, LUA_REGISTRYINDEX);
        gScriptRefs[src] = fnRef;
    }

    // Push compiled function, then swap in the per-actor _ENV upvalue.
    lua_rawgeti(gL, LUA_REGISTRYINDEX, fnRef);
    int envRef = GetOrCreateActorEnv(objectIndex);
    lua_rawgeti(gL, LUA_REGISTRYINDEX, envRef);
    lua_setupvalue(gL, -2, 1);  // upvalue 1 is always _ENV in Lua 5.4

    if (lua_pcall(gL, 0, 1, 0) != LUA_OK) {
        std::fprintf(stderr, "lua error: %s\n  script: %.120s\n",
                     lua_tostring(gL, -1), src);
        lua_pop(gL, 1);
        return 0.0f;
    }
    return HandlePCallResult(objectIndex);
}

} // namespace lua_engine

//=============================================================================
// fennel_engine — thin shim; Fennel evaluation lives inside lua_engine.
//
// The lua_engine Fennel path is triggered by a leading ';' sigil.  This
// wrapper ensures the sigil is present so scripts without the sigil (i.e.
// after the one-time migration pass) still hit the Fennel path.

#ifdef WF_ENABLE_FENNEL
namespace fennel_engine {

float RunScript(const char* src, int objectIndex)
{
    static thread_local std::string buf;
    const char* p = src;
    while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n') p++;
    if (*p == ';')
        return lua_engine::RunScript(src, objectIndex);
    buf = "; ";
    buf += src;
    return lua_engine::RunScript(buf.c_str(), objectIndex);
}

} // namespace fennel_engine
#endif

//=============================================================================
// ScriptRouter — neutral dispatcher; all engines are peers.

class ScriptRouter : public ScriptInterpreter
{
public:
    ScriptRouter(MailboxesManager& mgr);
    ~ScriptRouter() override;

    Scalar RunScript(const void* script, int objectIndex, int language) override;
    void   AddConstantArray(IntArrayEntry* entryList) override;
    void   DeleteConstantArray(IntArrayEntry* entryList) override;
};

ScriptRouter::ScriptRouter(MailboxesManager& mgr)
    : ScriptInterpreter(mgr)
{
#ifdef WF_WITH_FORTH
    forth_engine::Init(mgr);
#endif
    lua_engine::Init(mgr);
#ifdef WF_ENABLE_WREN
    wren_engine::Init(mgr);
#endif
#ifdef WF_WITH_JS
    js_engine::Init(mgr);
#endif
#ifdef WF_WITH_WASM
#  ifdef WF_WASM_ENGINE_WAMR
    wamr_engine::Init(mgr);
#  else
    wasm3_engine::Init(mgr);
#  endif
#endif
    AddConstantArray(mailboxIndexArray);
    AddConstantArray(joystickArray);
}

ScriptRouter::~ScriptRouter()
{
    DeleteConstantArray(joystickArray);
    DeleteConstantArray(mailboxIndexArray);
#ifdef WF_WITH_WASM
#  ifdef WF_WASM_ENGINE_WAMR
    wamr_engine::Shutdown();
#  else
    wasm3_engine::Shutdown();
#  endif
#endif
#ifdef WF_WITH_JS
    js_engine::Shutdown();
#endif
#ifdef WF_ENABLE_WREN
    wren_engine::Shutdown();
#endif
    lua_engine::Shutdown();
#ifdef WF_WITH_FORTH
    forth_engine::Shutdown();
#endif
}

Scalar ScriptRouter::RunScript(const void* script, int objectIndex, int language)
{
    const char* src = static_cast<const char*>(script);
    if (!src || !*src) return Scalar::FromFloat(0.0f);

    // language enum: 0=Lua 1=Fennel 2=Wren 3=Forth 4=JS 5=Wasm
    // Slots for engines not compiled in are null; assert rather than crash.
    using RunFn = float(*)(const char*, int);
    static const RunFn kDispatch[] = {
#ifdef WF_ENABLE_LUA
        /* 0 lua    */ lua_engine::RunScript,
#else
        /* 0 lua    */ nullptr,
#endif
#ifdef WF_ENABLE_FENNEL
        /* 1 fennel */ fennel_engine::RunScript,
#else
        /* 1 fennel */ nullptr,
#endif
#ifdef WF_ENABLE_WREN
        /* 2 wren   */ wren_engine::RunScript,
#else
        /* 2 wren   */ nullptr,
#endif
#ifdef WF_WITH_FORTH
        /* 3 forth  */ forth_engine::RunScript,
#else
        /* 3 forth  */ nullptr,
#endif
#ifdef WF_WITH_JS
        /* 4 js     */ js_engine::RunScript,
#else
        /* 4 js     */ nullptr,
#endif
#ifdef WF_WITH_WASM
#  ifdef WF_WASM_ENGINE_WAMR
        /* 5 wasm   */ wamr_engine::RunScript,
#  else
        /* 5 wasm   */ wasm3_engine::RunScript,
#  endif
#else
        /* 5 wasm   */ nullptr,
#endif
    };

    RangeCheck(0, language, std::size(kDispatch));
    AssertMsg(kDispatch[language], "script engine not compiled in for language " << language);
    return Scalar::FromFloat(kDispatch[language](src, objectIndex));
}

void ScriptRouter::AddConstantArray(IntArrayEntry* entryList)
{
#ifdef WF_WITH_FORTH
    forth_engine::AddConstantArray(entryList);
#endif
    lua_engine::AddConstantArray(entryList);
#ifdef WF_ENABLE_WREN
    wren_engine::AddConstantArray(entryList);
#endif
#ifdef WF_WITH_JS
    js_engine::AddConstantArray(entryList);
#endif
#ifdef WF_WITH_WASM
#  ifdef WF_WASM_ENGINE_WAMR
    wamr_engine::AddConstantArray(entryList);
#  else
    wasm3_engine::AddConstantArray(entryList);
#  endif
#endif
}

void ScriptRouter::DeleteConstantArray(IntArrayEntry* entryList)
{
#ifdef WF_WITH_FORTH
    forth_engine::DeleteConstantArray(entryList);
#endif
    lua_engine::DeleteConstantArray(entryList);
#ifdef WF_ENABLE_WREN
    wren_engine::DeleteConstantArray(entryList);
#endif
#ifdef WF_WITH_JS
    js_engine::DeleteConstantArray(entryList);
#endif
#ifdef WF_WITH_WASM
#  ifdef WF_WASM_ENGINE_WAMR
    wamr_engine::DeleteConstantArray(entryList);
#  else
    wasm3_engine::DeleteConstantArray(entryList);
#  endif
#endif
}

//=============================================================================

ScriptInterpreter* ScriptInterpreterFactory(MailboxesManager& mailboxesManager, Memory& memory)
{
    return new (memory) ScriptRouter(mailboxesManager);
}
