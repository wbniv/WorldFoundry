// wfcrdt_sync_test.cpp — headless convergence test for Doc::observeUpdates.
// Plan: docs/plans/2026-05-21-realtime-coediting.md Phase 0

#include "wfcrdt.hpp"

#include <cassert>
#include <cstdio>
#include <string>

// Returns 0 on pass, 1 on failure.
static int check(const char* label, bool cond) {
    if (cond) {
        printf("PASS  %s\n", label);
        return 0;
    }
    fprintf(stderr, "FAIL  %s\n", label);
    return 1;
}

int main() {
    int failures = 0;

    // ── A→B convergence ──────────────────────────────────────────────────────
    {
        wfcrdt::Doc a, b;

        // Wire A's updates into B.
        wfcrdt::Subscription sub = a.observeUpdates([&b](wfcrdt::ByteView update) {
            auto txn = b.begin();
            txn.apply(update);
        });

        // Edit A: insert a string and a long into map "test".
        {
            auto txn = a.begin();
            auto m = txn.map("test");
            m.insert("greeting", "hello");
            m.insert("count", static_cast<long long>(42));
        }  // commit — observer fires synchronously, B.apply runs

        // Read B and confirm convergence.
        {
            auto txn = b.begin();
            auto m = txn.map("test");
            auto greeting = m.get("greeting").readString();
            auto count    = m.get("count").readLong();

            failures += check("A→B string",  greeting && *greeting == "hello");
            failures += check("A→B long",    count    && *count    == 42);
        }
    }

    // ── B→A convergence ──────────────────────────────────────────────────────
    {
        wfcrdt::Doc a, b;

        // Wire B's updates into A.
        wfcrdt::Subscription sub = b.observeUpdates([&a](wfcrdt::ByteView update) {
            auto txn = a.begin();
            txn.apply(update);
        });

        // Edit B.
        {
            auto txn = b.begin();
            auto m = txn.map("data");
            m.insert("value", "world");
        }

        {
            auto txn = a.begin();
            auto val = txn.map("data").get("value").readString();
            failures += check("B→A string", val && *val == "world");
        }
    }

    // ── Subscription RAII — unsubscribe before commit ─────────────────────────
    {
        wfcrdt::Doc a, b;
        {
            wfcrdt::Subscription sub = a.observeUpdates([&b](wfcrdt::ByteView update) {
                auto txn = b.begin();
                txn.apply(update);
            });
        }  // sub destroyed — unsubscribed

        // Edit after unsubscribe; B must NOT see it.
        {
            auto txn = a.begin();
            txn.map("after").insert("k", "v");
        }

        {
            auto txn = b.begin();
            auto val = txn.map("after").get("k").readString();
            failures += check("unsubscribe gate", !val);
        }
    }

    if (failures == 0) {
        printf("All tests passed.\n");
        return 0;
    }
    fprintf(stderr, "%d test(s) failed.\n", failures);
    return 1;
}
