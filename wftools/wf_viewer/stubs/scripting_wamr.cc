// scripting_wamr.cc — WAMR scripting backend for wamr_engine namespace.
//
// Compiled in when WF_WASM_ENGINE_WAMR is defined (via build_game.sh).
// Sigil: `#b64\n` — handled by ScriptRouter before dispatch here.
//
// Uses the wasm-C-API (wasm_c_api.h) for portability.  One engine + store
// is created at Init and reused for all RunScript calls.  Per-call:
//   1. base64-decode the payload after the `#b64\n` header
//   2. load + compile the module
//   3. walk module imports — match "env" funcs and "consts" globals
//   4. instantiate with the resolved extern vector
//   5. call the exported "main" function
//   6. destroy the instance + module (the store survives)
//
// Host functions (registered once at Init):
//   "env" "read_mailbox"  (i32) → f32   mailbox read for current actor
//   "env" "write_mailbox" (i32 f32) → Ø mailbox write for current actor
//
// Host globals (per-call, from AddConstantArray map):
//   "consts" "<NAME>" → i32  resolved by name from g_consts
//
// Constants that appear in the module but are missing from g_consts default
// to 0 with a stderr warning — same fallback used by wasm3 baked-literal
// approach when a mailbox index is out of range.

#ifdef WF_WASM_ENGINE_WAMR

#include "scripting_wamr.hp"
#include <scripting/scriptinterpreter.hp>
#include <mailbox/mailbox.hp>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <unordered_map>
#include <vector>

extern "C" {
#include <wasm_c_api.h>
}

// ---------------------------------------------------------------------------
// base64 decoder — identical to the one in scripting_wasm3.cc

static const int8_t kB64Table[256] = {
    -1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,
    -1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,
    -1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,62,-1,-1,-1,63,
    52,53,54,55,56,57,58,59,60,61,-1,-1,-1, 0,-1,-1,
    -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9,10,11,12,13,14,
    15,16,17,18,19,20,21,22,23,24,25,-1,-1,-1,-1,-1,
    -1,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,
    41,42,43,44,45,46,47,48,49,50,51,-1,-1,-1,-1,-1,
    -1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,
    -1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,
    -1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,
    -1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,
    -1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,
    -1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,
    -1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,
    -1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1
};

static std::vector<uint8_t> base64_decode(const char* in, size_t len)
{
    std::vector<uint8_t> out;
    out.reserve(len * 3 / 4);
    uint32_t acc = 0;
    int bits = 0;
    for (size_t i = 0; i < len; ++i) {
        int8_t v = kB64Table[(uint8_t)in[i]];
        if (v < 0) continue; // skip whitespace / padding
        acc = (acc << 6) | (uint8_t)v;
        bits += 6;
        if (bits >= 8) {
            bits -= 8;
            out.push_back((uint8_t)((acc >> bits) & 0xff));
        }
    }
    return out;
}

// ---------------------------------------------------------------------------
// Module state

static wasm_engine_t*    g_engine  = nullptr;
static wasm_store_t*     g_store   = nullptr;
static MailboxesManager* g_mgr     = nullptr;
static int               g_curObj  = 0;

// Map from constant name (e.g. "INDEXOF_INPUT") to integer value.
// Built from AddConstantArray calls; never shrinks (constants persist).
static std::unordered_map<std::string, int32_t> g_consts;

// ---------------------------------------------------------------------------
// Host function callbacks — called from wasm via the wasm-C-API.
// Signature: read_mailbox(i32) -> f32

static wasm_trap_t* host_read_mailbox(const wasm_val_vec_t* args,
                                      wasm_val_vec_t*       results)
{
    int32_t idx = args->data[0].of.i32;
    float   val = 0.0f;
    if (g_mgr) {
        Mailboxes& mb = g_mgr->LookupMailboxes(g_curObj);
        val = mb.ReadMailbox(idx).AsFloat();
    }
    results->data[0].kind = WASM_F32;
    results->data[0].of.f32 = val;
    return nullptr;
}

// Signature: write_mailbox(i32, f32) -> ()
static wasm_trap_t* host_write_mailbox(const wasm_val_vec_t* args,
                                       wasm_val_vec_t*       /*results*/)
{
    int32_t idx = args->data[0].of.i32;
    float   val = args->data[1].of.f32;
    if (g_mgr) {
        Mailboxes& mb = g_mgr->LookupMailboxes(g_curObj);
        mb.WriteMailbox(idx, Scalar::FromFloat(val));
    }
    return nullptr;
}

