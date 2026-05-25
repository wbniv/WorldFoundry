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
        auto barr = btx.array("content");   // resolve root before apply opens the txn
        btx.apply(wfcrdt::ByteView{diff.data(), diff.size()});
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

// Native UndoManager: a tracked-scope array edit is reversible, redoable, and
// undo() bottoms out on an empty stack. stopCapturing() forces a step boundary
// so each insert is its own undo step (deterministic regardless of the 500 ms
// coalescing timer — here disabled with timeout 0).
static int test_undo_redo_basic() {
    wfcrdt::Doc doc;
    wfcrdt::UndoManager undo(doc, /*captureTimeoutMillis=*/0);
    CHECK(undo.valid(), "UndoManager should be valid");
    { auto txn = doc.begin(); undo.addScope(txn.array("content")); }

    { auto txn = doc.begin(); txn.array("content").insertLong(0, 10); }
    undo.stopCapturing();
    { auto txn = doc.begin(); auto c = txn.array("content"); c.insertLong(c.len(), 20); }

    { auto txn = doc.begin(); CHECK(txn.array("content").len() == 2, "len == 2 before undo"); }
    CHECK(undo.canUndo() && undo.undoStackLen() == 2, "two undo steps recorded");

    CHECK(undo.undo(), "first undo() returns true");
    { auto txn = doc.begin(); CHECK(txn.array("content").len() == 1, "len == 1 after one undo"); }
    CHECK(undo.undo(), "second undo() returns true");
    { auto txn = doc.begin(); CHECK(txn.array("content").len() == 0, "len == 0 after two undos"); }
    CHECK(!undo.undo(), "undo() on empty stack returns false");

    CHECK(undo.canRedo(), "canRedo true after undo");
    CHECK(undo.redo(), "redo() returns true");
    { auto txn = doc.begin(); CHECK(txn.array("content").len() == 1, "len == 1 after redo"); }
    return 0;
}

// Local-only-in-collab: a remote-origin edit (Doc::beginRemote) is NOT captured,
// so Ctrl+Z never reverts a peer's change — it only removes this editor's own
// local edit, leaving the remote element intact.
static int test_undo_skips_remote_origin() {
    wfcrdt::Doc doc;
    wfcrdt::UndoManager undo(doc, /*captureTimeoutMillis=*/0);
    { auto txn = doc.begin(); undo.addScope(txn.array("content")); }

    { auto txn = doc.beginRemote(); txn.array("content").insertLong(0, 99); }   // peer edit
    CHECK(!undo.canUndo() && undo.undoStackLen() == 0,
          "remote edit must not enter undo history");

    { auto txn = doc.begin(); auto c = txn.array("content"); c.insertLong(c.len(), 7); }  // local edit
    CHECK(undo.undoStackLen() == 1, "local edit captured");

    CHECK(undo.undo(), "undo removes the local edit");
    {
        auto txn = doc.begin();
        auto c = txn.array("content");
        CHECK(c.len() == 1, "remote element survives local undo");
        auto v = c.get(0).readLong();
        CHECK(v.has_value() && *v == 99, "surviving element is the remote one");
    }
    return 0;
}

// Collab local-only undo across a real sync round-trip. An edit that originated
// as a LOCAL txn on doc A, after traveling the (Yjs v1) wire to doc B and being
// applied via beginRemote(), must NOT enter B's undo history — origins aren't in
// the wire format, so B's apply-txn origin governs B's capture. Mirrors the relay
// (stateDiff/apply): B's Ctrl+Z can't revert A's edit; A's own Ctrl+Z reverts it
// and the revert syncs back to B.
static int test_undo_local_only_across_sync() {
    wfcrdt::Doc a, b;
    wfcrdt::UndoManager ua(a, /*captureTimeoutMillis=*/0);
    wfcrdt::UndoManager ub(b, /*captureTimeoutMillis=*/0);
    { auto t = a.begin(); ua.addScope(t.array("content")); }
    { auto t = b.begin(); ub.addScope(t.array("content")); }

    // A makes a local edit.
    { auto t = a.begin(); t.array("content").insertLong(0, 42); }
    CHECK(ua.undoStackLen() == 1, "A captured its own local edit");

    // Sync A→B (full diff; B applies as REMOTE — resolve root before apply opens the txn).
    {
        std::vector<std::uint8_t> diff;
        { auto t = a.begin(); diff = t.stateDiff(wfcrdt::ByteView{nullptr, 0}); }
        auto t = b.beginRemote();
        auto barr = t.array("content");
        t.apply(wfcrdt::ByteView{diff.data(), diff.size()});
        CHECK(barr.len() == 1, "B received A's edit");
        auto v = barr.get(0).readLong();
        CHECK(v.has_value() && *v == 42, "B sees A's value");
    }
    // The remote edit is NOT in B's undo history — B's Ctrl+Z is a no-op on it.
    CHECK(ub.undoStackLen() == 0, "remote edit not captured on B");
    CHECK(!ub.undo(), "B's undo() is a no-op (nothing local to undo)");
    { auto t = b.begin(); CHECK(t.array("content").len() == 1, "A's edit survives B's undo"); }

    // A undoes its OWN edit; the revert syncs to B (incremental diff vs B's SV).
    CHECK(ua.undo(), "A reverts its own edit");
    { auto t = a.begin(); CHECK(t.array("content").len() == 0, "A's edit reverted locally"); }
    {
        std::vector<std::uint8_t> bsv;
        { auto t = b.begin(); bsv = t.stateVector(); }
        std::vector<std::uint8_t> diff;
        { auto t = a.begin(); diff = t.stateDiff(wfcrdt::ByteView{bsv.data(), bsv.size()}); }
        auto t = b.beginRemote();
        auto barr = t.array("content");
        t.apply(wfcrdt::ByteView{diff.data(), diff.size()});
        CHECK(barr.len() == 0, "B sees A's revert");
    }
    // B's undo history stayed empty throughout (it never made a local edit).
    CHECK(ub.undoStackLen() == 0, "B undo stack still empty after sync round-trip");
    return 0;
}

