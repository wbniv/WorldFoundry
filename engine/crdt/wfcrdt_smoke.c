/*
 * wfcrdt_smoke.c — exercises the Yrs C ABI through libwfcrdt.a.
 *
 * Each test must pass before this binary returns 0; any failure prints a
 * one-line diagnostic to stderr and returns non-zero so CTest / CI can
 * detect regressions.
 *
 * Plan: docs/plans/2026-05-18-yrs-c-abi-binding.md (step 5)
 * Yrs 0.9.3 → 0.26.0 ABI: docs/plans/2026-05-22-yrs-upgrade-and-native-undo.md
 *   - transactions: ytransaction_new(doc) → ydoc_write_transaction(doc, 0, NULL)
 *   - root types:   ymap/yarray now take the DOC, not the txn
 *   - reads/mutators on a map take the txn; ymap_get/ymap_len gain a txn arg
 *   - observers return an owned YSubscription*, freed by yunobserve()
 *   - binary buffers are char* / uint32_t (were unsigned char* / int)
 *
 * Coverage (matches plan's verification matrix):
 *   - YDoc lifecycle (ydoc_new / ydoc_destroy)
 *   - YMap root insert + get round-trip
 *   - YArray root insert + len
 *   - Two-Doc state-vector + state-diff Yjs-wire-format compat
 *   - YArray observer fires on commit
 */

#include <libyrs.h>

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(cond, msg)                                                     \
    do {                                                                     \
        if (!(cond)) {                                                       \
            fprintf(stderr, "wfcrdt_smoke: FAIL %s (%s:%d)\n",               \
                    (msg), __FILE__, __LINE__);                              \
            return 1;                                                        \
        }                                                                    \
    } while (0)

/* Observer callback — bumps the int* in `state` each time the array fires. */
static void on_array_change(void *state, const YArrayEvent *e) {
    (void)e;
    int *counter = (int *)state;
    *counter += 1;
}

static int test_doc_lifecycle(void) {
    YDoc *doc = ydoc_new();
    CHECK(doc, "ydoc_new returned NULL");
    ydoc_destroy(doc);
    return 0;
}

static int test_map_round_trip(void) {
    YDoc *doc = ydoc_new();
    Branch *meta = ymap(doc, "meta");
    YTransaction *txn = ydoc_write_transaction(doc, 0, NULL);

    YInput v = yinput_long(42);
    ymap_insert(meta, txn, "answer", &v);

    YOutput *out = ymap_get(meta, txn, "answer");
    CHECK(out, "ymap_get returned NULL");
    const int64_t *got = youtput_read_long(out);
    CHECK(got, "youtput_read_long returned NULL");
    CHECK(*got == 42, "round-trip value mismatch");
    youtput_destroy(out);

    CHECK(ymap_len(meta, txn) == 1, "ymap_len != 1");

    ytransaction_commit(txn);
    ydoc_destroy(doc);
    return 0;
}

static int test_array_insert_len(void) {
    YDoc *doc = ydoc_new();
    Branch *content = yarray(doc, "content");
    YTransaction *txn = ydoc_write_transaction(doc, 0, NULL);

    YInput items[3];
    items[0] = yinput_long(10);
    items[1] = yinput_long(20);
    items[2] = yinput_long(30);
    yarray_insert_range(content, txn, 0, items, 3);

    CHECK(yarray_len(content) == 3, "yarray_len != 3 after insert");

    ytransaction_commit(txn);
    ydoc_destroy(doc);
    return 0;
}

static int test_two_doc_state_diff(void) {
    /* Doc A: insert 3 items. Doc B: empty. Apply A's diff to B. Assert B
     * sees the 3 items and the wire-format state vectors match. */
    YDoc *a = ydoc_new();
    YDoc *b = ydoc_new();

    Branch *aarr = yarray(a, "content");
    YTransaction *atx = ydoc_write_transaction(a, 0, NULL);
    YInput items[3];
    items[0] = yinput_long(1);
    items[1] = yinput_long(2);
    items[2] = yinput_long(3);
    yarray_insert_range(aarr, atx, 0, items, 3);
    ytransaction_commit(atx);

    /* Encode A's full update (sv = NULL means snapshot of entire state). */
    YTransaction *atx2 = ydoc_write_transaction(a, 0, NULL);
    uint32_t diff_len = 0;
    char *diff = ytransaction_state_diff_v1(atx2, NULL, 0, &diff_len);
    CHECK(diff, "state_diff returned NULL");
    CHECK(diff_len > 0, "state_diff returned empty payload");
    ytransaction_commit(atx2);

    /* Apply A's diff to B. */
    Branch *barr = yarray(b, "content");
    YTransaction *btx = ydoc_write_transaction(b, 0, NULL);
    ytransaction_apply(btx, diff, diff_len);
    CHECK(yarray_len(barr) == 3, "B's array != 3 after apply");
    ytransaction_commit(btx);
    ybinary_destroy(diff, diff_len);

    /* State vectors must now match. */
    YTransaction *atx3 = ydoc_write_transaction(a, 0, NULL);
    YTransaction *btx3 = ydoc_write_transaction(b, 0, NULL);
    uint32_t asv_len = 0, bsv_len = 0;
    char *asv = ytransaction_state_vector_v1(atx3, &asv_len);
    char *bsv = ytransaction_state_vector_v1(btx3, &bsv_len);
    CHECK(asv && bsv, "state_vector returned NULL");
    CHECK(asv_len == bsv_len, "state vector lengths differ after sync");
    CHECK(memcmp(asv, bsv, (size_t)asv_len) == 0,
          "state vectors differ byte-wise after sync");
    ybinary_destroy(asv, asv_len);
    ybinary_destroy(bsv, bsv_len);
    ytransaction_commit(atx3);
    ytransaction_commit(btx3);

    ydoc_destroy(a);
    ydoc_destroy(b);
    return 0;
}

static int test_observer_fires(void) {
    YDoc *doc = ydoc_new();
    Branch *arr = yarray(doc, "content");

    int fire_count = 0;
    YSubscription *sub = yarray_observe(arr, &fire_count, on_array_change);

    YTransaction *txn1 = ydoc_write_transaction(doc, 0, NULL);
    YInput item = yinput_long(99);
    yarray_insert_range(arr, txn1, 0, &item, 1);
    ytransaction_commit(txn1);

    CHECK(fire_count == 1, "observer didn't fire exactly once");

    yunobserve(sub);
    ydoc_destroy(doc);
    return 0;
}

int main(void) {
    int rc = 0;
    rc |= test_doc_lifecycle();
    rc |= test_map_round_trip();
    rc |= test_array_insert_len();
    rc |= test_two_doc_state_diff();
    rc |= test_observer_fires();

    if (rc == 0) {
        printf("wfcrdt_smoke: OK (5/5 tests passed)\n");
    }
    return rc;
}
