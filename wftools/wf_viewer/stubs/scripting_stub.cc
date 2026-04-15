// scripting_stub.cc — ScriptRouter: neutral sigil dispatcher + per-engine plugs.
//
// ScriptRouter owns the lifecycle of all compiled-in scripting engines as peers:
//   Lua 5.4 (+ optional Fennel sub-dispatch, handled inside lua_engine)
//   JavaScript  (QuickJS or JerryScript, via scripting_js.hp)
//   WebAssembly (wasm3, via scripting_wasm3.hp)
//
// None of these engines is the "parent" of any other. Sigil dispatch lives
// here in ScriptRouter::RunScript; each engine only sees scripts intended
// for it. ScriptInterpreterFactory returns a ScriptRouter.

#include <scripting/scriptinterpreter.hp>
#include <math/scalar.hp>
#include "scripting_js.hp"
#include "scripting_wasm3.hp"

extern "C" {
#include <lua.h>
#include <lualib.h>
#include <lauxlib.h>
}

#include <cstdio>

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

    Scalar RunScript(const void* /*script*/, int /*objectIndex*/) override
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
static int         gFennelEvalRef  = LUA_NOREF;
static MailboxesManager* gMailboxes = nullptr;

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
    std::fprintf(stderr, "  lua read_mailbox(%ld, actor=%d) -> %g\n",
                 mailbox, actorIdx, (double)v.AsFloat());
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
    std::fprintf(stderr, "  lua write_mailbox(%ld, %g, actor=%d)\n",
                 mailbox, value, actorIdx);
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
    luaL_openlibs(gL);

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
        lua_pop(gL, 1);  // pop fennel module
        std::fprintf(stderr, "fennel: loaded (%u bytes embedded)\n", kFennelSourceLen);
    }
#endif
}

void Shutdown()
{
    if (gL) {
        lua_close(gL);
        gL = nullptr;
    }
    gMailboxes = nullptr;
    gFennelEvalRef = LUA_NOREF;
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

#ifdef WF_ENABLE_FENNEL
    if (gFennelEvalRef != LUA_NOREF) {
        const char* p = src;
        while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n') p++;
        if (*p == ';') {
            lua_rawgeti(gL, LUA_REGISTRYINDEX, gFennelEvalRef);
            lua_pushstring(gL, src);
            if (lua_pcall(gL, 1, 1, 0) != LUA_OK) {
                std::fprintf(stderr, "fennel error: %s\n  script: %s\n",
                             lua_tostring(gL, -1), src);
                lua_pop(gL, 1);
                return 0.0f;
            }
            double result = lua_isnumber(gL, -1) ? lua_tonumber(gL, -1) : 0.0;
            lua_settop(gL, 0);
            return static_cast<float>(result);
        }
    }
#endif

    if (luaL_dostring(gL, src) != LUA_OK) {
        const char* err = lua_tostring(gL, -1);
        std::fprintf(stderr, "lua error: %s\n", err ? err : "(unknown)");
        std::fprintf(stderr, "  script: %s\n", src);
        lua_pop(gL, 1);
        return 0.0f;
    }
    double result = 0.0;
    if (lua_gettop(gL) > 0 && lua_isnumber(gL, -1))
        result = lua_tonumber(gL, -1);
    lua_settop(gL, 0);
    return static_cast<float>(result);
}

} // namespace lua_engine

//=============================================================================
// ScriptRouter — neutral dispatcher; all engines are peers.

class ScriptRouter : public ScriptInterpreter
{
public:
    ScriptRouter(MailboxesManager& mgr);
    ~ScriptRouter() override;

    Scalar RunScript(const void* script, int objectIndex) override;
    void   AddConstantArray(IntArrayEntry* entryList) override;
    void   DeleteConstantArray(IntArrayEntry* entryList) override;
};

ScriptRouter::ScriptRouter(MailboxesManager& mgr)
    : ScriptInterpreter(mgr)
{
    lua_engine::Init(mgr);
#ifdef WF_WITH_JS
    JsRuntimeInit(mgr);
#endif
#ifdef WF_WITH_WASM
    Wasm3RuntimeInit(mgr);
#endif
    AddConstantArray(mailboxIndexArray);
    AddConstantArray(joystickArray);
}

ScriptRouter::~ScriptRouter()
{
    DeleteConstantArray(joystickArray);
    DeleteConstantArray(mailboxIndexArray);
#ifdef WF_WITH_WASM
    Wasm3RuntimeShutdown();
#endif
#ifdef WF_WITH_JS
    JsRuntimeShutdown();
#endif
    lua_engine::Shutdown();
}

Scalar ScriptRouter::RunScript(const void* script, int objectIndex)
{
    const char* src = static_cast<const char*>(script);
    if (!src || !*src) return Scalar::FromFloat(0.0f);

    const char* p = src;
    while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n') p++;

#ifdef WF_WITH_JS
    // `//` → JavaScript. `//` is a Lua syntax error so no collision.
    if (p[0] == '/' && p[1] == '/')
        return Scalar::FromFloat(JsRunScript(src, objectIndex));
#endif

#ifdef WF_WITH_WASM
    // `#b64\n` → wasm3 (base64-encoded module). Bare `#` not claimed here
    // because cd.iff TCL fragments use `##` line comments.
    if (p[0] == '#' && p[1] == 'b' && p[2] == '6' && p[3] == '4' && p[4] == '\n')
        return Scalar::FromFloat(Wasm3RunScript(src, objectIndex));
#endif

    // Fallthrough → Lua engine (handles bare Lua and `;`-prefixed Fennel internally).
    return Scalar::FromFloat(lua_engine::RunScript(src, objectIndex));
}

void ScriptRouter::AddConstantArray(IntArrayEntry* entryList)
{
    lua_engine::AddConstantArray(entryList);
#ifdef WF_WITH_JS
    JsAddConstantArray(entryList);
#endif
#ifdef WF_WITH_WASM
    Wasm3AddConstantArray(entryList);
#endif
}

void ScriptRouter::DeleteConstantArray(IntArrayEntry* entryList)
{
    lua_engine::DeleteConstantArray(entryList);
#ifdef WF_WITH_JS
    JsDeleteConstantArray(entryList);
#endif
#ifdef WF_WITH_WASM
    Wasm3DeleteConstantArray(entryList);
#endif
}

//=============================================================================

ScriptInterpreter* ScriptInterpreterFactory(MailboxesManager& mailboxesManager, Memory& memory)
{
    return new (memory) ScriptRouter(mailboxesManager);
}
