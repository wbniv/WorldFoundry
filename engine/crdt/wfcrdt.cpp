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

// Transaction::stateVector / stateDiff / apply land in later steps.

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

}  // namespace wfcrdt
