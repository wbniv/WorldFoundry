# Plan — Real-time multi-user co-editing for wf-edit

**Date:** 2026-05-21

**Status:** Done — all 8 phases implemented (~2026-05-21, single session ~6 h).

## Context

The collaborative level editor (`wf-edit`) is the literal point of the project, but today it's effectively **single-user**: each instance has its own local CRDT `Doc`, and the only thing spanning instances is the voice/video call (UDP multicast). The headline "real-time multi-user co-editing over a network" capability is the ⏳ row in [`docs/wf-edit-manual.md`](../wf-edit-manual.md) and the unbuilt half of the [collaborative editor design doc](../investigations/2026-05-18-collaborative-level-editor-design.md). This plan builds it end-to-end: two+ editors join a room and edit the same level live — field edits, structural add/delete, presence, and chat — over a WebSocket relay with on-disk room persistence.

Confirmed scope: **WebSocket relay** (not LAN multicast); include **presence (cursors + selection rings)**, **text chat**, **lobby/`wfedit://` URLs**, and **relay disk persistence**; remote **add/delete reflects live** in the viewport (not reload).

This is a multi-week feature; it's phased so each phase is independently testable and committable. Order is by value — Phases 0–2 deliver working core sync; 3–7 add the rest.

### What already exists (reuse, don't rebuild)
- **CRDT update exchange** — `wfcrdt::Transaction::stateVector()/stateDiff()/apply()` ([`engine/crdt/wfcrdt.hpp:74-76`](../../engine/crdt/wfcrdt.hpp)); raw C ABI `ydoc_observe_updates_v1` / `ytransaction_apply` in [`wftools/y-crdt/tests-ffi/include/libyrs.h`](../../wftools/y-crdt/tests-ffi/include/libyrs.h). Yrs `yffi` crate is built editor-only via Corrosion ([`CMakeLists.txt:834-837`](../../CMakeLists.txt), [`engine/crdt/CMakeLists.txt`](../../engine/crdt/CMakeLists.txt)).
- **Room/peer/identity** — `CollabSession`, `PeerInfo`, `MakePeerId()` (UUID), and `RenderCollabPanel()` ([`engine/wf_edit/collab_session.{h,cc}`](../../engine/wf_edit/collab_session.h), [`collab_panel.{h,cc}`](../../engine/wf_edit/collab_panel.h)); the `--room <id>` flag in [`main.cc`](../../engine/wf_edit/main.cc).
- **CRDT→engine bridge** — `PropagateToEngine`, `TranslateField`, `InitBridgeMap`, `BridgeNotifyDelete/Duplicate`, `wfmut::SetActorPos/Orientation/Field/SpawnActor/RemoveActor` ([`engine/wf_edit/engine_bridge.{h,cc}`](../../engine/wf_edit/engine_bridge.h)).
- **Doc⇄level** — `LoadLevelTreeIntoDoc`, `ReadActorNames/Fields`, `WriteFieldLeaf`, `DeleteActor/DuplicateActor`, `SaveDocToLev` ([`engine/wf_edit/level_doc.cc`](../../engine/wf_edit/level_doc.cc), [`level_save`](../../engine/wf_edit/level_save.h)); `ResolveProperties` ([`property_panel.cc`](../../engine/wf_edit/property_panel.cc)); the game-thread drain pattern `RestApi_DrainQueue()` (called in `WFGame::StepFrame`).

### Hard constraints
- **Editor-only.** The relay, the WS client lib, and `wfcrdt` must never link into `libwfengine.a`/`wf_game` — game runtime build untouched (same posture as the resize fix).
- **Threading.** Networking runs on a background thread; **all** `wfcrdt::Doc` access, `PropagateToEngine`, and `wfmut` calls happen on the game thread, drained inside `editor_frame` (mirror `RestApi_DrainQueue`).
- **`.lev` round-trip stays byte-identical** for unedited levels — editor-only metadata (the per-actor `_eid`, Phase 3) must never leak into saved `.lev` output.
- New `.sh` scripts use `set -euo pipefail`.

