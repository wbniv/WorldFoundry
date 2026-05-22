// engine/crdt/wfcrdt.hpp
//
// C++17 RAII wrapper around the Yrs C ABI (libyrs.h). Move-only types;
// destructors release their underlying yffi handles. The editor's CRDT
// bridge is the primary consumer.
//
// Plan: docs/plans/2026-05-19-wfcrdt-cpp-raii-wrapper.md

#pragma once

#include <cstddef>
#include <cstdint>
#include <functional>
#include <optional>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

// Forward declarations of the C ABI's opaque types so callers don't need
// to include libyrs.h transitively.
struct YDoc;
// yffi ≥0.10 declares this as `typedef struct TransactionInner YTransaction`
// (an alias to an opaque inner struct), not a `struct YTransaction` tag — so we
// must mirror that exact spelling or the redeclaration conflicts when this
// header and libyrs.h are both visible (in wfcrdt.cpp).
typedef struct TransactionInner YTransaction;
struct Branch;
struct YOutput;
struct YMapEvent;
struct YArrayEvent;
struct YAfterTransactionEvent;
struct YSubscription;   // yffi ≥0.10: observers return an owned YSubscription*
struct YUndoManager;    // native undo/redo (yffi ≥0.16) — see UndoManager below

namespace wfcrdt {

// Transaction origin tags. Local edits — every Doc::begin() — carry kOriginLocal
// and are the only transactions an UndoManager tracks; remote applies use
// Doc::beginRemote() (kOriginRemote) and stay out of undo history. This is what
// makes Ctrl+Z reverse only THIS editor's own edits in a collab session, with
// zero per-edit bookkeeping. See docs/plans/2026-05-22-yrs-upgrade-and-native-undo.md.
inline constexpr char kOriginLocal[]  = "local";
inline constexpr char kOriginRemote[] = "remote";

// Borrowed pointer + length view. Std::span replacement for C++17.
struct ByteView {
    const std::uint8_t* data;
    std::size_t len;
};

class Doc;
class Output;
class Input;
class Map;
class Array;
class Subscription;
class UndoManager;

// RAII wrapper around YTransaction*. Move-only. Commits on scope exit
// unless commit() or cancel() were called explicitly. Mirrors the
// lock_guard pattern.
//
// LAZY ACQUISITION (yffi ≥0.10): the underlying yffi write transaction is
// opened on the *first data operation*, not at begin(). Root-type resolution
// (ymap/yarray(doc,name)) opens its own internal transaction inside yffi, so it
// would deadlock against an already-open write txn — by deferring our txn until
// after the caller has fetched its root Map/Array, root resolution always runs
// with no txn held. See docs/plans/2026-05-22-yrs-upgrade-and-native-undo.md.
// Consequence: a transaction that touches *two* distinct roots must fetch both
// (txn.map(...)/txn.array(...)) before its first read/write.
class Transaction {
public:
    ~Transaction();

    Transaction(Transaction&& other) noexcept;
    Transaction& operator=(Transaction&& other) noexcept;
    Transaction(const Transaction&) = delete;
    Transaction& operator=(const Transaction&) = delete;

    // Commits the txn immediately (no-op if it was never lazily opened).
    // Subsequent operations are illegal; valid() returns false. Safe to skip —
    // dtor commits if needed.
    void commit();

    // Discards the txn. The CRDT effect of an uncommitted txn is
    // implementation-defined in yffi (today: equivalent to commit, since
    // there's no rollback). Reserved for future-proofing.
    void cancel();

    bool valid() const { return _docw != nullptr; }

    // Lazily opens (if needed) and returns the underlying yffi write txn.
    // Returns nullptr only after commit()/cancel()/move. Used by Map/Array/
    // Output for their data operations.
    YTransaction* raw() const;

