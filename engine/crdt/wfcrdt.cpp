// engine/crdt/wfcrdt.cpp — see wfcrdt.hpp.
//
// Plan: docs/plans/2026-05-19-wfcrdt-cpp-raii-wrapper.md
// Yrs upgrade 0.9.3 → 0.26.0: docs/plans/2026-05-22-yrs-upgrade-and-native-undo.md

#include "wfcrdt.hpp"

// libyrs.h is a cbindgen-generated C header but it lacks `extern "C"`
// guards. When included from a C++ TU the declarations would otherwise
// get C++ mangling, then fail to link against the C-linkage symbols in
// libyrs.a. Wrap the include here at the boundary.
extern "C" {
#include <libyrs.h>
}

#include <cstdint>
#include <cstring>
#include <utility>

namespace wfcrdt {

// ─── Doc ──────────────────────────────────────────────────────────────────────

Doc::Doc() : _doc(ydoc_new()) {}

Doc::~Doc() {
    if (_doc) ydoc_destroy(_doc);
}

Doc::Doc(Doc&& other) noexcept
    : _doc(other._doc), _roots(std::move(other._roots)) {
    other._doc = nullptr;
}

Doc& Doc::operator=(Doc&& other) noexcept {
    if (this != &other) {
        if (_doc) ydoc_destroy(_doc);
        _doc = other._doc;
        _roots = std::move(other._roots);
        other._doc = nullptr;
    }
    return *this;
}

Transaction Doc::begin() {
    // Local edits carry kOriginLocal so an UndoManager tracking that origin
    // captures every editor edit path with no per-call-site change.
    return Transaction(this, kOriginLocal, sizeof(kOriginLocal) - 1);
}

Transaction Doc::beginRemote() {
    // Remote applies carry kOriginRemote — never captured by the local
    // UndoManager (its origin set holds only kOriginLocal).
    return Transaction(this, kOriginRemote, sizeof(kOriginRemote) - 1);
}

Branch* Doc::rootBranch(const char* name, bool asArray) {
    if (!_doc) return nullptr;
    auto it = _roots.find(name);
    if (it != _roots.end()) return it->second;
    // Cache miss: get-or-create the root. NB ymap/yarray each open their OWN
    // internal write txn in yffi, so this must run with no wfcrdt Transaction's
    // yffi txn open on this doc — guaranteed by Transaction's lazy acquisition.
    Branch* b = asArray ? yarray(_doc, name) : ymap(_doc, name);
    _roots.emplace(name, b);
    return b;
}

// ─── Transaction ──────────────────────────────────────────────────────────────

Transaction::Transaction(Doc* docw, const char* origin, std::uint32_t originLen)
    : _docw(docw), _txn(nullptr), _origin(origin), _originLen(originLen) {}

YTransaction* Transaction::raw() const {
    // Lazily open the yffi write txn on first use. ydoc_write_transaction()
    // returns NULL if another write txn is already open on the doc — that only
    // happens if a caller nests doc.begin() scopes (forbidden: yrs is
    // single-writer). The origin (kOriginLocal/kOriginRemote, or nullptr) gates
    // UndoManager capture; it isn't part of the v1 update wire format, so sync
    // is unaffected.
    if (!_docw) return nullptr;
    if (!_txn) _txn = ydoc_write_transaction(_docw->raw(), _originLen, _origin);
    return _txn;
}

Transaction::~Transaction() {
    if (_txn) ytransaction_commit(_txn);
}

Transaction::Transaction(Transaction&& other) noexcept
    : _docw(other._docw), _txn(other._txn),
      _origin(other._origin), _originLen(other._originLen) {
    other._docw = nullptr;
    other._txn = nullptr;
}

Transaction& Transaction::operator=(Transaction&& other) noexcept {
    if (this != &other) {
        if (_txn) ytransaction_commit(_txn);
        _docw = other._docw;
        _txn = other._txn;
        _origin = other._origin;
        _originLen = other._originLen;
        other._docw = nullptr;
        other._txn = nullptr;
    }
    return *this;
}

void Transaction::commit() {
    if (_txn) {
        ytransaction_commit(_txn);
        _txn = nullptr;
    }
    _docw = nullptr;   // mark not-live: further ops illegal, valid() == false
}

void Transaction::cancel() {
    // yffi has no rollback; today this is identical to commit().
    // Kept as a separate symbol so future yffi changes don't require
    // a caller-side migration.
    commit();
}

Map Transaction::map(const char* name) {
    // Resolve the root branch via the Doc cache WITHOUT opening this txn (so
    // ymap's internal txn can't deadlock against ours), then bind the view to
    // this Transaction — its data ops lazily open the txn via raw().
    return Map(_docw ? _docw->rootBranch(name, /*asArray=*/false) : nullptr, this);
}

Array Transaction::array(const char* name) {
    return Array(_docw ? _docw->rootBranch(name, /*asArray=*/true) : nullptr, this);
}

// Helper: copy a yffi-allocated byte buffer into an owned std::vector,
// then release the yffi heap allocation. The vector handles its own dtor.
static std::vector<std::uint8_t> takeYffiBytes(char* buf, std::uint32_t len) {
    if (!buf || len == 0) {
        if (buf) ybinary_destroy(buf, len);
        return {};
    }
    const auto* p = reinterpret_cast<const std::uint8_t*>(buf);
    std::vector<std::uint8_t> out(p, p + len);
    ybinary_destroy(buf, len);
    return out;
}

std::vector<std::uint8_t> Transaction::stateVector() const {
    std::uint32_t len = 0;
    char* buf = ytransaction_state_vector_v1(raw(), &len);
    return takeYffiBytes(buf, len);
}

std::vector<std::uint8_t> Transaction::stateDiff(ByteView remoteSv) const {
    std::uint32_t len = 0;
    char* buf = ytransaction_state_diff_v1(
        raw(),
        reinterpret_cast<const char*>(remoteSv.data),
        static_cast<std::uint32_t>(remoteSv.len),
        &len);
    return takeYffiBytes(buf, len);
}

void Transaction::apply(ByteView diff) {
    ytransaction_apply(raw(),
                       reinterpret_cast<const char*>(diff.data),
                       static_cast<std::uint32_t>(diff.len));
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
    const int64_t* p = youtput_read_long(_out);
    if (!p) return std::nullopt;
    return static_cast<long long>(*p);
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
    // yffi ≥0.10: youtput_read_float returns const double* (was float* at 0.9.3).
    const double* p = youtput_read_float(_out);
    if (!p) return std::nullopt;
    return *p;
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
// Historical note: yrs v0.9.3's YInput::integrate had an infinite-loop bug for
// prefilled shared maps (the Y_MAP loop never incremented its index). That bug
// is fixed in the current 0.26.0 submodule, so a direct prefilled
// yinput_ymap insert would now work. We keep the empty-then-populate pattern
// anyway: it's the same path upstream's own FFI tests exercise for nested
// shared types, and collapsing it is a pure optimization with no functional
// payoff. (Stale 0.9.3 patch: docs/patches/yrs-0.9.3-yinput-ymap-integrate-loop.patch.)
namespace {
void fill_map(Branch* m, YTransaction* txn, const Input& in);
void fill_array(Branch* a, YTransaction* txn, const Input& in);

// Insert `in` into map branch `m` under `key`.
void put_in_map(Branch* m, YTransaction* txn, const char* key, const Input& in) {
    using K = Input::Kind;
    switch (in.kind()) {
        case K::Str:     { YInput v = yinput_string(in.strVal().c_str()); ymap_insert(m, txn, key, &v); return; }
        case K::Long:    { YInput v = yinput_long(in.longVal());          ymap_insert(m, txn, key, &v); return; }
        case K::Double:  { YInput v = yinput_float(in.doubleVal());       ymap_insert(m, txn, key, &v); return; }
        case K::Boolean: { YInput v = yinput_bool(in.boolVal() ? 1 : 0);  ymap_insert(m, txn, key, &v); return; }
        case K::Map: {
            YInput empty = yinput_ymap(nullptr, nullptr, 0);
            ymap_insert(m, txn, key, &empty);
            YOutput* o = ymap_get(m, txn, key);   // inner branch, owned by the doc
            fill_map(youtput_read_ymap(o), txn, in);
            youtput_destroy(o);
            return;
        }
        case K::Array: {
            YInput empty = yinput_yarray(nullptr, 0);
            ymap_insert(m, txn, key, &empty);
            YOutput* o = ymap_get(m, txn, key);
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
        case K::Str:     { YInput v = yinput_string(in.strVal().c_str()); yarray_insert_range(a, txn, index, &v, 1); return; }
        case K::Long:    { YInput v = yinput_long(in.longVal());          yarray_insert_range(a, txn, index, &v, 1); return; }
        case K::Double:  { YInput v = yinput_float(in.doubleVal());       yarray_insert_range(a, txn, index, &v, 1); return; }
        case K::Boolean: { YInput v = yinput_bool(in.boolVal() ? 1 : 0);  yarray_insert_range(a, txn, index, &v, 1); return; }
        case K::Map: {
            YInput empty = yinput_ymap(nullptr, nullptr, 0);
            yarray_insert_range(a, txn, index, &empty, 1);
            YOutput* o = yarray_get(a, txn, index);
            fill_map(youtput_read_ymap(o), txn, in);
            youtput_destroy(o);
            return;
        }
        case K::Array: {
            YInput empty = yinput_yarray(nullptr, 0);
            yarray_insert_range(a, txn, index, &empty, 1);
            YOutput* o = yarray_get(a, txn, index);
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
    YInput v = yinput_long(value);
    ymap_insert(_branch, _txn->raw(), key, &v);
}

void Map::insert(const char* key, const char* value) {
    YInput v = yinput_string(value);
    ymap_insert(_branch, _txn->raw(), key, &v);
}

void Map::insert(const char* key, double value) {
    YInput v = yinput_float(value);
    ymap_insert(_branch, _txn->raw(), key, &v);
}

void Map::insert(const char* key, const Input& value) {
    put_in_map(_branch, _txn->raw(), key, value);
}

Output Map::get(const char* key) const {
    return Output(ymap_get(_branch, _txn->raw(), key), _txn);
}

int Map::len() const {
    return static_cast<int>(ymap_len(_branch, _txn->raw()));
}

// ─── Array ────────────────────────────────────────────────────────────────────

void Array::insertLong(int index, long long value) {
    YInput v = yinput_long(value);
    yarray_insert_range(_branch, _txn->raw(), index, &v, 1);
}

void Array::insertRange(int index, const long long* values, int count) {
    // yffi takes an array of YInput. Build one on the heap (small alloc;
    // count is bounded by caller intent — not concerned about overflow).
    std::vector<YInput> inputs;
    inputs.reserve(static_cast<std::size_t>(count));
    for (int i = 0; i < count; ++i) {
        inputs.push_back(yinput_long(values[i]));
    }
    yarray_insert_range(_branch, _txn->raw(), index, inputs.data(), count);
}

void Array::insert(int index, const Input& value) {
    put_in_array(_branch, _txn->raw(), index, value);
}

void Array::remove(int index, int count) {
    // yffi panics if [index, index+count) escapes the array bounds; guard.
    // yarray_len takes no txn in yffi ≥0.10 (asymmetric vs ymap_len).
    if (count <= 0) return;
    const int n = static_cast<int>(yarray_len(_branch));
    if (index < 0 || index + count > n) return;
    yarray_remove_range(_branch, _txn->raw(), index, count);
}

void Array::push(const Input& value) {
    insert(len(), value);
}

Output Array::get(int index) const {
    return Output(yarray_get(_branch, _txn->raw(), index), _txn);
}

int Array::len() const {
    return static_cast<int>(yarray_len(_branch));
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
struct DocUpdatesTrampoline {
    std::function<void(ByteView)> cb;
};
struct DeepTrampoline {
    std::function<void(const std::vector<DeepPath>&)> cb;
};

// Decode one yffi event's path (relative to the observed root) into a DeepPath.
// The path accessor is type-specific (selected by YEvent::tag); the segments are
// owned by yffi and must be released with ypath_destroy.
DeepPath decode_event_path(const YEvent& ev) {
    std::uint32_t len = 0;
    YPathSegment* segs = nullptr;
    switch (ev.tag) {
        case Y_ARRAY: segs = yarray_event_path(&ev.content.array, &len); break;
        case Y_MAP:   segs = ymap_event_path(&ev.content.map, &len);     break;
        case Y_TEXT:  segs = ytext_event_path(&ev.content.text, &len);   break;
        default:      return {};   // XML / weak types don't occur in the level Doc
    }
    DeepPath path;
    path.reserve(len);
    for (std::uint32_t i = 0; i < len; ++i) {
        PathSegment ps{};
        if (segs[i].tag == Y_EVENT_PATH_INDEX) {
            ps.isIndex = true;
            ps.index   = segs[i].value.index;
        } else {  // Y_EVENT_PATH_KEY
            ps.isIndex = false;
            ps.key     = segs[i].value.key ? segs[i].value.key : "";
        }
        path.push_back(std::move(ps));
    }
    if (segs) ypath_destroy(segs, len);
    return path;
}

extern "C" void wfcrdt_map_trampoline(void* state, const YMapEvent* e) {
    auto* t = static_cast<MapTrampoline*>(state);
    t->cb(e);
}
extern "C" void wfcrdt_array_trampoline(void* state, const YArrayEvent* e) {
    auto* t = static_cast<ArrayTrampoline*>(state);
    t->cb(e);
}
// yffi ≥0.10 doc-updates callback signature: (void*, uint32_t len, const char* data).
extern "C" void wfcrdt_doc_updates_trampoline(void* state, std::uint32_t len, const char* data) {
    auto* t = static_cast<DocUpdatesTrampoline*>(state);
    t->cb(ByteView{reinterpret_cast<const std::uint8_t*>(data), static_cast<std::size_t>(len)});
}
// yobserve_deep callback: (void*, uint32_t count, const YEvent*) — `count`
// events, one per nested type changed in the committing transaction.
extern "C" void wfcrdt_deep_trampoline(void* state, std::uint32_t count, const YEvent* evs) {
    auto* t = static_cast<DeepTrampoline*>(state);
    std::vector<DeepPath> paths;
    paths.reserve(count);
    for (std::uint32_t i = 0; i < count; ++i) paths.push_back(decode_event_path(evs[i]));
    t->cb(paths);
}

}  // namespace

Subscription Doc::observeUpdates(std::function<void(ByteView)> cb) {
    auto* t = new DocUpdatesTrampoline{std::move(cb)};
    YSubscription* sub = ydoc_observe_updates_v1(_doc, t, &wfcrdt_doc_updates_trampoline);
    return Subscription(sub, SubKind::DocUpdates, t);
}

Subscription Map::observe(std::function<void(const YMapEvent*)> cb) {
    auto* t = new MapTrampoline{std::move(cb)};
    YSubscription* sub = ymap_observe(_branch, t, &wfcrdt_map_trampoline);
    return Subscription(sub, SubKind::Map, t);
}

Subscription Array::observe(std::function<void(const YArrayEvent*)> cb) {
    auto* t = new ArrayTrampoline{std::move(cb)};
    YSubscription* sub = yarray_observe(_branch, t, &wfcrdt_array_trampoline);
    return Subscription(sub, SubKind::Array, t);
}

Subscription Array::observeDeep(std::function<void(const std::vector<DeepPath>&)> cb) {
    auto* t = new DeepTrampoline{std::move(cb)};
    YSubscription* sub = yobserve_deep(_branch, t, &wfcrdt_deep_trampoline);
    return Subscription(sub, SubKind::Deep, t);
}

// ─── Subscription ─────────────────────────────────────────────────────────────

Subscription::Subscription(YSubscription* sub, SubKind kind, void* heapTrampoline)
    : _sub(sub), _kind(kind), _heap(heapTrampoline) {}

namespace {
void subscription_destroy(YSubscription* sub, SubKind kind, void* heap) {
    if (!sub) return;
    yunobserve(sub);   // releases the callback; one entry point for all kinds
    switch (kind) {
        case SubKind::Map:        delete static_cast<MapTrampoline*>(heap);        break;
        case SubKind::Array:      delete static_cast<ArrayTrampoline*>(heap);      break;
        case SubKind::DocUpdates: delete static_cast<DocUpdatesTrampoline*>(heap); break;
        case SubKind::Deep:       delete static_cast<DeepTrampoline*>(heap);       break;
    }
}
}  // namespace

Subscription::~Subscription() {
    subscription_destroy(_sub, _kind, _heap);
}

Subscription::Subscription(Subscription&& other) noexcept
    : _sub(other._sub), _kind(other._kind), _heap(other._heap) {
    other._sub = nullptr;
    other._heap = nullptr;
}

Subscription& Subscription::operator=(Subscription&& other) noexcept {
    if (this != &other) {
        subscription_destroy(_sub, _kind, _heap);
        _sub  = other._sub;
        _kind = other._kind;
        _heap = other._heap;
        other._sub = nullptr;
        other._heap = nullptr;
    }
    return *this;
}

// ─── UndoManager ────────────────────────────────────────────────────────────

UndoManager::UndoManager(Doc& doc, int captureTimeoutMillis) : _mgr(nullptr) {
    YUndoManagerOptions opts{};
    opts.capture_timeout_millis = captureTimeoutMillis;
    _mgr = yundo_manager(doc.raw(), &opts);
    // Track only local edits. With kOriginLocal in the origin set, a txn tagged
    // kOriginRemote (Doc::beginRemote) is never recorded — undo is local-only.
    if (_mgr)
        yundo_manager_add_origin(_mgr, sizeof(kOriginLocal) - 1, kOriginLocal);
}

UndoManager::~UndoManager() {
    if (_mgr) yundo_manager_destroy(_mgr);
}

UndoManager::UndoManager(UndoManager&& other) noexcept : _mgr(other._mgr) {
    other._mgr = nullptr;
}

UndoManager& UndoManager::operator=(UndoManager&& other) noexcept {
    if (this != &other) {
        if (_mgr) yundo_manager_destroy(_mgr);
        _mgr = other._mgr;
        other._mgr = nullptr;
    }
    return *this;
}

void UndoManager::addScope(const Map& root) {
    if (_mgr && root._branch) yundo_manager_add_scope(_mgr, root._branch);
}

void UndoManager::addScope(const Array& root) {
    if (_mgr && root._branch) yundo_manager_add_scope(_mgr, root._branch);
}

bool UndoManager::undo() {
    // yundo_manager_undo opens its own internal write txn — the caller must hold
    // no live wfcrdt txn (true at frame top). Returns Y_FALSE on an empty stack.
    return _mgr && yundo_manager_undo(_mgr);
}

bool UndoManager::redo() {
    return _mgr && yundo_manager_redo(_mgr);
}

int UndoManager::undoStackLen() const {
    return _mgr ? static_cast<int>(yundo_manager_undo_stack_len(_mgr)) : 0;
}

int UndoManager::redoStackLen() const {
    return _mgr ? static_cast<int>(yundo_manager_redo_stack_len(_mgr)) : 0;
}

void UndoManager::stopCapturing() {
    if (_mgr) yundo_manager_stop(_mgr);
}

void UndoManager::clear() {
    if (_mgr) yundo_manager_clear(_mgr);
}

}  // namespace wfcrdt
