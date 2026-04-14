// scripting_jerryscript.cc — JerryScript back-end for the `//` sigil.
//
// Only compiled when WF_JS_ENGINE_JERRYSCRIPT is defined. Exposes the same
// read_mailbox / write_mailbox callbacks and INDEXOF_* / JOYSTICK_BUTTON_*
// globals as the Lua / QuickJS sides.

#include "scripting_js.hp"

#ifdef WF_JS_ENGINE_JERRYSCRIPT

#include <mailbox/mailbox.hp>
#include <math/scalar.hp>
#include <scripting/scriptinterpreter.hp>  // IntArrayEntry

#include "jerryscript.h"

#include <cstdio>
#include <cstring>
#include <cmath>

namespace {

MailboxesManager* gMgr    = nullptr;
int               gCurObj = 0;
bool              gInit   = false;

jerry_value_t js_read_mailbox(const jerry_call_info_t*,
                              const jerry_value_t args[],
                              const jerry_length_t argc)
{
    if (argc < 1 || !jerry_value_is_number(args[0])) return jerry_number(0);
    int mailbox = (int)jerry_value_as_number(args[0]);
    int actor   = gCurObj;
    if (argc >= 2 && jerry_value_is_number(args[1])) {
        actor = (int)jerry_value_as_number(args[1]);
    }
    Mailboxes& mb = gMgr->LookupMailboxes(actor);
    Scalar v = mb.ReadMailbox(mailbox);
    std::fprintf(stderr, "  jry read_mailbox(%d, actor=%d) -> %g\n",
                 mailbox, actor, (double)v.AsFloat());
    return jerry_number((double)v.AsFloat());
}

jerry_value_t js_write_mailbox(const jerry_call_info_t*,
                               const jerry_value_t args[],
                               const jerry_length_t argc)
{
    if (argc < 2 || !jerry_value_is_number(args[0]) || !jerry_value_is_number(args[1])) {
        return jerry_undefined();
    }
    int    mailbox = (int)jerry_value_as_number(args[0]);
    double value   = jerry_value_as_number(args[1]);
    int    actor   = gCurObj;
    if (argc >= 3 && jerry_value_is_number(args[2])) {
        actor = (int)jerry_value_as_number(args[2]);
    }
    Mailboxes& mb = gMgr->LookupMailboxes(actor);
    std::fprintf(stderr, "  jry write_mailbox(%d, %g, actor=%d)\n",
                 mailbox, value, actor);
    mb.WriteMailbox(mailbox, Scalar::FromFloat((float)value));
    return jerry_undefined();
}

void set_global_fn(const char* name, jerry_external_handler_t h)
{
    jerry_value_t global = jerry_current_realm();
    jerry_value_t fn     = jerry_function_external(h);
    jerry_value_t res    = jerry_object_set_sz(global, name, fn);
    jerry_value_free(res);
    jerry_value_free(fn);
    jerry_value_free(global);
}

} // namespace

void JsRuntimeInit(MailboxesManager& mgr)
{
    gMgr = &mgr;
    jerry_init(JERRY_INIT_EMPTY);
    gInit = true;
    set_global_fn("read_mailbox",  js_read_mailbox);
    set_global_fn("write_mailbox", js_write_mailbox);
    std::fprintf(stderr, "jerryscript: runtime initialised\n");
}

void JsRuntimeShutdown()
{
    if (gInit) {
        jerry_cleanup();
        gInit = false;
    }
    gMgr = nullptr;
}

void JsAddConstantArray(IntArrayEntry* entryList)
{
    if (!gInit) return;
    jerry_value_t global = jerry_current_realm();
    for (IntArrayEntry* p = entryList; p->name; ++p) {
        jerry_value_t v   = jerry_number((double)p->value);
        jerry_value_t res = jerry_object_set_sz(global, p->name, v);
        jerry_value_free(res);
        jerry_value_free(v);
    }
    jerry_value_free(global);
}

void JsDeleteConstantArray(IntArrayEntry* entryList)
{
    if (!gInit) return;
    jerry_value_t global = jerry_current_realm();
    for (IntArrayEntry* p = entryList; p->name; ++p) {
        jerry_value_t res = jerry_object_delete_sz(global, p->name);
        jerry_value_free(res);
    }
    jerry_value_free(global);
}

float JsRunScript(const char* src, int objectIndex)
{
    if (!gInit || !src) return 0.0f;
    gCurObj = objectIndex;
    size_t len = std::strlen(src);
    jerry_value_t rv = jerry_eval((const jerry_char_t*)src, len, JERRY_PARSE_NO_OPTS);
    if (jerry_value_is_exception(rv)) {
        jerry_value_t e = jerry_exception_value(rv, false);
        jerry_value_t s = jerry_value_to_string(e);
        char buf[512];
        jerry_size_t n = jerry_string_to_buffer(s, JERRY_ENCODING_UTF8,
                                                (jerry_char_t*)buf,
                                                (jerry_size_t)sizeof(buf) - 1);
        buf[n] = '\0';
        std::fprintf(stderr, "jerryscript error: %s\n  script: %s\n", buf, src);
        jerry_value_free(s);
        jerry_value_free(e);
        jerry_value_free(rv);
        return 0.0f;
    }
    double d = 0.0;
    if (jerry_value_is_number(rv)) {
        d = jerry_value_as_number(rv);
        if (std::isnan(d)) d = 0.0;
    }
    jerry_value_free(rv);
    return (float)d;
}

#endif // WF_JS_ENGINE_JERRYSCRIPT
