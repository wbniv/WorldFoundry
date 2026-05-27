# Jolt defensive null — already implemented (no work needed)

**Date:** 2026-05-17
**Status:** DONE — already implemented in `7af255b` (predates this plan); confirmed in `dd5497c8`.

## Context

`gWatches` (actor → set of watched mailbox indices) and `gMailboxPrev` (change-detection cache) are never cleared when a debug-bridge client disconnects. Stale entries accumulate: a fresh reconnecting client sees noise from the prior session's watches, and `BroadcastMailboxes` continues scanning and emitting values for a dead fd. The fix is to post a `CLIENT_DISCONNECT` sentinel to the pending-update queue on disconnect; `DrainQueue` (game thread) handles it by clearing both maps.

## Critical file

`engine/stubs/debug_server.cc` — only file touched.

## Implementation

### 1. Extend `PendingUpdate::Kind` enum (line 262)

```cpp
// before:
enum Kind { SET_PROP, SET_TRANSFORM, PICK, UNDO_STEP, REVERT_ALL,
            WATCH, UNWATCH, SET_MAILBOX, INJECT_INPUT, SET_SHADER,
            RELOAD_SCRIPT, SCREENSHOT } kind;

// after:
enum Kind { SET_PROP, SET_TRANSFORM, PICK, UNDO_STEP, REVERT_ALL,
            WATCH, UNWATCH, SET_MAILBOX, INJECT_INPUT, SET_SHADER,
            RELOAD_SCRIPT, SCREENSHOT, CLIENT_DISCONNECT } kind;
```

### 2. Push sentinel in the disconnect handler (lines 492-498)

After `gClients.erase` and before `::close(fd)` is done, while still holding `gQueueMutex`, push a `CLIENT_DISCONNECT` update:

```cpp
{
    std::lock_guard<std::mutex> lk(gQueueMutex);
    ::close(fd);
    auto it = std::find(gClients.begin(), gClients.end(), fd);
    if (it != gClients.end()) gClients.erase(it);
    PendingUpdate disc;
    disc.kind = PendingUpdate::CLIENT_DISCONNECT;
    gQueue.push(disc);
}
std::fprintf(stderr, "[debug] client disconnected fd=%d\n", fd);
```

### 3. Handle `CLIENT_DISCONNECT` in `DrainQueue` (around line 900, after the UNWATCH case)

```cpp
case PendingUpdate::CLIENT_DISCONNECT:
    gWatches.clear();
    gMailboxPrev.clear();
    break;
```

## Why queue, not direct clear

`gWatches` and `gMailboxPrev` are documented "game-thread only — accessed exclusively in DrainQueue / BroadcastMailboxes" (line 204). The disconnect handler runs on the listener thread. Direct clear from the listener thread would be a data race; the queue is the existing cross-thread channel.

## Verification

1. Build: `task build` — confirm no new errors or warnings.
2. Run qbert_practice; connect a Python test client that issues a `watch` op, then disconnect it.
3. Re-connect a second client immediately; confirm no stale `mailbox_change` events arrive from the prior session.
4. Run the existing pytest bridge suite: `pytest tests/ -k debug` — confirm all tests still pass.
