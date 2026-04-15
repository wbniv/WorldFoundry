// scripting_quickjs.cc — QuickJS back-end for the LuaInterpreter `//` sigil.
//
// Only compiled when WF_JS_ENGINE_QUICKJS is defined. Exposes the same
// read_mailbox / write_mailbox callbacks and INDEXOF_* / JOYSTICK_BUTTON_*
// globals the Lua side publishes, so an author can port a Lua script to JS
// by hand with no API drift.

#include "scripting_js.hp"

#ifdef WF_JS_ENGINE_QUICKJS

#include <mailbox/mailbox.hp>
#include <math/scalar.hp>
#include <scripting/scriptinterpreter.hp>  // IntArrayEntry

extern "C" {
#include "quickjs.h"
}

#include <cstdio>
#include <cstring>
#include <cmath>

namespace {

JSRuntime*        gRt       = nullptr;
JSContext*        gCtx      = nullptr;
MailboxesManager* gMgr      = nullptr;
int               gCurObj   = 0;

JSValue js_read_mailbox(JSContext* ctx, JSValueConst, int argc, JSValueConst* argv)
{
    if (argc < 1) return JS_EXCEPTION;
    int32_t mailbox = 0;
    if (JS_ToInt32(ctx, &mailbox, argv[0]) < 0) return JS_EXCEPTION;
    int32_t actor = gCurObj;
    if (argc >= 2) {
        if (JS_ToInt32(ctx, &actor, argv[1]) < 0) return JS_EXCEPTION;
    }
    Mailboxes& mb = gMgr->LookupMailboxes(actor);
    Scalar v = mb.ReadMailbox(mailbox);
    std::fprintf(stderr, "  qjs read_mailbox(%d, actor=%d) -> %g\n",
                 mailbox, actor, (double)v.AsFloat());
    return JS_NewFloat64(ctx, (double)v.AsFloat());
}

JSValue js_write_mailbox(JSContext* ctx, JSValueConst, int argc, JSValueConst* argv)
{
    if (argc < 2) return JS_EXCEPTION;
    int32_t mailbox = 0;
    if (JS_ToInt32(ctx, &mailbox, argv[0]) < 0) return JS_EXCEPTION;
    double value = 0.0;
    if (JS_ToFloat64(ctx, &value, argv[1]) < 0) return JS_EXCEPTION;
    int32_t actor = gCurObj;
    if (argc >= 3) {
        if (JS_ToInt32(ctx, &actor, argv[2]) < 0) return JS_EXCEPTION;
    }
    Mailboxes& mb = gMgr->LookupMailboxes(actor);
    std::fprintf(stderr, "  qjs write_mailbox(%d, %g, actor=%d)\n",
                 mailbox, value, actor);
    mb.WriteMailbox(mailbox, Scalar::FromFloat((float)value));
    return JS_UNDEFINED;
}

void set_global_fn(const char* name, JSCFunction* fn, int argc)
{
    JSValue global = JS_GetGlobalObject(gCtx);
    JS_SetPropertyStr(gCtx, global, name, JS_NewCFunction(gCtx, fn, name, argc));
    JS_FreeValue(gCtx, global);
}

void log_exception(const char* where)
{
    JSValue exc = JS_GetException(gCtx);
    const char* msg = JS_ToCString(gCtx, exc);
    std::fprintf(stderr, "qjs %s: %s\n", where, msg ? msg : "(unknown)");
    if (msg) JS_FreeCString(gCtx, msg);
    JSValue stack = JS_GetPropertyStr(gCtx, exc, "stack");
    if (!JS_IsUndefined(stack)) {
        const char* s = JS_ToCString(gCtx, stack);
        if (s) {
            std::fprintf(stderr, "%s\n", s);
            JS_FreeCString(gCtx, s);
        }
    }
    JS_FreeValue(gCtx, stack);
    JS_FreeValue(gCtx, exc);
}

} // namespace

void js_engine::Init(MailboxesManager& mgr)
{
    gMgr = &mgr;
    gRt  = JS_NewRuntime();
    gCtx = JS_NewContext(gRt);
    set_global_fn("read_mailbox",  js_read_mailbox,  2);
    set_global_fn("write_mailbox", js_write_mailbox, 3);
    std::fprintf(stderr, "quickjs: runtime initialised\n");

    // One-shot smoke test (per plan §Verification step 2). Cheap, runs once at
    // boot, makes a JS-on/JS-off regression visible in stderr without needing
    // an IFF patch. Drop after the JS path has shipped to a level script.
    {
        const char* s1 = "// js smoke 1\n1 + 2";
        float r1 = js_engine::RunScript(s1, 0);
        std::fprintf(stderr, "quickjs smoke: 1+2 -> %g (expect 3)\n", (double)r1);
    }
}

void js_engine::Shutdown()
{
    if (gCtx) { JS_FreeContext(gCtx); gCtx = nullptr; }
    if (gRt)  { JS_FreeRuntime(gRt);  gRt  = nullptr; }
    gMgr = nullptr;
}

void js_engine::AddConstantArray(IntArrayEntry* entryList)
{
    if (!gCtx) return;
    JSValue global = JS_GetGlobalObject(gCtx);
    for (IntArrayEntry* p = entryList; p->name; ++p) {
        JS_SetPropertyStr(gCtx, global, p->name, JS_NewInt32(gCtx, p->value));
    }
    JS_FreeValue(gCtx, global);
}

void js_engine::DeleteConstantArray(IntArrayEntry* entryList)
{
    if (!gCtx) return;
    JSValue global = JS_GetGlobalObject(gCtx);
    for (IntArrayEntry* p = entryList; p->name; ++p) {
        JSAtom a = JS_NewAtom(gCtx, p->name);
        JS_DeleteProperty(gCtx, global, a, 0);
        JS_FreeAtom(gCtx, a);
    }
    JS_FreeValue(gCtx, global);
}

float js_engine::RunScript(const char* src, int objectIndex)
{
    if (!gCtx || !src) return 0.0f;
    gCurObj = objectIndex;
    size_t len = std::strlen(src);
    JSValue rv = JS_Eval(gCtx, src, len, "<iff>", JS_EVAL_TYPE_GLOBAL);
    if (JS_IsException(rv)) {
        log_exception("error");
        std::fprintf(stderr, "  script: %s\n", src);
        JS_FreeValue(gCtx, rv);
        return 0.0f;
    }
    double d = 0.0;
    if (JS_ToFloat64(gCtx, &d, rv) < 0 || std::isnan(d)) d = 0.0;
    JS_FreeValue(gCtx, rv);
    return (float)d;
}

#endif // WF_JS_ENGINE_QUICKJS
