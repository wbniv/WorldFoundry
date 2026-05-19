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

Output::Output(Output&& other) noexcept : _out(other._out) {
    other._out = nullptr;
}

Output& Output::operator=(Output&& other) noexcept {
    if (this != &other) {
        if (_out) youtput_destroy(_out);
        _out = other._out;
        other._out = nullptr;
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

Output Map::get(const char* key) const {
    return Output(ymap_get(_branch, key));
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

Output Array::get(int index) const {
    return Output(yarray_get(_branch, index));
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
