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

static int test_two_doc_state_diff() {
    // Doc A inserts 3 items, encodes a full diff (empty remote SV),
    // Doc B applies the diff, both end up with identical state vectors.
    wfcrdt::Doc a, b;

    {
        auto atx = a.begin();
        auto aarr = atx.array("content");
        long long items[3] = {1, 2, 3};
        aarr.insertRange(0, items, 3);
    }  // commit

    std::vector<std::uint8_t> diff;
    {
        auto atx = a.begin();
        diff = atx.stateDiff(wfcrdt::ByteView{nullptr, 0});
        CHECK(!diff.empty(), "stateDiff returned empty");
    }

    {
        auto btx = b.begin();
        btx.apply(wfcrdt::ByteView{diff.data(), diff.size()});
        auto barr = btx.array("content");
        CHECK(barr.len() == 3, "B's array != 3 after apply");
    }

    {
        auto atx = a.begin();
        auto btx = b.begin();
        auto asv = atx.stateVector();
        auto bsv = btx.stateVector();
        CHECK(asv.size() == bsv.size(), "state vector sizes differ");
        CHECK(asv == bsv, "state vectors differ byte-wise after sync");
    }
    return 0;
}

static int test_observer_fires() {
    // Mirrors C smoke: subscribe via a txn that DOESN'T mutate, commit
    // that registration txn, then a SECOND txn mutates → observer fires
    // on that second commit.
    wfcrdt::Doc doc;

    // First txn creates the array. Commit closes it.
    Branch* arrBranch = nullptr;
    {
        auto txn = doc.begin();
        auto arr = txn.array("content");
        (void)arr;
        // Branch identity is stable across txns for a given root name,
        // so we can re-fetch it later instead of stashing it.
    }
    (void)arrBranch;

    int fireCount = 0;
    wfcrdt::Subscription sub = [&]() {
        auto txn = doc.begin();
        auto arr = txn.array("content");
        return arr.observe([&](const YArrayEvent*) { ++fireCount; });
        // ~Transaction commits the registration txn here.
    }();

    // A separate txn now performs a mutation; commit on scope exit fires
    // the callback.
    {
        auto txn = doc.begin();
        auto arr = txn.array("content");
        arr.insertLong(0, 7);
    }
    CHECK(fireCount == 1, "observer didn't fire exactly once on commit");
    return 0;
}

static int test_observer_cancelled_before_commit() {
    // Destroying the Subscription before the mutating commit should
    // prevent the callback from firing.
    wfcrdt::Doc doc;
    {
        auto txn = doc.begin();
        (void)txn.array("a");
    }

    int fireCount = 0;
    {
        // Register subscription in its own commit-and-discard scope.
        wfcrdt::Subscription sub = [&]() {
            auto txn = doc.begin();
            auto arr = txn.array("a");
            return arr.observe([&](const YArrayEvent*) { ++fireCount; });
        }();

        // Now destroy the subscription BEFORE the mutating commit.
        { wfcrdt::Subscription moved = std::move(sub); }  // ~moved unsubscribes

        // Mutate in a fresh txn — observer is gone, no callback.
        {
            auto txn = doc.begin();
            auto arr = txn.array("a");
            arr.insertLong(0, 1);
        }
    }
    CHECK(fireCount == 0,
          "callback fired even after Subscription destroyed pre-commit");
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

// Nested containers (the recursive CRDT chunk schema): an array of maps, and a
// map holding a nested array — built via wfcrdt::Input, read back via
// Output::asMap / asArray.
static int test_nested_array_of_maps() {
    wfcrdt::Doc doc;
    {
        auto txn = doc.begin();
        auto content = txn.array("content");
        content.push(wfcrdt::Input::map()
                         .set("name", wfcrdt::Input::str("House"))
                         .set("hp",   wfcrdt::Input::lng(100)));
        content.push(wfcrdt::Input::map()
                         .set("name", wfcrdt::Input::str("Player"))
                         .set("hp",   wfcrdt::Input::lng(50)));
        CHECK(content.len() == 2, "content array should have 2 elements");
    }
    {
        auto txn = doc.begin();
        auto content = txn.array("content");
        CHECK(content.len() == 2, "content len after commit");

        auto m0 = content.get(0).asMap();
        auto n0 = m0.get("name").readString();
        CHECK(n0.has_value() && *n0 == "House", "elem0 name == House");
        auto h0 = m0.get("hp").readLong();
        CHECK(h0.has_value() && *h0 == 100, "elem0 hp == 100");

        auto n1 = content.get(1).asMap().get("name").readString();
        CHECK(n1.has_value() && *n1 == "Player", "elem1 name == Player");
    }
    {
        auto txn = doc.begin();
        auto root = txn.map("root");
        root.insert("kids", wfcrdt::Input::array()
                                .push(wfcrdt::Input::str("a"))
                                .push(wfcrdt::Input::str("b")));
    }
    {
        auto txn = doc.begin();
        auto kids = txn.map("root").get("kids").asArray();
        CHECK(kids.len() == 2, "nested array len == 2");
        auto k0 = kids.get(0).readString();
        CHECK(k0.has_value() && *k0 == "a", "nested array [0] == a");
    }
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
    rc |= test_two_doc_state_diff();
    rc |= test_observer_fires();
    rc |= test_observer_cancelled_before_commit();
    rc |= test_nested_array_of_maps();
    if (rc == 0) {
        std::printf("wfcrdt_wrapper_test: OK (10/10 tests passed — incl. nested map/array)\n");
    }
    return rc;
}
