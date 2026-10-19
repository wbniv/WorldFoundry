# Plan — Fix the two-editor presence-broadcast invisibility, land the canonical b2 screenshot

**Date:** 2026-05-31
**Status:** **DONE 2026-05-31** — root cause was a bash-comment swallowing the `>/tmp/b2-A.log 2>&1 &` redirect+background in `tests/screenshot_two_peer_b2.sh`, so the editors ran sequentially with no log capture and never observed each other's broadcasts. The network path (CH_PRESENCE send → relay fan-out → receive → `peer_presence` populate) is functioning correctly. Diagnostic instrumentation around `main.cc:1346` (broadcast) and `:509` (receive) confirmed broadcasts, fan-out, and parsed-with-self-filter=0 are all working. The two-editor smoke now produces the canonical screenshots — Bob's PNG shows Alice's wireframe frustum + Peers (2) + Alice's `Jump` button. ~30 minutes total.
**Parent:** §2 of [B-leftovers plan](2026-05-31-shared-cursors-b-leftovers.md); follow-up to [`--relay --frames` crash fix](2026-05-31-fix-relay-frames-readactornames-crash.md) (`ebef9be7`).

## Context

After `ebef9be7` removed the relay-connect crash, both editors run the full session cleanly through [`tests/screenshot_two_peer_b2.sh`](../../tests/screenshot_two_peer_b2.sh). But Bob's screenshot still shows:

- the Collaborators voice/video panel claiming **"No peers in room yet"**,
- the Chat sidebar with no peer tiles (so `peer_presence` is empty), and
- no selection ring / camera frustum on Alice's actor.

The relay's CH_PRESENCE fan-out at [`wftools/wf_collab/src/bin/relay.rs:285`](../../wftools/wf_collab/src/bin/relay.rs) is correct (forwards 0x02 frames to every other peer in the room, excluding the sender). Both editors connect to the same room per their logs. So the failure is somewhere in the **CH_PRESENCE send → relay fan-out → CH_PRESENCE receive → `peer_presence` populate** chain. The B-leftovers verification screenshot still hinges on this; without it, the live overlay-through-the-network proof remains a TODO and the b2 work's value is locked behind a TODO.

## Phase 1 — Targeted diagnostics (~15 min)

Add tightly scoped fprintfs on both sides:

- **Broadcast side** at [`main.cc:~1157`](../../engine/wf_edit/main.cc) (the `if (c->relay_client.connected())` block that sends 0x02 every 0.1 s): on each send, print `peer_id_prefix` + `body.size()`.
- **Receive side** at [`main.cc:~509`](../../engine/wf_edit/main.cc) (the `ch == 0x02` branch of `CollabDrain`): print every frame's `frame.size()` + parsed `pid`, plus whether `pid == c->our_peer_id` (so we filter self-echo cleanly even with the relay's exclude-sender), plus the final `peer_presence` size after eviction.
- **Once per second** print `c->peer_presence.size()` so the steady state is visible in the log even if individual frames are noisy.
- **Relay-side**: confirm the relay is logging fan-out events. The `[relay]` log currently shows `joined`/`left` only — likely worth a one-line `eprintln!` in the fan-out branch ([`relay.rs:288`](../../wftools/wf_collab/src/bin/relay.rs)) to count outbound forwards. Optional but trivial.

Rerun `tests/screenshot_two_peer_b2.sh` and inspect `/tmp/b2-A.log`, `/tmp/b2-B.log`, `/tmp/b2-relay.log`.

## Phase 2 — Identify (~10 min)

The diagnostic logs will pin the failure to one of these layers; each has a different fix shape:

### H1: The broadcast never sends (`relay_client.connected()` is false)

If A's send-side log is silent, `relay_client.connected()` is returning false even though the higher-level "relay connected" message printed. The connection model has two stages (CONTROL join + WS-up); `connected()` may gate on something that isn't true yet in the screenshot timeframe.

**Fix shape:** loosen the gate to `relay_client.is_open()` or whatever the underlying socket state is; or fix the connected() return path.

### H2: Broadcasts send but the relay drops them

If A's send-side log fires but the relay log shows no fan-out, the relay's room state may not have the sender registered (CONTROL join racing the first PRESENCE send). The CONTROL join happens at [`main.cc:2922`](../../engine/wf_edit/main.cc) and PRESENCE broadcasts start as soon as `editor_build` first sees `relay_client.connected()` — there's a real race.

