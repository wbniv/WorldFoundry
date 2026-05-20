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
#include <utility>
#include <vector>

// Forward declarations of the C ABI's opaque types so callers don't need
// to include libyrs.h transitively.
struct YDoc;
struct YTransaction;
struct Branch;
struct YOutput;
struct YMapEvent;
struct YArrayEvent;

namespace wfcrdt {

// Borrowed pointer + length view. Std::span replacement for C++17.
struct ByteView {
    const std::uint8_t* data;
    std::size_t len;
};

class Output;
class Input;
class Map;
class Array;
class Subscription;

// RAII wrapper around YTransaction*. Move-only. Commits on scope exit
// unless commit() or cancel() were called explicitly. Mirrors the
// lock_guard pattern.
class Transaction {
public:
    ~Transaction();

    Transaction(Transaction&& other) noexcept;
    Transaction& operator=(Transaction&& other) noexcept;
    Transaction(const Transaction&) = delete;
    Transaction& operator=(const Transaction&) = delete;

    // Commits the txn immediately. Subsequent operations are illegal;
    // valid() will return false. Safe to skip — dtor commits if needed.
    void commit();

    // Discards the txn. The CRDT effect of an uncommitted txn is
    // implementation-defined in yffi (today: equivalent to commit, since
    // there's no rollback). Reserved for future-proofing.
    void cancel();

    bool valid() const { return _txn != nullptr; }
    YTransaction* raw() const { return _txn; }

    // Get-or-create root types. The returned Map/Array borrows this
    // Transaction — its operations route through `_txn`.
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
    explicit Transaction(YDoc* doc);
    YTransaction* _txn;
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

    Transaction begin();

    bool valid() const { return _doc != nullptr; }
    YDoc* raw() const { return _doc; }

private:
    YDoc* _doc;
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
    Output(YOutput* out, YTransaction* txn) : _out(out), _txn(txn) {}
    YOutput* _out;
    YTransaction* _txn;
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
    Map(Branch* branch, YTransaction* txn) : _branch(branch), _txn(txn) {}
    Branch* _branch;
    YTransaction* _txn;
};

// Borrowed view of a root-level YArray. Same ownership rules as Map.
class Array {
public:
    void insertLong(int index, long long value);
    void insertRange(int index, const long long* values, int count);
    void insert(int index, const Input& value);   // nested map/array
    void push(const Input& value);                 // append at end

    // False for the view returned by Output::asArray() on a non-array value.
    bool valid() const { return _branch != nullptr; }

    Output get(int index) const;
    int len() const;

    // See Map::observe.
    Subscription observe(std::function<void(const YArrayEvent*)> cb);

private:
    friend class Transaction;
    friend class Output;
    Array(Branch* branch, YTransaction* txn) : _branch(branch), _txn(txn) {}
    Branch* _branch;
    YTransaction* _txn;
};

// Subscription discriminator — selects the right yffi unobserve()
// + matches the trampoline type so its heap allocation can be freed.
enum class SubKind { Map, Array };

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
    Subscription(Branch* target,
                 unsigned int subId,
                 SubKind kind,
                 void* heapTrampoline);

    Branch* _target;
    unsigned int _subId;
    SubKind _kind;
    void* _heap;  // owned MapTrampoline* / ArrayTrampoline*
};

}  // namespace wfcrdt
