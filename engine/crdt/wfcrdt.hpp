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
    Output() : _out(nullptr) {}
    ~Output();

    Output(Output&& other) noexcept;
    Output& operator=(Output&& other) noexcept;
    Output(const Output&) = delete;
    Output& operator=(const Output&) = delete;

    bool valid() const { return _out != nullptr; }

    std::optional<long long>   readLong()   const;
    std::optional<std::string> readString() const;
    std::optional<double>      readFloat()  const;

private:
    friend class Map;
    friend class Array;
    explicit Output(YOutput* out) : _out(out) {}
    YOutput* _out;
};

// Borrowed view of a root-level YMap. Does NOT own the Branch* —
// lifetime is tied to the owning Doc. Routes mutations through the
// active Transaction supplied at construction.
class Map {
public:
    void insert(const char* key, long long value);
    void insert(const char* key, const char* value);
    void insert(const char* key, double value);

    Output get(const char* key) const;
    int len() const;

private:
    friend class Transaction;
    Map(Branch* branch, YTransaction* txn) : _branch(branch), _txn(txn) {}
    Branch* _branch;
    YTransaction* _txn;
};

// Borrowed view of a root-level YArray. Same ownership rules as Map.
class Array {
public:
    void insertLong(int index, long long value);
    void insertRange(int index, const long long* values, int count);

    Output get(int index) const;
    int len() const;

private:
    friend class Transaction;
    Array(Branch* branch, YTransaction* txn) : _branch(branch), _txn(txn) {}
    Branch* _branch;
    YTransaction* _txn;
};

// (Subscription body fleshed out in step 5.)

}  // namespace wfcrdt