    // Get-or-create root types. Resolves (and caches on the Doc) the root
    // branch *without* opening this transaction, then returns a Map/Array view
    // that drives its operations through raw().
    Map map(const char* name);
    Array array(const char* name);

    // State sync. stateVector encodes "what this Doc has seen"; stateDiff
    // takes a remote sv and returns "what we know that the remote doesn't";
    // apply consumes a diff from a peer.
    std::vector<std::uint8_t> stateVector() const;
    std::vector<std::uint8_t> stateDiff(ByteView remoteStateVector) const;
    void apply(ByteView diff);

private:
    friend class Doc;
    // `origin` (borrowed; must outlive the txn — in practice a static
    // kOriginLocal/kOriginRemote) tags the yffi write txn so an UndoManager can
    // gate capture on it. nullptr/0 leaves the origin unset.
    Transaction(Doc* docw, const char* origin, std::uint32_t originLen);
    Doc* _docw;                    // owning Doc wrapper (root cache + YDoc*)
    mutable YTransaction* _txn;    // lazily opened on first raw(); may be null
    const char*   _origin;         // borrowed origin bytes (or nullptr)
    std::uint32_t _originLen;
};

// RAII wrapper around YDoc*. The Doc owns the underlying y-crdt document.
class Doc {
public:
    Doc();
    ~Doc();

    Doc(Doc&& other) noexcept;
    Doc& operator=(Doc&& other) noexcept;
    Doc(const Doc&) = delete;
    Doc& operator=(const Doc&) = delete;

    // Open a local-edit transaction (origin = kOriginLocal). Every editor edit
    // path goes through here, so an UndoManager tracking kOriginLocal captures
    // them all with no per-call-site change.
    Transaction begin();

    // Open a transaction for applying a REMOTE update (origin = kOriginRemote).
    // Use this on the CollabDrain / initial-sync paths so peer edits never enter
    // this editor's undo history. Functionally identical to begin() otherwise.
    Transaction beginRemote();

    // Subscribe to all document updates (v1 encoding). The callback receives
    // the raw Yrs v1 update bytes every time a transaction commits. Wire the
    // callback to another Doc's Transaction::apply() for CRDT sync.
    Subscription observeUpdates(std::function<void(ByteView)> cb);

    bool valid() const { return _doc != nullptr; }
    YDoc* raw() const { return _doc; }

    // Resolve (get-or-create) a root Map/Array branch by name, caching the
    // stable Branch* for the Doc's lifetime. MUST be called with no wfcrdt
    // Transaction's yffi txn open on this Doc — root resolution opens its own
    // internal write txn in yffi and would otherwise deadlock. The Transaction
    // wrapper guarantees this via lazy txn acquisition. Returns nullptr only on
    // a moved-from Doc.
    Branch* rootBranch(const char* name, bool asArray);

private:
    YDoc* _doc;
    // Root branches are permanent for the Doc's lifetime, so we resolve each
    // name once and cache it; this is also what lets Transaction::map/array
    // hand back a branch without opening a (deadlock-prone) txn.
    std::unordered_map<std::string, Branch*> _roots;
};

// RAII wrapper around YOutput* (returned by ymap_get / yarray_get).
// Reads return std::optional<T> — empty when the stored value's type
// doesn't match the requested read.
class Output {
public:
    Output() : _out(nullptr), _txn(nullptr) {}
    ~Output();

    Output(Output&& other) noexcept;
    Output& operator=(Output&& other) noexcept;
    Output(const Output&) = delete;
    Output& operator=(const Output&) = delete;

    bool valid() const { return _out != nullptr; }

    std::optional<long long>   readLong()   const;
    std::optional<std::string> readString() const;
    std::optional<double>      readFloat()  const;