**Fix shape:** delay PRESENCE broadcasts until the room CONTROL handshake has been acknowledged, OR have the relay queue early PRESENCE frames per-peer until the CONTROL join completes.

### H3: Broadcasts reach Bob but parse fails

If A's send fires, the relay logs fan-out, but Bob's receive-side log is silent (no `[ci] PRESENCE recv`), the polling loop isn't pulling 0x02 frames. Either the ws_client buffers them but `poll()` returns false, or there's a channel multiplexing bug.

**Fix shape:** instrument the lower-level `relay_client.poll()` to log every frame popped from the receive queue regardless of channel.

### H4: Broadcasts parse but `peer_presence` stays empty

If Bob's receive-side log shows incoming 0x02 frames but `peer_presence` size stays 0, the parse path's `try { ... } catch (...) {}` is silently swallowing the JSON parse error, or `pid == c->our_peer_id` is matching every frame (sender filter bug — the relay supposedly excludes the sender, but maybe Bob is receiving his OWN echo because the relay's exclude isn't working).

**Fix shape:** if it's the catch-all, narrow it and log the exception. If it's the self-echo, the relay's exclude logic is broken; fix that (probably `relay.rs:288` `room.fanout(&bytes, &peer_id)` where peer_id might be empty or wrongly identified).

### H5: Bob's `CollabDrain` doesn't run in `--frames` mode

`CollabDrain(c)` is wired in `editor_build` at [`main.cc:1326`](../../engine/wf_edit/main.cc). If for some startup-path reason `editor_build` isn't being called in `--frames + --screenshot` mode (e.g. the screenshot path takes a separate engine loop), `CollabDrain` never fires.

**Fix shape:** explicitly ensure the screenshot path runs through the normal frame loop.

## Phase 3 — Fix + verify (~20 min)

Apply the fix matching Phase 2's identified hypothesis. Strip the Phase 1 fprintfs in the same commit per [`feedback_debug_instrumentation_teardown`](../../../../home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_debug_instrumentation_teardown.md).

### Verification

1. **Headless smoke:** `bash tests/screenshot_two_peer_b2.sh` produces two PNGs. Bob's PNG must show Alice's coloured selection ring and her camera frustum overlaid on the scene; the Chat sidebar's `Peers (N)` count must read `2` (or higher).
2. **Self-echo correctness:** Alice's PNG must NOT show her own frustum (the b2 overlay deliberately skips own-peer rendering — assert that the self-filter still works after any relay/sender fix).
3. **Live interactive use unchanged:** `task quick-tunnel`-driven 1-on-1 voice/video pair still works.

## Phase 4 — Close out (~10 min)

- Replace the `WF_EDIT_AUTO_JUMP` fake-peer screenshot link in [`wf-status.md`](../../wf-status.md) with the live two-editor PNGs (the fake-peer screenshot still demonstrates the rendering path; live screenshot demonstrates the network path).
- Flip the [B-leftovers plan](2026-05-31-shared-cursors-b-leftovers.md) §2 status from open → DONE.
- Flip the [TODO.md](../../TODO.md) row.
- Prepend a [`wf-status.md`](../../wf-status.md) history entry.

## Critical files

- `engine/wf_edit/main.cc` (broadcast `:1157`, receive `:509`) — Phase 1 instrumentation; possibly the fix in Phase 3 (H1, H2, H4, H5).
- `wftools/wf_collab/src/bin/relay.rs` (`:285` fanout) — Phase 1 optional instrumentation; possibly the fix (H2 race, H4 sender-exclude bug).
- `engine/wf_edit/ws_client.cc` — possibly Phase 3 fix if H3.
- `tests/screenshot_two_peer_b2.sh` — re-runs unchanged.
- `tests/screenshots/wfedit_shared_cursors_b2_live_{A,B}.png` — replaced with the visually-correct screenshots.
- `docs/plans/2026-05-31-shared-cursors-b-leftovers.md` — flip §2 to DONE.
- `wf-status.md` — history entry.

## Sizing

~45 min average-programmer scale. Most likely is H2 (CONTROL/PRESENCE race) or H4 (parse-side issue) based on shape; H1 / H5 would be more invasive but Phase 1 logs make the call cheaply.

## Out of scope

- Multi-peer voice/video, screen share, dedicated Peers panel.
- The relay's auth / persistence story (the bug is local to the in-room broadcast path).
- The pre-existing `WF_EDIT_FAKE_PEER` / `WF_EDIT_AUTO_JUMP` cleanup (still TODO).
