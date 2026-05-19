// engine/crdt/wfcrdt.cpp — see wfcrdt.hpp.
//
// Plan: docs/plans/2026-05-19-wfcrdt-cpp-raii-wrapper.md

#include "wfcrdt.hpp"

#include <libyrs.h>

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

// Transaction::map / array / stateVector / stateDiff / apply are
// declared in wfcrdt.hpp but not yet defined — bodies land in
// subsequent plan steps. No caller exists yet, so the linker is happy.

}  // namespace wfcrdt