    // Nested-container reads: view a stored Y.Map / Y.Array. The returned view
    // is valid only within the transaction the parent get() was issued under.
    // Returns an invalid view if the stored value isn't a map / array.
    Map   asMap()   const;
    Array asArray() const;

private:
    friend class Map;
    friend class Array;
    Output(YOutput* out, Transaction* txn) : _out(out), _txn(txn) {}
    YOutput* _out;
    Transaction* _txn;   // owning transaction (lazily opens the yffi txn)
};

// Preliminary value tree for building nested containers in a single insert
// (the recursive CRDT chunk schema: Y.Map { children: Y.Array<chunk>, … }).
// Build with the static factories + set()/push(), then hand the root to
// Map::insert(key, Input) or Array::push(Input). Pure C++ data here; the
// .cpp materializes it into a yffi prelim YInput tree. Mirrors Yrs prelim
// values; see docs/plans/2026-05-19-wfcrdt-cpp-raii-wrapper.md (deferred
// "nested types" extension, triggered by the editor's Y.Doc population).
class Input {
public:
    // NB: `Boolean`, not `Bool` — Xlib's `#define Bool int` (pulled in by the
    // editor's X11/GLX headers ahead of this one) would mangle a `Bool` token.
    enum class Kind { Str, Long, Double, Boolean, Map, Array };

    static Input str(std::string s) { Input i; i._k = Kind::Str;    i._s = std::move(s); return i; }
    static Input lng(long long v)   { Input i; i._k = Kind::Long;   i._l = v; return i; }
    static Input dbl(double v)      { Input i; i._k = Kind::Double; i._d = v; return i; }
    static Input boolean(bool v)    { Input i; i._k = Kind::Boolean; i._b = v; return i; }
    static Input map()              { Input i; i._k = Kind::Map;    return i; }
    static Input array()            { Input i; i._k = Kind::Array;  return i; }

    Input& set(std::string key, Input value) { _m.emplace_back(std::move(key), std::move(value)); return *this; }
    Input& push(Input value)                 { _a.emplace_back(std::move(value)); return *this; }

    // Read-only accessors used by the .cpp YInput materializer.
    Kind kind() const { return _k; }
    const std::string& strVal() const { return _s; }
    long long longVal() const { return _l; }
    double doubleVal() const { return _d; }
    bool boolVal() const { return _b; }
    const std::vector<std::pair<std::string, Input>>& mapEntries() const { return _m; }
    const std::vector<Input>& arrayElems() const { return _a; }

private:
    Kind _k = Kind::Str;
    std::string _s;
    long long   _l = 0;
    double      _d = 0;
    bool        _b = false;
    std::vector<std::pair<std::string, Input>> _m;
    std::vector<Input> _a;
};

// Borrowed view of a root-level YMap. Does NOT own the Branch* —
// lifetime is tied to the owning Doc. Routes mutations through the
// active Transaction supplied at construction.
class Map {
public:
    void insert(const char* key, long long value);
    void insert(const char* key, const char* value);
    void insert(const char* key, double value);
    void insert(const char* key, const Input& value);   // nested map/array

    // False for the view returned by Output::asMap() on a non-map value.
    bool valid() const { return _branch != nullptr; }

    Output get(const char* key) const;
    int len() const;

    // Subscribe to map changes. Callback fires once per ytransaction_commit
    // that mutates this map. Destruction of the returned Subscription
    // unsubscribes; until then the callback persists across commits.
    Subscription observe(std::function<void(const YMapEvent*)> cb);

private:
    friend class Transaction;
    friend class Output;
    friend class UndoManager;   // reads _branch to register an undo scope
    Map(Branch* branch, Transaction* txn) : _branch(branch), _txn(txn) {}
    Branch* _branch;
    Transaction* _txn;   // owning transaction (lazily opens the yffi txn)
};

// Borrowed view of a root-level YArray. Same ownership rules as Map.
class Array {
public:
    void insertLong(int index, long long value);
    void insertRange(int index, const long long* values, int count);
    void insert(int index, const Input& value);   // nested map/array
    void push(const Input& value);                 // append at end
    void remove(int index, int count = 1);         // erase count elements at index