## Relay protocol (kept simple — levels are small)
Avoid full y-sync step1/2 negotiation. The relay holds an **authoritative `yrs::Doc` per room**:
- On client join → relay sends the room's **full state** (`encode_state_as_update`) as one `UPDATE` message.
- Client/relay send local changes as `UPDATE` (Yrs v1 update bytes); relay **applies to the room Doc** (for persistence + late-joiners) and **fans out** to other peers.
- `PRESENCE` and `CHAT` are **opaque passthrough** (relay forwards to room peers, never persisted).
- Wire envelope: `[1 byte channel: SYNC|PRESENCE|CHAT|CONTROL][payload]`. Lobby = `CONTROL` request/response (or HTTP `GET /rooms`).

## Phases

### Phase 0 — `wfcrdt` update-observer wrapper + headless convergence test
Wrap `ydoc_observe_updates_v1`/`unobserve` as `wfcrdt::Doc::observeUpdates(std::function<void(ByteView)>)` returning a `Subscription` (mirror the existing `Map::observe` trampoline in [`wfcrdt.cpp`](../../engine/crdt/wfcrdt.cpp)). Add a headless test: two `Doc`s, wire A's `observeUpdates` → `B.apply()`, edit A, assert B converges (and back). Files: `engine/crdt/wfcrdt.{hpp,cpp}`, a `wfcrdt_sync` smoke test alongside `wfcrdt_smoke`.

### Phase 1 — `wf-relay` server + transport client lib (Rust)
New crate `wftools/wf_collab` with two targets sharing the envelope/codec:
- `[[bin]] wf-relay` — tokio + `tokio-tungstenite` WS server; per-room authoritative `yrs::Doc`; join→full-state, update→apply+fanout, presence/chat passthrough; `--port`, `--snapshot-dir`. Persistence stubbed (Phase 7).
- `[lib] crate-type=["staticlib"]` transport **client** — a dumb byte pipe over a C ABI: `wfc_connect(url, room, peer_id) -> handle`, `wfc_send(h, channel, bytes, len)`, `wfc_poll(h, &out)` (non-blocking, called per frame), `wfc_disconnect(h)`. Runs its own tokio runtime on a thread; thread-safe in/out channels; TLS via `tokio-tungstenite` for `wss://`. C header hand-written or cbindgen.
Wire into CMake via Corrosion next to the `yffi` import (editor-only). Smoke: a tiny CLI exercises two clients ↔ localhost relay.

### Phase 2 — editor ↔ relay live **field** sync (the core)
In [`main.cc`](../../engine/wf_edit/main.cc): add `--relay <url>`; on start, `wfc_connect`. Implement the simple protocol in C++ using `wfcrdt`: apply the join full-state `UPDATE`; on `observeUpdates` (local commit, game thread) → `wfc_send(SYNC, update)`; drain inbound in `editor_frame` (new `CollabDrain(c)` before the UI block) → `Doc.apply(update)`. After applying a remote update: `RefreshActorList(c)` (re-reads names, sets `fields_for=-1`), and for the selected actor re-resolve via `ResolveProperties(ReadActorFields(...))`, diff vs cached `c->props`, and `PropagateToEngine(selected, changed)` for each changed field. Add `EditorCtx` fields for the client handle + a stable local `peer_id`. Test: two `wf-edit` on a localhost relay editing the same `.lev` — a Position/Mass edit in one appears in the other's panel **and** viewport.

