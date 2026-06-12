# Plan: wf-edit in the browser (WebRTC collab editor UI → WASM)

> Status: approved 2026-06-12, implementation in progress. Phase 0 first (gating).

## Context

`wf-edit` is WorldFoundry's collaborative level editor — a Dear ImGui app that embeds
the live engine viewport, drives an OAD-based property panel + outliner + ImGuizmo
gizmo, and edits a `wfcrdt::Doc` (Yrs/y-crdt) synced to co-editors over a stateless
Rust WebSocket relay. Today it's **Linux/X11 only**.

Two facts make a browser port high-reuse rather than a rewrite:

1. **The engine half already runs in the browser** — `libwfengine.a` compiles to
   WASM/WebGL2 and is live at worldfoundry.org/v2/play (GLES3→WebGL2, zForth-only,
   `emscripten_set_main_loop` state-machine inversion, IDBFS persistence, MEMFS asset
   IO). Web build: `task build-web` → `emcmake cmake -B build-web`.
2. **The collab transport is already browser-friendly** — the relay is reachable at
   `wss://wf.worldfoundry.org`; the wire protocol is a binary channel tag + payload
   (`CH_SYNC=0x01` Yrs update bytes, `CH_PRESENCE=0x02`, `CH_CHAT=0x03`,
   `CH_CONTROL=0x04`, `CH_SIGNAL=0x05`). Only **voice/video media** uses native libs
   (libdatachannel/Opus/libvpx/V4L2) that don't port to WASM.

So the editor's UI, gizmo, property panel, OAD reader, CRDT bridge, and engine
viewport are all reusable; the work is build plumbing + replacing three platform seams
(windowing/GL, WebSocket transport, main-loop ownership) and compiling out the
native-only media stack.

## Decided scope (settled with the user)

- **Approach: port the existing C++ ImGui editor to WASM** (not a JS/TS rewrite). One
  codebase for desktop + web; binary-compatible with native clients in the same rooms.
- **v1 collab = co-edit + presence + text chat. Voice/video DEFERRED** — the native
  libdatachannel/Opus/libvpx/V4L2 stack is **compiled out** of the web build, not ported.

## Architecture: the three seams to convert

| Native (X11) | Browser (WASM) |
|---|---|
| GLFW owns X11/GLX window; `SetHostGLContext` hands X11 handles to engine | `-sUSE_GLFW=3` (Emscripten GLFW port); editor creates the single WebGL2 canvas context, engine **adopts** it via a new web host-context flag |
| `ws_client` = POSIX sockets + OpenSSL + hand-rolled RFC6455 framing; sync blocking `connect()` | new `ws_client_emscripten.cc` over `emscripten/websocket.h` (`-lwebsocket.js`); browser does TLS + framing; async connect → `connected()` state machine + incoming-frame queue |
| `RunEditor` blocking `for(;;){ build; StepFrame; present; }` in `game.cc` | new `RunEditorWeb`/`WebTickEditor` via `emscripten_set_main_loop`, mirroring the engine's existing `RunLevelWeb`/`WebTick` (game.cc:723-768) |
| `std::thread` connect/reconnect; nested blocking modals (picker/tunnel/connect); `execvp` re-exec; shell-out compile | single-threaded poll-in-loop; modals/re-exec/compile `#if !defined(__EMSCRIPTEN__)`-excluded; level switch = page reload w/ query param |

Decision — **GL context ownership**: editor (GLFW) creates the context; the engine's
`emscripten_window.cc::InitWindow` early-returns and adopts the current context when a
web host-context is registered. This keeps `imgui_impl_glfw` + `imgui_impl_opengl3`
working unchanged (maximum reuse) and is the direct analogue of the native host-owned mode.

Decision — **new CMake target `wf_edit_web`**, not a branch of `wf_edit`. The existing
`wf_edit` block unconditionally `find_package`s OpenSSL and FetchContent-builds
libdatachannel + glfw-from-source at *configure* time (CMakeLists.txt:1194-1221);
threading `if(EMSCRIPTEN)` through that risks the native build. A sibling target sharing
a common source list is cleaner.

## Phase 0 — De-risk spike: yffi → wasm32-unknown-emscripten (HIGHEST RISK — do first, in isolation)