// ---------------------------------------------------------------------------
// wamr_engine namespace — public plug interface

namespace wamr_engine {

void Init(MailboxesManager& mgr)
{
    g_mgr    = &mgr;
    g_curObj = 0;

    g_engine = wasm_engine_new();
    if (!g_engine) {
        fprintf(stderr, "wamr: wasm_engine_new failed\n");
        return;
    }
    g_store = wasm_store_new(g_engine);
    if (!g_store) {
        fprintf(stderr, "wamr: wasm_store_new failed\n");
        wasm_engine_delete(g_engine);
        g_engine = nullptr;
    }
}

void Shutdown()
{
    if (g_store)  { wasm_store_delete(g_store);   g_store  = nullptr; }
    if (g_engine) { wasm_engine_delete(g_engine); g_engine = nullptr; }
    g_mgr = nullptr;
    g_curObj = 0;
    g_consts.clear();
}

void AddConstantArray(IntArrayEntry* entryList)
{
    for (IntArrayEntry* p = entryList; p->name; p++)
        g_consts[p->name] = p->value;
}

void DeleteConstantArray(IntArrayEntry* /*entryList*/)
{
    // Constant map is append-only; entries persist for engine lifetime.
}

float RunScript(const char* src, int objectIndex)
{
    if (!src || !g_engine || !g_store) return 0.0f;

    // Skip sigil line: `#b64\n`
    const char* b64 = strchr(src, '\n');
    if (!b64) return 0.0f;
    b64++; // skip '\n'

    // Decode base64 payload.
    std::vector<uint8_t> wasm_bytes = base64_decode(b64, strlen(b64));
    if (wasm_bytes.empty()) {
        fprintf(stderr, "wamr: base64 decode produced empty module\n");
        return 0.0f;
    }

    g_curObj = objectIndex;

    // -----------------------------------------------------------------------
    // 1. Compile module
    wasm_byte_vec_t bytes;
    bytes.size = wasm_bytes.size();
    bytes.data = reinterpret_cast<wasm_byte_t*>(wasm_bytes.data());

    wasm_module_t* module = wasm_module_new(g_store, &bytes);
    if (!module) {
        fprintf(stderr, "wamr: wasm_module_new failed\n");
        return 0.0f;
    }

    // -----------------------------------------------------------------------
    // 2. Walk imports — build extern vector in declaration order.
    //    Each import is either:
    //      "env"    func  read_mailbox / write_mailbox
    //      "consts" global <NAME>
    wasm_importtype_vec_t import_types;
    wasm_module_imports(module, &import_types);

    // Pre-build the two host function types.
    // read_mailbox: (i32) -> f32
    wasm_valtype_t* rm_param_v[]  = { wasm_valtype_new_i32() };
    wasm_valtype_t* rm_result_v[] = { wasm_valtype_new_f32() };
    wasm_valtype_vec_t rm_params, rm_results;
    wasm_valtype_vec_new(&rm_params,  1, rm_param_v);
    wasm_valtype_vec_new(&rm_results, 1, rm_result_v);
    wasm_functype_t* read_ft = wasm_functype_new(&rm_params, &rm_results);

    // write_mailbox: (i32, f32) -> ()
    wasm_valtype_t* wm_param_v[] = { wasm_valtype_new_i32(), wasm_valtype_new_f32() };
    wasm_valtype_vec_t wm_params, wm_results_empty;
    wasm_valtype_vec_new(&wm_params, 2, wm_param_v);
    wasm_valtype_vec_new_empty(&wm_results_empty);
    wasm_functype_t* write_ft = wasm_functype_new(&wm_params, &wm_results_empty);

    // Build externs in import order.
    size_t n = import_types.size;
    std::vector<wasm_extern_t*> extern_ptrs(n, nullptr);
    // Keep ownership of created objects to free them later.
    std::vector<wasm_func_t*>   owned_funcs;
    std::vector<wasm_global_t*> owned_globals;

    bool ok = true;
    for (size_t i = 0; i < n; i++) {
        const wasm_importtype_t* imp  = import_types.data[i];
        const wasm_name_t*       mod  = wasm_importtype_module(imp);
        const wasm_name_t*       name = wasm_importtype_name(imp);
        const wasm_externtype_t* ext  = wasm_importtype_type(imp);

        std::string mod_str(mod->data,   mod->size);
        std::string nm_str (name->data,  name->size);

        if (mod_str == "env") {
            // Host functions: read_mailbox and write_mailbox
            wasm_functype_t* ft = nullptr;
            wasm_func_callback_t cb = nullptr;
            if (nm_str == "read_mailbox") {
                ft = read_ft;
                cb = host_read_mailbox;
            } else if (nm_str == "write_mailbox") {
                ft = write_ft;
                cb = host_write_mailbox;
            } else {
                fprintf(stderr, "wamr: unknown env import '%s'\n", nm_str.c_str());
                ok = false;
                break;
            }
            wasm_func_t* f = wasm_func_new(g_store, ft, cb);
            owned_funcs.push_back(f);
            extern_ptrs[i] = wasm_func_as_extern(f);
        } else if (mod_str == "consts") {
            // Host globals: INDEXOF_* constants
            if (wasm_externtype_kind(ext) != WASM_EXTERN_GLOBAL) {
                fprintf(stderr, "wamr: 'consts' import '%s' is not a global\n",
                        nm_str.c_str());
                ok = false;
                break;
            }
            int32_t val = 0;
            auto it = g_consts.find(nm_str);
            if (it != g_consts.end()) {
                val = it->second;
            } else {
                fprintf(stderr, "wamr: unknown const '%s' (defaulting to 0)\n",
                        nm_str.c_str());
            }
            wasm_val_t wval;
            wval.kind  = WASM_I32;
            wval.of.i32 = val;
            wasm_globaltype_t* gt = wasm_globaltype_new(
                wasm_valtype_new_i32(), WASM_CONST);
            wasm_global_t* g = wasm_global_new(g_store, gt, &wval);
            wasm_globaltype_delete(gt);
            owned_globals.push_back(g);
            extern_ptrs[i] = wasm_global_as_extern(g);
        } else {
            fprintf(stderr, "wamr: unknown import module '%s'\n", mod_str.c_str());
            ok = false;
            break;
        }
    }

    wasm_importtype_vec_delete(&import_types);
    wasm_functype_delete(read_ft);
    wasm_functype_delete(write_ft);

    float result = 0.0f;
    if (ok) {
        // -----------------------------------------------------------------------
        // 3. Instantiate
        wasm_extern_vec_t imports;
        imports.size = n;
        imports.data = extern_ptrs.data();

        wasm_trap_t* trap = nullptr;
        wasm_instance_t* instance = wasm_instance_new(g_store, module, &imports, &trap);
        if (!instance) {
            if (trap) {
                wasm_message_t msg;
                wasm_trap_message(trap, &msg);
                fprintf(stderr, "wamr: instantiation trap: %.*s\n",
                        (int)msg.size, msg.data);
                wasm_byte_vec_delete(&msg);
                wasm_trap_delete(trap);
            } else {
                fprintf(stderr, "wamr: wasm_instance_new failed\n");
            }
        } else {
            // -----------------------------------------------------------------------
            // 4. Call exported "main"
            wasm_extern_vec_t exports;
            wasm_instance_exports(instance, &exports);

            wasm_func_t* main_fn = nullptr;
            for (size_t i = 0; i < exports.size; i++) {
                // The module must export a function named "main".
                // We look at type: exports order matches the wasm export section.
                if (wasm_extern_kind(exports.data[i]) == WASM_EXTERN_FUNC) {
                    main_fn = wasm_extern_as_func(exports.data[i]);
                    break; // first exported function = main
                }
            }

            if (main_fn) {
                wasm_val_vec_t call_args, call_results;
                wasm_val_vec_new_empty(&call_args);
                wasm_val_vec_new_empty(&call_results);
                wasm_trap_t* call_trap = wasm_func_call(main_fn, &call_args, &call_results);
                if (call_trap) {
                    wasm_message_t msg;
                    wasm_trap_message(call_trap, &msg);
                    fprintf(stderr, "wamr: main() trap: %.*s\n",
                            (int)msg.size, msg.data);
                    wasm_byte_vec_delete(&msg);
                    wasm_trap_delete(call_trap);
                }
                wasm_val_vec_delete(&call_args);
                wasm_val_vec_delete(&call_results);
            } else {
                fprintf(stderr, "wamr: no exported function 'main'\n");
            }

            wasm_extern_vec_delete(&exports);
            wasm_instance_delete(instance);
        }
    }

    // -----------------------------------------------------------------------
    // 5. Cleanup owned objects
    for (auto* g : owned_globals) wasm_global_delete(g);
    for (auto* f : owned_funcs)   wasm_func_delete(f);
    wasm_module_delete(module);

    return result;
}

} // namespace wamr_engine

#endif // WF_WASM_ENGINE_WAMR