// Deep observer (yobserve_deep): fires for a field-leaf edit many levels below
// the observed root, delivering a path whose first segment is the actor's
// content[] index — the basis for the CRDT→engine bridge's remote/replay/DAP
// field propagation (docs/plans/2026-05-25-observe-deep-bridge.md). Also checks
// the structural-vs-field discrimination the bridge relies on: a direct child
// add to the observed array yields an empty-path (root-level) event.
static int test_deep_observer() {
    wfcrdt::Doc doc;
    // content = [ actor0, actor1 ]; actor1 carries items=[ fieldChunk ].
    {
        auto txn = doc.begin();
        auto content = txn.array("content");
        content.push(wfcrdt::Input::map().set("name", wfcrdt::Input::str("actor0")));
        content.push(wfcrdt::Input::map()
            .set("name", wfcrdt::Input::str("actor1"))
            .set("items", wfcrdt::Input::array()
                .push(wfcrdt::Input::map().set("text", wfcrdt::Input::str("old")))));
    }

    std::vector<wfcrdt::DeepPath> last;
    int fires = 0;
    wfcrdt::Subscription sub = [&]() {
        auto txn = doc.begin();
        auto content = txn.array("content");
        return content.observeDeep([&](const std::vector<wfcrdt::DeepPath>& evs) {
            last = evs;
            ++fires;
        });
    }();

    // (1) Mutate a leaf deep under content[1]: set a key on content[1].items[0].
    {
        auto txn = doc.begin();
        auto content = txn.array("content");
        auto field = content.get(1).asMap().get("items").asArray().get(0).asMap();
        CHECK(field.valid(), "navigated to content[1].items[0] map");
        field.insert("n", static_cast<long long>(7));
    }
    CHECK(fires == 1, "deep observer fired once on a nested-leaf edit");
    bool found = false;
    for (const auto& p : last) {
        if (!p.empty() && p[0].isIndex && p[0].index == 1) {
            found = true;
            bool key_ok = false;
            for (const auto& seg : p)
                if (!seg.isIndex && seg.key == "items") key_ok = true;
            CHECK(key_ok, "deep path includes the 'items' key segment");
        }
    }
    CHECK(found, "deep path[0] resolves to actor index 1");

    // (2) A direct child add is structural — its event path is empty, which is how
    // the bridge tells a structural edit (rebuild) from a field edit (propagate).
    last.clear();
    fires = 0;
    {
        auto txn = doc.begin();
        auto content = txn.array("content");
        content.push(wfcrdt::Input::map().set("name", wfcrdt::Input::str("actor2")));
    }
    CHECK(fires == 1, "deep observer fired once on a structural add");
    bool has_empty = false;
    for (const auto& p : last)
        if (p.empty()) has_empty = true;
    CHECK(has_empty, "structural add yields an empty-path (root-level) event");

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
    rc |= test_undo_redo_basic();
    rc |= test_undo_skips_remote_origin();
    rc |= test_undo_local_only_across_sync();
    rc |= test_deep_observer();
    if (rc == 0) {
        std::printf("wfcrdt_wrapper_test: OK (14/14 tests passed — incl. nested map/array + native undo + collab local-only + deep observer)\n");
    }
    return rc;
}