`wfcrdt`→`libyrs.a` is built by **Corrosion** (`engine/crdt/CMakeLists.txt`,
`corrosion_import_crate ... yffi/Cargo.toml`). The vendored Corrosion
`cmake/Corrosion/cmake/FindRust.cmake` has branches only for WIN32/Android/OHOS and
**falls back to the host triple otherwise** — under `emcmake` it would silently build
yffi for `x86_64-unknown-linux-gnu`, not wasm. Phase 1 also links `wfcrdt`, so this
gates everything.

Steps:
1. `rustup target add wasm32-unknown-emscripten` (add to a `dev-setup-web-edit` task).
2. In top-level `CMakeLists.txt`, before `add_subdirectory(engine/crdt)` (~line 1177):
   `if(EMSCRIPTEN AND NOT DEFINED Rust_CARGO_TARGET) set(Rust_CARGO_TARGET "wasm32-unknown-emscripten" CACHE STRING "" FORCE) endif()`
   (FindRust reads this before its fallback and auto-installs the target; leaves the
   vendored Corrosion pristine.)
3. Spike: `emcmake cmake` over just `engine/crdt` building `yrs`+`wfcrdt`, link a
   ~20-line C harness calling `ydoc_new()`/`ydoc_destroy()`; confirm a `.wasm` is
   produced and yffi symbols resolve (`emnm`/`wasm-objdump`, or run under node).

**Fallback if Corrosion won't drive it cleanly**: replace `corrosion_import_crate` with
an `add_custom_command` running `cargo build --release --target wasm32-unknown-emscripten
--manifest-path .../yffi/Cargo.toml` + an `IMPORTED STATIC` lib pointing at
`target/wasm32-unknown-emscripten/release/libyrs.a` — exactly the pattern `wf_relay`
already uses (CMakeLists.txt:1347-1351). (`ywasm` is NOT a fallback — it's JS bindings,
wrong ABI for linking into our C++ wasm.)

**Verify before proceeding**: minimal C harness linking `libyrs.a` + `libwfcrdt.a`
produces a runnable wasm module that round-trips a CRDT update.

### Phase 0 — verification (2026-06-12) — ✅ PASS