    // False for the view returned by Output::asArray() on a non-array value.
    bool valid() const { return _branch != nullptr; }

    Output get(int index) const;
    int len() const;

    // See Map::observe.
    Subscription observe(std::function<void(const YArrayEvent*)> cb);

private:
    friend class Transaction;
    friend class Output;
    friend class UndoManager;   // reads _branch to register an undo scope
    Array(Branch* branch, Transaction* txn) : _branch(branch), _txn(txn) {}
    Branch* _branch;
    Transaction* _txn;   // owning transaction (lazily opens the yffi txn)
};

// Subscription discriminator — selects the right yffi unobserve()
// + matches the trampoline type so its heap allocation can be freed.
enum class SubKind { Map, Array, DocUpdates };

// RAII handle for an observer subscription. Destruction calls the
// appropriate yffi unobserve and frees the heap std::function
// trampoline. Move-only.
class Subscription {
public:
    ~Subscription();
    Subscription(Subscription&& other) noexcept;
    Subscription& operator=(Subscription&& other) noexcept;
    Subscription(const Subscription&) = delete;
    Subscription& operator=(const Subscription&) = delete;

private:
    friend class Map;
    friend class Array;
    friend class Doc;
    // yffi ≥0.10: every observe() returns an owned YSubscription*, freed by a
    // single yunobserve() regardless of source — so one ctor covers all three
    // kinds. `_kind` only selects which trampoline type to delete.
    Subscription(YSubscription* sub, SubKind kind, void* heapTrampoline);

    YSubscription* _sub;   // owned; freed via yunobserve in the dtor
    SubKind _kind;
    void* _heap;  // owned MapTrampoline* / ArrayTrampoline* / DocUpdatesTrampoline*
};

// RAII wrapper around YUndoManager*. The native Yrs undo manager records every
// transaction that (a) mutates a tracked scope root AND (b) carries the tracked
// origin, making it reversible — undo()/redo() mutate the Doc directly, so the
// editor just re-syncs its UI/engine view afterwards. Construct AFTER the Doc's
// initial population so the load isn't itself an undo step. Tracks kOriginLocal,
// so remote applies (Doc::beginRemote) stay out of history — undo is local-only
// in collab. See docs/plans/2026-05-22-yrs-upgrade-and-native-undo.md.
//
// Constraint: undo()/redo() open their own internal write txn, so they must run
// with no wfcrdt Transaction's yffi txn live on the Doc (true at frame top).
class UndoManager {
public:
    // captureTimeoutMillis: edits within this window coalesce into a single undo
    // step — one Ctrl+Z reverses a whole gizmo drag or burst of typing. Call
    // stopCapturing() to force a step boundary between discrete structural ops.
    explicit UndoManager(Doc& doc, int captureTimeoutMillis = 500);
    ~UndoManager();

    UndoManager(UndoManager&& other) noexcept;
    UndoManager& operator=(UndoManager&& other) noexcept;
    UndoManager(const UndoManager&) = delete;
    UndoManager& operator=(const UndoManager&) = delete;

    // Track a root container so edits to it become undoable. Call once per root
    // (e.g. the "content" actor array) after construction.
    void addScope(const Map& root);
    void addScope(const Array& root);

    bool undo();   // revert the last step; false if the stack was empty
    bool redo();   // replay the last undone step; false if the stack was empty

    // yffi exposes stack lengths, not a can_undo predicate.
    bool canUndo() const { return undoStackLen() > 0; }
    bool canRedo() const { return redoStackLen() > 0; }
    int  undoStackLen() const;
    int  redoStackLen() const;

    void stopCapturing();   // cut a new undo-step boundary (yundo_manager_stop)
    void clear();           // drop both stacks

    bool valid() const { return _mgr != nullptr; }

private:
    YUndoManager* _mgr;
};

}  // namespace wfcrdt
