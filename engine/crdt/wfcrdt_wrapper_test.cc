// engine/crdt/wfcrdt_wrapper_test.cc — exercises wfcrdt.hpp.
//
// Mirrors wfcrdt_smoke.c's five scenarios through the RAII wrapper.
// Each plan step adds the next scenario; build/link succeed throughout.
//
// Plan: docs/plans/2026-05-19-wfcrdt-cpp-raii-wrapper.md

#include "wfcrdt.hpp"

#include <cstdio>
#include <cstdlib>
#include <string>

#define CHECK(cond, msg)                                                       \
    do {                                                                       \
        if (!(cond)) {                                                         \
            std::fprintf(stderr, "wfcrdt_wrapper_test: FAIL %s (%s:%d)\n",     \
                         (msg), __FILE__, __LINE__);                           \
            return 1;                                                          \
        }                                                                      \
    } while (0)

static int test_doc_lifecycle() {
    wfcrdt::Doc doc;
    CHECK(doc.valid(), "default-constructed Doc should be valid");
    return 0;
}

static int test_move_semantics() {
    wfcrdt::Doc a;
    CHECK(a.valid(), "src Doc valid before move");
    wfcrdt::Doc b = std::move(a);
    CHECK(b.valid(), "dst Doc valid after move");
    CHECK(!a.valid(), "src Doc invalidated after move");
    return 0;
}

static int test_map_round_trip() {
    wfcrdt::Doc doc;
    {
        auto txn = doc.begin();
        auto meta = txn.map("meta");
        meta.insert("answer", static_cast<long long>(42));
        CHECK(meta.len() == 1, "map len != 1 after insert");

        auto got = meta.get("answer");
        CHECK(got.valid(), "ymap_get returned empty");
        auto v = got.readLong();
        CHECK(v.has_value(), "readLong returned nullopt");
        CHECK(*v == 42, "round-trip value mismatch");
        // ~Transaction commits.
    }
    return 0;
}

static int test_array_insert_len() {
    wfcrdt::Doc doc;
    auto txn = doc.begin();
    auto content = txn.array("content");

    long long items[3] = {10, 20, 30};
    content.insertRange(0, items, 3);
    CHECK(content.len() == 3, "array len != 3 after insertRange");

    auto got = content.get(1);
    CHECK(got.valid(), "yarray_get returned empty");
    auto v = got.readLong();
    CHECK(v.has_value() && *v == 20, "array[1] != 20");
    return 0;
}

static int test_array_single_insert() {
    wfcrdt::Doc doc;
    auto txn = doc.begin();
    auto a = txn.array("a");
    a.insertLong(0, 99);
    CHECK(a.len() == 1, "array len != 1 after insertLong");
    auto v = a.get(0).readLong();
    CHECK(v.has_value() && *v == 99, "single-insert round-trip mismatch");
    return 0;
}

static int test_map_type_mismatch_returns_nullopt() {
    wfcrdt::Doc doc;
    auto txn = doc.begin();
    auto m = txn.map("meta");
    m.insert("k", static_cast<long long>(123));
    auto got = m.get("k");
    CHECK(got.valid(), "get returned empty");
    CHECK(!got.readString().has_value(),
          "readString on long-typed entry should yield nullopt");
    CHECK(got.readLong().has_value(),
          "readLong on long-typed entry should yield value");
    return 0;
}

int main() {
    int rc = 0;
    rc |= test_doc_lifecycle();
    rc |= test_move_semantics();
    rc |= test_map_round_trip();
    rc |= test_map_type_mismatch_returns_nullopt();
    rc |= test_array_insert_len();
    rc |= test_array_single_insert();
    if (rc == 0) {
        std::printf("wfcrdt_wrapper_test: OK (6/6 tests passed — step 3)\n");
    }
    return rc;
}