Step (End-to-end verification #1): *C harness linking `libyrs.a`+`libwfcrdt.a` runs as wasm
and round-trips a CRDT update.*

Two environment discoveries, both now folded into `task dev-setup-web-edit`:

1. **Rust is the distro package** (`/usr/bin/rustc` 1.85.1, sysroot `/usr/lib/rust-1.85`),
   *not* rustup-managed, with only the host std — and Corrosion's `FindRust` has no Emscripten
   branch, so it silently falls back to the host triple. Fix: install **rustup isolated**
   (`--no-modify-path`, distro rust untouched), pin toolchain **1.85.1** (matches the
   known-good native build vs the vendored yrs 0.26), `rustup target add wasm32-unknown-emscripten`.
2. **yffi wouldn't cross-compile**: `yrs::undo::Options::default()` is gated
   `#[cfg(not(target_family = "wasm"))]`, over-broadly excluding emscripten even though its only
   dependency, `SystemClock`, is gated the narrower `not(all(wasm, os=unknown))` and IS present
   on emscripten. The host build succeeds, so it's purely target-cfg, not a wasm-feasibility
   issue. Fix: `docs/patches/yrs-0.26-undo-options-default-emscripten.patch` aligns the two gates.
   `wftools/y-crdt` is an **upstream submodule** (can't push), so the fix ships as a tracked
   patch applied idempotently by `dev-setup-web-edit`.

Raw output (stronger than the planned C smoke — the full C++ RAII wrapper test, which is the
exact wrapper the editor links):

```
$ cargo rustc --release --target wasm32-unknown-emscripten ... yffi --lib --crate-type staticlib
    Finished `release` profile [optimized] target(s) in 1.87s
staticlib: .../wasm32-unknown-emscripten/release/libyrs.a (14384034 bytes)
$ em++ -O2 ... wfcrdt.cpp wfcrdt_stub.c wfcrdt_wrapper_test.cc libyrs.a -o wrap.js
/tmp/wfcrdt_spike/wrap.wasm: WebAssembly (wasm) binary module version 0x1 (MVP)
$ node wrap.js
wfcrdt_wrapper_test: OK (14/14 tests passed — incl. nested map/array + native undo
  + collab local-only + deep observer)
  node exit code: 0
```

**PASS** — the full CRDT chain (yrs → yffi → `libyrs.a` → `wfcrdt` C++ wrapper → wasm)
cross-compiles for `wasm32-unknown-emscripten` and runs under node, 14/14. The `native undo`
test passing confirms the `Options::default()` patch works at runtime. Highest-risk item retired.
Remaining Phase-0 plumbing (CMake `Rust_CARGO_TARGET` + Corrosion driving this under `emcmake`)
folds into Phase 1's `wf_edit_web` target.

## Phase 1 — Non-collab WASM editor (preloaded level, ImGui panels + gizmo, no network)

Earliest end-to-end value; exercises every non-network seam.

- **CMake `wf_edit_web` target** (CMakeLists.txt): add option `WF_ENABLE_WEB_EDITOR`
  (default OFF); when ON under EMSCRIPTEN also force `WF_ENABLE_EDITOR ON` so
  `engine/crdt` (wfcrdt/yrs) builds. Sources = the editor's portable set
  (`main.cc, level_doc.cc, property_panel.cc, oad_reader.cc, engine_bridge.cc,
  gizmo.cc, level_save.cc, collab_panel.cc`, `wftools/oaddump/oad.cc`, ImGui core +
  `imgui_stdlib` + `imgui_impl_glfw` + `imgui_impl_opengl3` + `ImGuizmo.cpp`) plus a new
  `collab_stub_web.cc`. **Omit** `collab_session.cc / voice_track.cc / video_track.cc /
  webrtc_session.cc / ws_client.cc`. Link only `wfengine wfcrdt`. Link options clone the
  `wf_game` EMSCRIPTEN block (CMakeLists.txt:912-948) plus `-sUSE_GLFW=3
  -sMIN/MAX_WEBGL_VERSION=2 -sALLOW_MEMORY_GROWTH=1 -lwebsocket.js -lidbfs.js`,
  `--shell-file web/shell-edit.html`, `--preload-file <leveltree>@/level`,
  `SUFFIX ".html"`, `OUTPUT_NAME wf-edit`. Reuse `add_dependencies(... gen_oas_headers)`
  + the `engine_bridge.cc` `OBJECT_DEPENDS` (CMakeLists.txt:1250-1254).
- **`collab_stub_web.cc`** (new): no-op definitions of `CollabSession`/`VoiceChat`/
  `VideoChat`/`WebrtcSession` so `main.cc` compiles unmodified for those member calls
  (less invasive than `#ifdef`-ing every call site). `CollabSession::SetRelayPeers`/
  `Peers` round-trip the relay roster (used by the collab panel in Phase 3).
- **GL context adopt path** (`wfsource/source/gfx/gl/emscripten_window.cc`): gate
  `InitWindow`'s `emscripten_webgl_create_context` behind a "host owns context" flag;
  add a tiny web host-context registration in `main.cc` replacing the X11 block
  (main.cc:3011-3026). Keep init order: `glfwCreateWindow` → `ImGui_Impl*_Init` →
  register web host-ctx → engine init.
- **Main-loop inversion** (`wfsource/source/game/game.cc` + `game.hp`): add
  `RunEditorWeb()` + `WebTickEditor()` next to `RunLevelWeb`/`WebTick` (723-768). Tick
  body inverts `RunEditor`'s loop preserving build→StepFrame(false)→present ordering
  (the zero-latency-local-edits invariant). `game/main.cc` `--editor` dispatch → call
  `RunEditorWeb()` on web. In `engine/wf_edit/main.cc`, `#if !defined(__EMSCRIPTEN__)`
  the post-`HALStart` teardown, the `std::thread` connect/reconnect (main.cc:389, 621,
  3244), and the nested blocking modal loops (cd.iff picker 818, quick-tunnel 3042,
  connect pump 3278). Keep the `glReadPixels`/`write_ppm` screenshot path for headless CI.
- **Level load**: `--preload-file` into MEMFS; `main.cc`'s `LoadLevelTreeIntoDoc`
  (POSIX IO over MEMFS) + engine `-L` resolve the same preloaded path. Drive paths via
  `Module.arguments` from a new `web/shell-edit.html` (clone `web/shell.html`,
  click-to-start, `#canvas`).
- **Taskfile**: `build-web-edit` (mirror `build-web` + `-DWF_ENABLE_WEB_EDITOR=ON
  -DRust_CARGO_TARGET=wasm32-unknown-emscripten`), `serve-web-edit`, `dev-setup-web-edit`.

**Verify**: `task build-web-edit` → `task serve-web-edit`; browser renders the preloaded
level; Outliner lists actors; selecting populates Properties (OAD reader); gizmo moves an
actor visibly same-frame (build-before-step + engine_bridge wfmut). Headless: run `.js`
under node with `--frames N --screenshot out.ppm` for CI.

### Phase 1 — progress & findings (2026-06-12/13) — 🟡 renders in-browser; 1 UB heisenbug blocks a clean build

Landed (commits `89b25159` plumbing, `9d30b480` compile+link, `687d460b` GL adopt,
`da860e04` shell+preload, `f5de5a89` stack+shader): the `wf_edit_web` target compiles
+ links, and **boots in headless Chrome (SwiftShader WebGL2)** — `main()` runs, the
GLFW→WebGL2 context-adopt works (`engine surface 1280x800`), and the engine loads the
level (Jolt init, 37 objects, zForth constants, broadphase). Verified by screenshotting
`google-chrome --headless --use-gl=angle --use-angle=swiftshader … wf-edit.html`.

Runtime fixes found (each unblocked the next, classic emscripten bring-up):

1. **Stack overflow → `-sSTACK_SIZE=8388608`.** ImGui's recursive draw + the engine
   `StepFrame` run on one stack; emscripten's 64 KB default overflows on the first
   editor frame (`-sASSERTIONS=2` named it). `wf_game` (shallower per-frame depth)
   never needed it. 8 MB ≈ a desktop stack.

2. **ImGui shader `#version 130` → `#version 300 es` (the issue you flagged).**
   Implications:
   - `ImGui_ImplOpenGL3_Init(glsl_version)`'s string sets the GLSL dialect for **ImGui's
     own UI-drawing shaders** — not the engine's. `#version 130` is desktop GL 3.0 GLSL;
     **WebGL2 = OpenGL ES 3.0 requires `#version 300 es`** (with mandatory `precision`
     qualifiers, which ImGui's backend emits only when handed an `…es` version). A 130
     shader is rejected by the WebGL2 compiler → `CreateDeviceObjects` fails → ImGui
     can't draw a single vertex (blank panels), and on some drivers the failed program
     cascades into a draw-time fault.
   - **The engine viewport was never affected**: `gfx/glpipeline/backend_modern.cc`
     already emits `#version 300 es` on web. This bug was isolated to the ImGui overlay;
     the `#if __EMSCRIPTEN__` conditional keeps native on 130 and web on 300 es from one
     source, zero runtime cost.
   - **Broader class it represents**: the editor was authored desktop-GL-first, so every
     editor-side GL/GLSL assumption must be remapped to GLES3/WebGL2. This was the ImGui
     backend; ImGuizmo is safe (it emits into ImGui's draw list, no shaders of its own);
     audit `gizmo.cc` and any direct GL in editor TUs for the same axis. It's a
     necessary-but-not-sufficient fix — it cleared the shader failure but rendering is
     still blocked by (4).

3. **Doc/Outliner population gap (popen/levtree).** `LoadLevelTreeIntoDoc` shells out to
   the `levtree` binary via `popen` to parse a `.lev` — `popen` doesn't exist on wasm, so
   the Doc is empty (`Y.Doc population failed … Outliner will be empty`). The 3D viewport
   still loads via the engine `-L` (a binary `.iff`), so the scene renders; only the
   Outliner/Properties are empty until a web Doc-population path exists. Options: compile
   the levtree parser into the wasm (call it in-process instead of via popen), or have
   the relay deliver the initial CRDT state (Phase 2 already does this for co-edit). Track
   as a Phase-1 follow-up; not blocking the viewport.

4. **The "null function" was three stacked bugs — two FIXED (commit `f7483dbb`), one OPEN.**
   The original opaque `RuntimeError: null function` resolved into a chain, each masking
   the next:
   - **(a) FIXED** — A WF assert (`assert(HALScratchLmalloc.Empty())`, game.cc:739 + :562)
     fires every frame on the editor path (scratch genuinely non-empty), and
     `_sys_assert`'s `exit(-1)` under `-sEXIT_RUNTIME=0` unwinds to an opaque wasm trap that
     blanks the canvas with no readable cause. Fix: `pigsys/assert.cc` — on web a firing
     assert WARNS (throttled) + CONTINUES instead of exiting.
   - **(b) FIXED** — `_sys_assert` was `__attribute__((noreturn))`, so the non-fatal return
     made the compiler emit a wasm `unreachable` after every assert call site. Fix:
     `pigsys/assert.hp` drops `noreturn` on web.
   - **(c) FIXED** — `DBSTREAM1(cframeinfo<<…)` in `StepFrame` traps (the gamestrm.cc game
     debug streams hit a cross-TU static-init-order issue on web → null streambuf vtable;
     `cprogress` from the lib-stream TU works, `cframeinfo` doesn't). Fix: guarded on web
     (it's a null sink + violates DBSTREAM1's own "not in the game loop" contract).
   - **(d) FIXED (commit `59dc44d3`) — `stack-use-after-scope` on the HAL scratch allocator.**
     It looked like a CRDT-bridge heisenbug (traps right after `[bridge] InitBridgeMap: 0
     actors`, masked by any `fprintf`), but ASan + `emsymbolizer` pinned it to **`game.cc:553`**
     — the `assert(HALScratchLmalloc.Empty())` in `StepFrame` (which runs just after
     `editor_build`, hence the misleading "after InitBridgeMap"). Root cause is in **`hal.cc`,
     not the bridge:** `HALStart` holds the global `_HALScratchLmalloc` pointing at a **stack
     local** `__scratchLMalloc` and calls `PIGSMain` inside that scope. Native runs the game
     loop nested in that frame (local stays alive); web's `emscripten_set_main_loop(…,
     simulate_infinite_loop=1)` **unwinds the C stack**, destroying the local while the global
     still points at it → every `StepFrame` reads a dead `LMalloc` → garbage vtable → "null
     function" (layout-sensitive, so `fprintf` masked it). Latent since the 2010 first commit;
     see [`docs/BUGS.md`](../BUGS.md). Fix: `static` `__scratchLMalloc` on web so it outlives
     the unwind. The earlier (a)–(c) fixes (non-fatal asserts, cframeinfo guard) were treating
     symptoms of the same dead allocator + an independent gamestrm static-init issue; kept as
     they're correct on their own.

   **Render proof — CLEAN build (no fprintf, no ASan), all (a)–(d) + Doc-population fixed:**
   the editor draws its menu bar (File/Edit/Collaborate), a **populated Outliner (36 snowgoons
   actors** — `InitBridgeMap: 36 actors`), Properties, and the engine viewport rendering the
   snowgoons terrain, full frame loop completing, **zero traps**. So the whole WASM/WebGL2 +
   ImGui + engine-viewport architecture is sound — Phase 1 renders end-to-end in a clean build.

   <img src="screenshots/2026-06-13-wf-edit-web-renders.png" width="700">

   *wf-edit running in headless Chrome (SwiftShader WebGL2): Dear ImGui menu bar + Outliner
   (36 actors: statplat/actboxor/room/light/camshot/target/tool/…) + Properties, and the
   engine viewport. The terrain is flat grey because snowgoons' inherited camera fog
   (FoggingColor 0x888888, complete at 30 m) greys out anything past the pulled-back
   edit camera — the known snowgoons fog trap, not missing textures.*

## Phase 2 — Emscripten WebSocket backend + CRDT sync (co-edit with a native client)

- **`ws_client_emscripten.cc`** (new): implement the *same* `wfedit::WsClient` interface
  (`connect/lastError/disconnect/connected/send/poll`) over `emscripten/websocket.h`.
  Keep the public signatures in `ws_client.h` identical; add `#if defined(__EMSCRIPTEN__)`
  private members (a `EMSCRIPTEN_WEBSOCKET_T`, a state enum, an incoming-frame
  `std::deque<std::vector<uint8_t>>`).
  - `connect()` → `emscripten_websocket_new` + register onopen/onmessage/onclose/onerror
    (`this` as userData); returns "connect initiated" (state `Connecting`), not blocking.
  - `connected()` → `state == Open` (set by onopen). The web connect flow moves into the
    main-loop tick: call `connect()`, each tick check `connected()`, then send the
    `CH_CONTROL` join frame (`SendRoomJoin`) and wire `observeUpdates`→relay send
    (main.cc:3329-3335) — a small web state machine replacing the threaded native one.
  - `onmessage` delivers complete binary messages (browser handles RFC6455) → push to
    queue; `poll()` pops one. **Application framing (byte-0 channel tag + payload) is
    byte-identical on the wire**, so web and native interoperate in the same room.
  - `send()` → `emscripten_websocket_send_binary`; `disconnect()` → close+delete;
    `lastError()` → map onerror/onclose into the existing `ConnectError` enum.
- The `CollabDrain` `CH_SYNC` apply (`doc.beginRemote()`, main.cc:646-655) and the
  `observeUpdates`→send wiring are **reused unchanged**; only connect/reconnect scaffolding
  differs. Initial state: relay pushes a full `CH_SYNC` snapshot on join (relay Phase-7
  persistence); CRDT merge converges it with the preloaded Doc — no blocking wait.
- **Exceptions note**: keep `wf_edit_web`'s own TUs (incl. `main.cc`, which uses
  nlohmann/json `try/catch` for presence/chat) **with exceptions enabled**, while the
  engine library stays `-fno-exceptions` (as today).

**Verify**: run native `wf-edit --relay=wss://wf.worldfoundry.org --room=webtest` AND a
browser `wf-edit.html` on the same room; moving an actor in one moves it in the other
(bidirectional `CH_SYNC` + wasm CRDT apply + identical framing). A fresh tab joining
mid-session shows current edits from the relay snapshot.

### Phase 2 — status (2026-06-13) — ✅ COMPLETE: transport verified + Doc-population done + multi-peer join-and-receive verified

- **DONE (commits `f713533a`, `58652d7e`)** — real browser-WebSocket backend
  (`ws_client_emscripten.cc` over `emscripten/websocket.h`, same `WsClient` interface +
  wire framing as native) and the web connect state machine: `main()` initiates a
  non-blocking connect pre-`HALStart`; `WebConnectStep` (in `editor_build`) sends the
  room-join + wires `observeUpdates`→relay once `connected()` flips; `CollabDrain`
  applies inbound. Threaded connect + mid-session reconnect are native-only. Compiles +
  links into `wf_edit_web`.
- **GATE CLEARED** — finding (d) fixed (`59dc44d3`), so a clean build runs `editor_build`
  (`WebConnectStep` / `CollabDrain`) every frame.
- **TRANSPORT VERIFIED (2026-06-13)** — local `wf-relay` + headless-Chrome
  `wf-edit.html?room=webtest&relay=ws://localhost:9911`: browser console
  `relay connected, joined room=webtest`; relay log `[relay] anon joined room webtest`;
  zero traps. So `ws_client_emscripten` + `WebConnectStep` work end-to-end against a real relay.
- **DOC-POPULATION FIXED (`be7baa6e`)** — the browser now loads the level locally (36
  snowgoons actors via preloaded levtree JSON), so it has a base Doc for editing.
- **MULTI-PEER JOIN-AND-RECEIVE DONE + VERIFIED (`main.cc`, this commit)** — the
  seeding/CRDT-origin problem is solved. On web, when joining a relay room the local Doc
  load is **deferred** (`web_defer_doc_load = !room_id.empty()` in `main()`); after the
  join frame, `WebConnectStep` arms a ~0.6 s window and `WebSeedStep` (run each
  `editor_build` frame) resolves the role:
  - **Host path** — if the Doc is still empty at the deadline, this peer is first in:
    `LoadLevelTreeIntoDoc` runs *after* `observeUpdates` is wired, so every commit
    auto-pushes `CH_SYNC` to the relay, seeding it for later joiners.
  - **Joiner path** — if the relay populated the Doc within the window (`content` array
    non-empty), this peer adopts it as-is and **never loads locally** — so there are no
    independent Yrs client IDs and no duplication.

  This avoids the duplicate-vs-converge trap: exactly one peer ever loads the `.lev`; all
  others inherit its Doc via the relay. Native is untouched — `web_defer_doc_load` is
  `false` off-wasm (collapses to the original `if (!show_picker)`), and `WebSeedStep` /
  the new `EditorCtx::web_seed_*` fields are inside `#if defined(__EMSCRIPTEN__)` /
  inert on native.
- **VERIFIED (2026-06-13)** — local `wf-relay --port 9931` + two sequential headless-Chrome
  tabs on `wf-edit.html?room=coedit&relay=ws://localhost:9931` (separate
  `--user-data-dir`). Tab A console: `room was empty — seeded it from
  /level/snowgoons-blender.lev`. Tab B console: `adopted room Doc from relay (36 actors)`
  — **36, not 0, not 72** (no duplication). Relay log shows both joins to room `coedit`.
  Tab B screenshot (Outliner = 36 actors, full tree, viewport rendering):
  <img src="screenshots/2026-06-12-coedit-joiner-adopts-36.png" width="700">
  The relay's durable snapshot held the seed across A's disconnect, so B (joining after A
  left) still adopted it — proving both the seed→relay push and the relay→joiner adopt
  legs of the round-trip.

## Phase 3 — Presence + text chat

Mostly falls out of Phase 2: the `CH_PRESENCE` (main.cc:656-690) and `CH_CHAT`
(main.cc:691-713) handlers live in `main.cc` (not `collab_session.cc`) and are already in
the web build.

- Ensure the periodic presence broadcast + chat send happen in the web tick (route
  through `relay_client.send`, now the web WS backend; `glfwGetTime()` works under
  `-sUSE_GLFW=3`).
- `collab_stub_web.cc::SetRelayPeers/Peers` round-trip the relay roster so
  `collab_panel.cc` shows web peers (multicast path is absent on web — relay-only, the
  desired behavior).
- `web/shell-edit.html`: plumb `?room=` / `?relay=` / `?name=` query params into
  `Module.arguments`.

**Verify**: native + browser in one room; browser shows the native peer's name/colour and
a selection ring on the actor it selected; chat round-trips both ways; closing a tab
evicts the peer after the timeout.

## Save semantics on web (no local FS / no shell)

- Disable **Save + Compile** (shells out to `build_level_binary.sh`) on web.
- Primary "it's saved" = the relay's durable snapshot (co-editors already converge).
- Explicit **Export**: `SaveDocToLev` → MEMFS → offer as a JS `Blob` download.
- Optional cross-session local persistence via IDBFS (`-lidbfs.js`, `syncfs`).

## Files to create / modify

**Create**: `engine/wf_edit/ws_client_emscripten.cc`, `engine/wf_edit/collab_stub_web.cc`,
`web/shell-edit.html`.

**Modify**: `CMakeLists.txt` (`WF_ENABLE_WEB_EDITOR` + `Rust_CARGO_TARGET` set +
`wf_edit_web` target), `engine/crdt/CMakeLists.txt` (Phase-0 cross-compile, with cargo
custom-command fallback), `engine/wf_edit/ws_client.h` (web private members behind the same
interface), `engine/wf_edit/main.cc` (web host-ctx register, `#if __EMSCRIPTEN__`
exclusions for threads/modals/teardown/re-exec, web connect state machine),
`wfsource/source/game/game.cc` + `game.hp` (`RunEditorWeb`/`WebTickEditor`),
`wfsource/source/game/main.cc` (`--editor` web dispatch),
`wfsource/source/gfx/gl/emscripten_window.cc` (host-context adopt path), `Taskfile.yml`
(`build-web-edit`, `serve-web-edit`, `dev-setup-web-edit`).

## Top risks

1. **(HIGHEST) Corrosion mis-targets yffi to the host triple** — confirmed in
   `FindRust.cmake`. Mitigate by forcing `Rust_CARGO_TARGET`; fallback is the cargo
   custom-command + IMPORTED lib. **Spike in Phase 0 before committing further.**
2. **Single canvas, two would-be context creators** (GLFW-emscripten vs engine
   `InitWindow`) — editor creates, engine adopts via host-ctx flag.
3. **Threads / blocking modals / `execvp` / shell-out compile** — all excluded on web;
   connect/reconnect becomes a poll-in-loop state machine.
4. **Async WS vs the synchronous `connect()` contract** — redefine web `connect()` as
   "begin connecting" + `connected()` state machine + queue-drained `poll()`.
5. **Teardown/save-on-exit never runs** (main loop never returns) — move persistence to
   explicit actions / `beforeunload` + IDBFS sync.

## End-to-end verification

1. Phase 0: C harness linking `libyrs.a`+`libwfcrdt.a` runs as wasm and round-trips a CRDT update.
2. Phase 1: `task build-web-edit && task serve-web-edit` → browser renders preloaded level; Outliner/Properties/gizmo work; headless `--frames N --screenshot` produces a non-blank PPM.
3. Phase 2: browser tab + native `wf-edit` on `room=webtest` co-edit bidirectionally; mid-session join shows current state.
4. Phase 3: presence (names/colours/selection rings) + chat round-trip between browser and native; tab close evicts the peer.