### Phase 3 — live remote **structural** edits (stable-id bridge)
Give each actor an **editor-only stable id**: on `LoadLevelTreeIntoDoc`, add an `_eid` (UUID) key to each actor chunk's map; `ReadActorNames/Fields` ignore it; **`SaveDocToLev` skips any key other than `chunk_type`/`items`** so `.lev` round-trips byte-identical (verify against the existing round-trip gate). Replace the bridge's positional `s_doc_to_engine` vector with an `eid → wfmut::ActorIdx` map. Add a `content`-array `observe` reconciler (game thread) that, for **both local and remote** structural changes, diffs present `_eid`s and calls `wfmut::SpawnActor`/`RemoveActor`, updating the map. Local `DoDelete/DoDuplicate` stop calling `BridgeNotify*` directly and rely on the observer (unifies local+remote). Files: `level_doc.cc`, `level_save`, `engine_bridge.{h,cc}`, `main.cc`. Test: remote add/delete reflects live in the other editor's viewport + Outliner.

### Phase 4 — presence (cursors + selection rings)
Ephemeral `PRESENCE` messages (throttled, ~10 Hz): `{peer_id, name, colour, selected_eid, cursor_ndc}`. Editor sends its own each frame; renders peers as an **ImGui overlay** — project the selected actor's world position to screen (using the now-correct projection from the resize fix) and draw a coloured ring + name label; draw cursor dots from `cursor_ndc`. Colour/name from a per-user identity (Phase 6); `peer_id` from `MakePeerId()`. No engine-render changes. Test: selection ring + cursor visible across two editors.

### Phase 5 — text chat sidebar
Vendor [`imgui_markdown`](https://github.com/juliettef/imgui_markdown) (header-only, MIT) under `third_party/`. `CHAT` messages over the transport; a Chat panel folded into the Collaborators sidebar ([`collab_panel.cc`](../../engine/wf_edit/collab_panel.cc)); send on enter, render history with `imgui_markdown`. Plaintext wire format. Test: messages exchange between two editors.

### Phase 6 — lobby, `wfedit://` URLs, identity persistence
Relay `CONTROL`/`GET /rooms` → active rooms + peer counts. Editor "Open" dialog with **Active / Recent / URL / New** tabs; parse `wfedit://<relay>/r/<room-id>`; `--relay`/`--room` remain the direct-join path. Persist identity (UUID + display name + colour), recent rooms, and relay URL under `$HOME/.config/wf-edit/`. Test: launch with no `--room`, pick a room from the lobby, join.

### Phase 7 — relay disk persistence
Relay snapshots each room to `<snapshot-dir>/<room>.ydoc` (`encode_state_as_update`), debounced 2 s edit-quiet / 10 s max-wait, **N=3 rotating generations**, through a `wrap: fn(&[u8]) -> Vec<u8>` hook (identity in v1, BYOK later). On room (re)create, load the newest valid `.ydoc`; empty → first joiner seeds it. Hibernate idle rooms to disk. Test: edit, restart `wf-relay`, a late-joiner gets the persisted state.

## Verification
- **Per phase:** the test named in each phase. Build the editor with `cmake --build build-editor --target wf_edit` (target is `wf_edit`, underscore — `wf-edit` is only the `OUTPUT_NAME` and silently no-ops); build the relay with `cargo build` / Corrosion. Confirm the binary mtime changed.
- **Game runtime untouched:** `cmake --build build-editor --target wf_game` (or the normal game build) still builds; `git diff` shows no `wfsource/` engine-library changes.
- **End-to-end (interactive, two instances on one box):** start `wf-relay` on localhost; launch two `wf-edit --relay ws://localhost:<port> --room demo` on the same `.lev`; in window A edit a field, add an actor, delete an actor, select an actor, send a chat — confirm each reflects in window B's viewport, Outliner, selection rings, and chat. (On-screen GL can't be auto-captured under Wayland — visual confirmation is the user's; the headless Phase 0 test + the bridge unit paths cover the non-visual logic.)
- **Round-trip safety (Phase 3):** the existing `.lev` round-trip identity gate passes unchanged for an unedited level (the `_eid` does not leak).
- **Persistence (Phase 7):** edit → kill relay → restart → late join shows prior state.

## Out of scope (this round)
Matrix/E2E chat backend, BYOK encryption (hook only), mDNS LAN discovery (v1.5), avatar uploads/Gravatar, OS `wfedit://` URL-handler registration.
