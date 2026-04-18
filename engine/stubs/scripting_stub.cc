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
#include "scripting_lua.hp"
#include "scripting_forth.hp"
#include "scripting_wren.hp"
#include "scripting_js.hp"
#include "scripting_wamr.hp"
#include "physics_jolt.hp"

#include <cstdio>
#include <string>
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
#ifdef WF_ENABLE_LUA
    lua_engine::Init(mgr);
#endif
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
#ifdef WF_ENABLE_LUA
    lua_engine::Shutdown();
#endif
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
    if (!kDispatch[language])
    {
        // Requested engine isn't compiled in for this build (e.g. Lua on the
        // Forth-only Android build). Graceful no-op — callers like game.cc's
        // meta-script path + level.cc's shell path hardcode language=0, and
        // skipping them lets the game continue; the director + per-actor
        // scripts keep running under whichever engine(s) are compiled in.
        static bool s_warned[std::size(kDispatch)] = {};
        if (!s_warned[language])
        {
            s_warned[language] = true;
            cerror << "ScriptRouter: engine for language " << language
                   << " not compiled in; skipping script (warned once)"
                   << std::endl;
        }
        return Scalar::FromFloat(0.0f);
    }
    return Scalar::FromFloat(kDispatch[language](src, objectIndex));
}

void ScriptRouter::AddConstantArray(IntArrayEntry* entryList)
{
#ifdef WF_WITH_FORTH
    forth_engine::AddConstantArray(entryList);
#endif
#ifdef WF_ENABLE_LUA
    lua_engine::AddConstantArray(entryList);
#endif
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
#ifdef WF_ENABLE_LUA
    lua_engine::DeleteConstantArray(entryList);
#endif
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
