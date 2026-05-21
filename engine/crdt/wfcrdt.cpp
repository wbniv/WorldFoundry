// engine/crdt/wfcrdt.cpp — see wfcrdt.hpp.
//
// Plan: docs/plans/2026-05-19-wfcrdt-cpp-raii-wrapper.md

#include "wfcrdt.hpp"

// libyrs.h is a cbindgen-generated C header but it lacks `extern "C"`
// guards. When included from a C++ TU the declarations would otherwise
// get C++ mangling, then fail to link against the C-linkage symbols in
// libyrs.a. Wrap the include here at the boundary.
extern "C" {
#include <libyrs.h>
}

#include <cstring>
#include <utility>

namespace wfcrdt {

// ─── Doc ──────────────────────────────────────────────────────────────────────

Doc::Doc() : _doc(ydoc_new()) {}

Doc::~Doc() {
    if (_doc) ydoc_destroy(_doc);
}

Doc::Doc(Doc&& other) noexcept : _doc(other._doc) {
    other._doc = nullptr;
}

Doc& Doc::operator=(Doc&& other) noexcept {
    if (this != &other) {
        if (_doc) ydoc_destroy(_doc);
        _doc = other._doc;
        other._doc = nullptr;
    }
    return *this;
}

Transaction Doc::begin() {
    return Transaction(_doc);
}

// ─── Transaction ──────────────────────────────────────────────────────────────

Transaction::Transaction(YDoc* doc) : _txn(ytransaction_new(doc)) {}

Transaction::~Transaction() {
    if (_txn) ytransaction_commit(_txn);
}

Transaction::Transaction(Transaction&& other) noexcept : _txn(other._txn) {
    other._txn = nullptr;
}

Transaction& Transaction::operator=(Transaction&& other) noexcept {
    if (this != &other) {
        if (_txn) ytransaction_commit(_txn);
        _txn = other._txn;
        other._txn = nullptr;
    }
    return *this;
}

void Transaction::commit() {
    if (_txn) {
        ytransaction_commit(_txn);
        _txn = nullptr;
    }
}

void Transaction::cancel() {
    // yffi has no rollback; today this is identical to commit().
    // Kept as a separate symbol so future yffi changes don't require
    // a caller-side migration.
    if (_txn) {
        ytransaction_commit(_txn);
        _txn = nullptr;
    }
}

Map Transaction::map(const char* name) {
    return Map(ymap(_txn, name), _txn);
}

Array Transaction::array(const char* name) {
    return Array(yarray(_txn, name), _txn);
}

// Helper: copy a yffi-allocated byte buffer into an owned std::vector,
// then release the yffi heap allocation. The vector handles its own dtor.
static std::vector<std::uint8_t> takeYffiBytes(unsigned char* buf, int len) {
    if (!buf || len <= 0) {
        if (buf) ybinary_destroy(buf, len);
        return {};
    }
    std::vector<std::uint8_t> out(buf, buf + len);
    ybinary_destroy(buf, len);
    return out;
}

std::vector<std::uint8_t> Transaction::stateVector() const {
    int len = 0;
    unsigned char* buf = ytransaction_state_vector_v1(_txn, &len);
    return takeYffiBytes(buf, len);
}

std::vector<std::uint8_t> Transaction::stateDiff(ByteView remoteSv) const {
    int len = 0;
    unsigned char* buf = ytransaction_state_diff_v1(
        _txn,
        remoteSv.data,
        static_cast<int>(remoteSv.len),
        &len);
    return takeYffiBytes(buf, len);
}

void Transaction::apply(ByteView diff) {
    ytransaction_apply(_txn, diff.data, static_cast<int>(diff.len));
}

// ─── Output ───────────────────────────────────────────────────────────────────

Output::~Output() {
    if (_out) youtput_destroy(_out);
}

Output::Output(Output&& other) noexcept : _out(other._out), _txn(other._txn) {
    other._out = nullptr;
    other._txn = nullptr;
}

Output& Output::operator=(Output&& other) noexcept {
    if (this != &other) {
        if (_out) youtput_destroy(_out);
        _out = other._out;
        _txn = other._txn;
        other._out = nullptr;
        other._txn = nullptr;
    }
    return *this;
}

std::optional<long long> Output::readLong() const {
    if (!_out) return std::nullopt;
    const long long* p = youtput_read_long(_out);
    if (!p) return std::nullopt;
    return *p;
}

std::optional<std::string> Output::readString() const {
    if (!_out) return std::nullopt;
    char* p = youtput_read_string(_out);
    if (!p) return std::nullopt;
    // youtput's string is owned by the YOutput cell — destroyed with it.
    // Copy into a std::string so the caller's value survives ~Output().
    return std::string(p);
}

std::optional<double> Output::readFloat() const {
    if (!_out) return std::nullopt;
    const float* p = youtput_read_float(_out);
    if (!p) return std::nullopt;
    return static_cast<double>(*p);
}

Map Output::asMap() const {
    // youtput_read_ymap returns the inner Branch* (owned by the doc, not the
    // YOutput) or null if the stored value isn't a Y.Map. Bound to the same txn.
    return Map(_out ? youtput_read_ymap(_out) : nullptr, _txn);
}

Array Output::asArray() const {
    return Array(_out ? youtput_read_yarray(_out) : nullptr, _txn);
}

// ─── nested-input materializer ──────────────────────────────────────────────
//
// Materializes a wfcrdt::Input tree into a live branch by inserting an EMPTY
// nested container (yinput_ymap/yinput_yarray with no entries) and then
// recursively populating it — rather than handing yffi a prefilled prelim.
//
// This deliberately avoids prefilled yinput_ymap: yrs v0.9.3's
// YInput::integrate has an infinite-loop bug for prefilled shared maps
// (wftools/y-crdt/yffi/src/lib.rs:1795 — the Y_MAP loop uses `let i = 0`,
// never increments, and re-inserts the same key/value forever → unbounded
// allocation; the Y_ARRAY branch right below it correctly uses `let mut i`).
// Empty-container-then-populate is also the pattern upstream's own FFI tests
// use for nested shared types, so it stays on a well-exercised code path.
// Upstream one-line fix kept as a submittable patch (submodule stays pinned):
//   docs/patches/yrs-0.9.3-yinput-ymap-integrate-loop.patch
// TODO(crdt): collapse this back to a direct prefilled insert once the y-crdt
// submodule is bumped past the fix (or our patch is upstreamed).
namespace {
void fill_map(Branch* m, YTransaction* txn, const Input& in);
void fill_array(Branch* a, YTransaction* txn, const Input& in);

// Insert `in` into map branch `m` under `key`.
void put_in_map(Branch* m, YTransaction* txn, const char* key, const Input& in) {
    using K = Input::Kind;
    switch (in.kind()) {
        case K::Str:    { YInput v = yinput_string(in.strVal().c_str());              ymap_insert(m, txn, key, &v); return; }
        case K::Long:   { YInput v = yinput_long(static_cast<long>(in.longVal()));     ymap_insert(m, txn, key, &v); return; }
        case K::Double: { YInput v = yinput_float(static_cast<float>(in.doubleVal())); ymap_insert(m, txn, key, &v); return; }
        case K::Boolean:   { YInput v = yinput_bool(in.boolVal() ? 1 : 0);                ymap_insert(m, txn, key, &v); return; }
        case K::Map: {
            YInput empty = yinput_ymap(nullptr, nullptr, 0);
            ymap_insert(m, txn, key, &empty);
            YOutput* o = ymap_get(m, key);   // inner branch, owned by the doc
            fill_map(youtput_read_ymap(o), txn, in);
            youtput_destroy(o);
            return;
        }
        case K::Array: {
            YInput empty = yinput_yarray(nullptr, 0);
            ymap_insert(m, txn, key, &empty);
            YOutput* o = ymap_get(m, key);
            fill_array(youtput_read_yarray(o), txn, in);
            youtput_destroy(o);
            return;
        }
    }
}

// Insert `in` into array branch `a` at `index`.
void put_in_array(Branch* a, YTransaction* txn, int index, const Input& in) {
    using K = Input::Kind;
    switch (in.kind()) {
        case K::Str:    { YInput v = yinput_string(in.strVal().c_str());              yarray_insert_range(a, txn, index, &v, 1); return; }
        case K::Long:   { YInput v = yinput_long(static_cast<long>(in.longVal()));     yarray_insert_range(a, txn, index, &v, 1); return; }
        case K::Double: { YInput v = yinput_float(static_cast<float>(in.doubleVal())); yarray_insert_range(a, txn, index, &v, 1); return; }
        case K::Boolean:   { YInput v = yinput_bool(in.boolVal() ? 1 : 0);                yarray_insert_range(a, txn, index, &v, 1); return; }
        case K::Map: {
            YInput empty = yinput_ymap(nullptr, nullptr, 0);
            yarray_insert_range(a, txn, index, &empty, 1);
            YOutput* o = yarray_get(a, index);
            fill_map(youtput_read_ymap(o), txn, in);
            youtput_destroy(o);
            return;
        }
        case K::Array: {
            YInput empty = yinput_yarray(nullptr, 0);
            yarray_insert_range(a, txn, index, &empty, 1);
            YOutput* o = yarray_get(a, index);
            fill_array(youtput_read_yarray(o), txn, in);
            youtput_destroy(o);
            return;
        }
    }
}

void fill_map(Branch* m, YTransaction* txn, const Input& in) {
    for (const auto& kv : in.mapEntries()) put_in_map(m, txn, kv.first.c_str(), kv.second);
}
void fill_array(Branch* a, YTransaction* txn, const Input& in) {
    int i = 0;
    for (const auto& e : in.arrayElems()) put_in_array(a, txn, i++, e);
}
}  // namespace

// ─── Map ──────────────────────────────────────────────────────────────────────

void Map::insert(const char* key, long long value) {
    YInput v = yinput_long(static_cast<long>(value));
    ymap_insert(_branch, _txn, key, &v);
}

void Map::insert(const char* key, const char* value) {
    YInput v = yinput_string(value);
    ymap_insert(_branch, _txn, key, &v);
}

void Map::insert(const char* key, double value) {
    YInput v = yinput_float(static_cast<float>(value));
    ymap_insert(_branch, _txn, key, &v);
}

void Map::insert(const char* key, const Input& value) {
    put_in_map(_branch, _txn, key, value);
}

Output Map::get(const char* key) const {
    return Output(ymap_get(_branch, key), _txn);
}

int Map::len() const {
    return ymap_len(_branch);
}

// ─── Array ────────────────────────────────────────────────────────────────────

void Array::insertLong(int index, long long value) {
    YInput v = yinput_long(static_cast<long>(value));
    yarray_insert_range(_branch, _txn, index, &v, 1);
}

void Array::insertRange(int index, const long long* values, int count) {
    // yffi takes an array of YInput. Build one on the heap (small alloc;
    // count is bounded by caller intent — not concerned about overflow).
    std::vector<YInput> inputs;
    inputs.reserve(static_cast<std::size_t>(count));
    for (int i = 0; i < count; ++i) {
        inputs.push_back(yinput_long(static_cast<long>(values[i])));
    }
    yarray_insert_range(_branch, _txn, index, inputs.data(), count);
}

void Array::insert(int index, const Input& value) {
    put_in_array(_branch, _txn, index, value);
}

void Array::remove(int index, int count) {
    // yffi panics if [index, index+count) escapes the array bounds; guard.
    if (count <= 0) return;
    const int n = yarray_len(_branch);
    if (index < 0 || index + count > n) return;
    yarray_remove_range(_branch, _txn, index, count);
}

void Array::push(const Input& value) {
    insert(len(), value);
}

Output Array::get(int index) const {
    return Output(yarray_get(_branch, index), _txn);
}

int Array::len() const {
    return yarray_len(_branch);
}

// ─── Observer trampolines ─────────────────────────────────────────────────────
//
// The C ABI takes (void* state, void (*cb)(void*, YEvent*)). We heap-allocate
// a Trampoline struct holding the caller's std::function and pass its address
// as `state`; the C-linkage trampoline below downcasts and invokes.
//
// extern "C" on the trampolines guarantees C calling convention. In practice
// on Linux/x86_64 it's identical to the C++ convention for this signature,
// but extern "C" is the portable spelling.

namespace {

struct MapTrampoline {
    std::function<void(const YMapEvent*)> cb;
};
struct ArrayTrampoline {
    std::function<void(const YArrayEvent*)> cb;
};

extern "C" void wfcrdt_map_trampoline(void* state, const YMapEvent* e) {
    auto* t = static_cast<MapTrampoline*>(state);
    t->cb(e);
}
extern "C" void wfcrdt_array_trampoline(void* state, const YArrayEvent* e) {
    auto* t = static_cast<ArrayTrampoline*>(state);
    t->cb(e);
}

}  // namespace

Subscription Map::observe(std::function<void(const YMapEvent*)> cb) {
    auto* t = new MapTrampoline{std::move(cb)};
    unsigned int subId =
        ymap_observe(_branch, t, &wfcrdt_map_trampoline);
    return Subscription(_branch, subId, SubKind::Map, t);
}

Subscription Array::observe(std::function<void(const YArrayEvent*)> cb) {
    auto* t = new ArrayTrampoline{std::move(cb)};
    unsigned int subId =
        yarray_observe(_branch, t, &wfcrdt_array_trampoline);
    return Subscription(_branch, subId, SubKind::Array, t);
}

// ─── Subscription ─────────────────────────────────────────────────────────────

Subscription::Subscription(Branch* target,
                           unsigned int subId,
                           SubKind kind,
                           void* heapTrampoline)
    : _target(target), _subId(subId), _kind(kind), _heap(heapTrampoline) {}

Subscription::~Subscription() {
    if (!_target) return;
    if (_kind == SubKind::Map) {
        ymap_unobserve(_target, _subId);
        delete static_cast<MapTrampoline*>(_heap);
    } else {
        yarray_unobserve(_target, _subId);
        delete static_cast<ArrayTrampoline*>(_heap);
    }
}

Subscription::Subscription(Subscription&& other) noexcept
    : _target(other._target),
      _subId(other._subId),
      _kind(other._kind),
      _heap(other._heap) {
    other._target = nullptr;
    other._heap = nullptr;
}

Subscription& Subscription::operator=(Subscription&& other) noexcept {
    if (this != &other) {
        // Run our own dtor logic first.
        if (_target) {
            if (_kind == SubKind::Map) {
                ymap_unobserve(_target, _subId);
                delete static_cast<MapTrampoline*>(_heap);
            } else {
                yarray_unobserve(_target, _subId);
                delete static_cast<ArrayTrampoline*>(_heap);
            }
        }
        _target = other._target;
        _subId = other._subId;
        _kind = other._kind;
        _heap = other._heap;
        other._target = nullptr;
        other._heap = nullptr;
    }
    return *this;
}

}  // namespace wfcrdt
