# Plan: macOS Metal renderer — finish the shared Metal path, with macOS as the bench

**Date:** 2026‑09‑20
**Status:** Plan only — nothing implemented. Written for review; several decisions below are the user's call.
**TODO entry:** `TODO.md:9` — *"macOS Metal renderer"* (Open → Platform / Display).
**Companion investigation:** [2026-05-26-macos-port-estimate.md](../investigations/2026-05-26-macos-port-estimate.md) — **its central premise is now false**; see §2.
**Prior plan:** [2026-05-26-macos-port-runtime-bringup.md](2026-05-26-macos-port-runtime-bringup.md) — the headless half, landed; this is its deferred "gfx half".

**Visible surface:** yes, eventually — but there is no new design to mock. The target image is defined entirely by the existing Linux GL build: the same level, same frame, same pixels. The acceptance artifact is a **side‑by‑side capture against the Linux GL renderer**, not an invented mockup, so the mockup bundle section is dropped per `~/CLAUDE.md`.

---

## 1. Context

`TODO.md:9` reads:

> **macOS Metal renderer.** iOS Metal backend exists; macOS desktop is still on GL stubs. Needs a real Metal renderer + window (shared with iOS), then re-enable Jolt + full scripting roster on macOS once headless is green.

Three of those four clauses are stale. Checked against the tree at `3fccf5fa`:

| TODO clause | Reality |
|---|---|
| "iOS Metal backend exists" | A Metal `RendererBackend` **class** exists and is complete. It has **never rendered a triangle** — see §2. |
| "macOS desktop is still on GL stubs" | Imprecise, and the imprecision matters. **There is no GL on macOS at all** — no `OpenGL.framework` is linked (`CMakeLists.txt:922-933`), and `gfx/gl` + `gfx/glpipeline` are both excluded from the build (`CMakeLists.txt:221-236`). The *renderer* is `engine/stubs/renderer_stub.cc` — a `HeadlessBackend` whose every virtual is empty, selected by `backend_factory.cc:17,27`. `hal/macos/gl_stubs.cc` is a separate and much narrower thing: seven no-op GL entry points that exist only because `gfx/pixelmap.cc` still calls GL directly (§D4), linked purely to satisfy the linker. |
| "re-enable Jolt" | **Already on** — not a phase to plan. `CMakeLists.txt:30` defaults `WF_PHYSICS_ENGINE=jolt`; the macOS gate (`CMakeLists.txt:115-123`) does not override it; there is no macOS-specific override file (`macos/` contains only `Info.plist`); and the `-DWF_PHYSICS_ENGINE=legacy` that the first bring-up run used is **gone** from the configure step, which now passes only `-DCMAKE_BUILD_TYPE=Debug -DCMAKE_OSX_ARCHITECTURES=arm64 -DWF_ASAN=OFF` (`codemagic.yaml:384-394`). The Xcode-generator workaround that once forced legacy was replaced by source-file properties (`CMakeLists.txt:624-660`), and macOS builds with Ninja anyway. |
| "full scripting roster" | **Already on** since `04061deb` (2026‑05‑27), likewise not a phase. `CMakeLists.txt:115-123` forces off only `WF_WASM_ENGINE`, `WF_ENABLE_EDITOR`, `WF_ENABLE_STEAM`. Lua/Fennel/QuickJS/Wren/zForth and the debug bridge are live. The residue is **WAMR only**, and even that is pre-wired (`CMakeLists.txt:464-472` already sets `darwin`/`AARCH64` for `APPLE`). |

So the physics and scripting half of the TODO text is **already-satisfied groundwork**. The remaining gap is exactly two things: the renderer backend (a true no-op today) and a real window-and-input loop. That is narrower than the TODO says in the tail, and **much wider than it says in the head**.

**The macOS build has run on Codemagic, contrary to the sibling plan's status line.** [2026-05-26-macos-port-runtime-bringup.md](2026-05-26-macos-port-runtime-bringup.md):4 still says *"awaiting first Codemagic macOS build"*, but three macOS fix commits landed the next day — `ab1a0f3a` (add the missing `Display::MeasureDelta()`, a link error), `a7ee03ba` (`NSBundleAccessor` falls back to `fopen` for absolute paths, a runtime behaviour), and `d0dcece2` (delta `timeval` before `ConvertTimeToScalar`, a `Scalar` overflow). Those are build-and-run feedback, not desk-checking. That status line should be corrected in Phase 0.

## 2. The finding that changes the plan's shape

The 2026‑05‑26 investigation is built on one premise ([§Decision premises](../investigations/2026-05-26-macos-port-estimate.md)):

> **The iOS Metal renderer will be finished before the macOS port begins.** […] a *proven* Metal renderer available at macOS-start-time […] Adding macOS is *selecting the Metal backend for a 4th platform arm*, not writing a renderer.

That premise does not hold. Traced end to end:

1. **The Metal backend is never fed an encoder.** `hal/ios/backend_metal.mm:342` (`SetCurrentEncoder`) and `:347` (`ClearCurrentEncoder`) have **zero callers** anywhere in `wfsource/` or `engine/`. `hal/ios/native_app_entry.mm:76-77` says so in as many words:

   > `// Phase 2C-B — for now, Display::PageFlip sleeps ~16ms and the Metal`
   > `// backend drops any batched triangles because no encoder is set.`

2. **No triangles are submitted in the first place.** Both the iOS and macOS arms compile `engine/stubs/renderpoly3d_stubs.cc` (`CMakeLists.txt:347-351`, `:352-368`) — eight `RenderObject3D::RenderPoly3D*` methods that `return 0`. The real ones are in `gfx/glpipeline/`, which both arms exclude (`CMakeLists.txt:212-236`).

3. **The view host is still Phase 2A.** `hal/ios/metal_view.mm` acquires a drawable, opens a render command encoder, calls `endEncoding` immediately, and presents. It is a clear-to-cornflower-blue and nothing else.

4. **Textures are not implemented.** `backend_metal.mm:110` and `:466` (`u.use_tex = 0;  // Phase 2C adds texture binding.`) — `DrawTriangle` ignores its `PixelMap*`.

5. **There is no depth buffer.** `backend_metal.mm:432` sets `colorAttachments[0].pixelFormat` and nothing else — no `depthAttachmentPixelFormat`, no `MTLDepthStencilState`, no depth texture. On the GL side depth is never the backend's business: it comes from the GLX visual plus scattered `glEnable(GL_DEPTH_TEST)` in `gfx/gl/display.cc:543,853` and `gfx/pixelmap.cc:217`. Nothing in the Metal path replaces that.

**Net: "iOS Metal" is a well-built engine-side backend object with no window feeding it, no geometry reaching it, no textures, and no Z-buffer.** There is nothing to "select for a 4th platform arm".

### 2.1 The counterweight: most of the port is already done, and the remaining work is portable

Against that, a second finding cuts the other way and is the reason this is still a good next move:

**The eight geometry-submission files are already backend-agnostic.** `gfx/glpipeline/rend{f,g}{c,t}{l,p}.cc` include *only* `gfx/renderer_backend.hp` and WF math headers and end in a `RendererBackendGet().DrawTriangle(...)` call — see `gfx/glpipeline/rendfcl.cc:13-22` and `:57-63`. Not one GL symbol among them. Same for `gfx/glpipeline/rendobj3.cc`. The only genuinely GL-bound file in that directory is `backend_modern.cc`, which includes `<GL/gl.h>` at `:16-28`.

The CMake comment that keeps them out — *"gfx/glpipeline (GL-only backend) stay out"* (`CMakeLists.txt:208-210`) — was true when the directory *was* the GL backend and is no longer true since the `RendererBackend` seam landed. So "write eight Metal `RenderPoly3D` implementations" is not work that exists. **It is a CMake change: compile the eight files, drop `renderpoly3d_stubs.cc`.**

That inverts the cost model. The remaining Metal work is: an encoder handoff, a depth attachment, a texture path, and a window. Of those, exactly one (the window) is platform-specific. **Three of the four are shared with iOS, and the fourth is easier on macOS.**

## 3. Design decisions

### D1 — macOS is the development bench for the shared Metal renderer; iOS inherits it

The investigation sequenced iOS → macOS. Reverse it. macOS is the better bench for the same renderer:

- Ninja + CMake, no Xcode generator (`codemagic.yaml:384-394`), so Jolt and everything else build normally.
- A deterministic headless driver already exists: `wf_game --frame-step-smoke=N --cycles=M -L<level>` (`game/game.cc:414`) runs `Load → N × Step → Unload` and exits. iOS has no equivalent — it is `UIApplicationMain` plus a background engine thread (`hal/ios/native_app_entry.mm:82`).
- A CI workflow that already exercises it: `macos-desktop-debug` (`codemagic.yaml:354-420`).
- No simulator, no code signing, no device provisioning in the loop.
- The engine runs on the **main thread** on macOS (`hal/macos/platform_main.cc:29-43`), so the Metal frame can be built synchronously inside `Display` — no cross-thread encoder handoff. That is the single hardest unbuilt piece of iOS Phase 2C‑B, and macOS gets to skip it.

**Rejected:** finish iOS Phase 2C‑B first, then port. It pays for the thread-handoff design *before* anything has proven the renderer draws correctly, and it debugs first-light on the platform with the worst iteration loop.

**Consequence for iOS:** once macOS is drawing, iOS Phase 2C‑B reduces to "run the same synchronous frame on the engine thread, with `CADisplayLink` used only as a vsync pacer" — the encoder-handoff design in `backend_metal.mm:339-350` can likely be deleted rather than completed. That is an iOS-side follow-up, out of scope here, but the plan should not make it harder.

### D2 — The frame is synchronous and owned by `Display`, mirroring the Linux GL path

Linux structure, for reference: `Display::RenderBegin` (`gfx/gl/display.cc:796`) clears (`:818`), the engine draws, `Display::PageFlip` (`:1027`) pumps X events and calls `glXSwapBuffers` (`:1167`).

macOS Metal takes the identical shape, in what is today the headless `hal/macos/display_macos.cc`:

| Linux GL | macOS Metal |
|---|---|
| `RenderBegin` → `glClear` | acquire `nextDrawable`, build `MTLRenderPassDescriptor` (color + **depth**), open encoder, hand it to the backend |
| engine draws → `DrawTriangle` | unchanged — same eight `rend*.cc` files |
| `RenderEnd` → backend `EndFrame` | unchanged — `EndFrame` flushes the batch through the live encoder |
| `PageFlip` → `XEventLoop`, `glXSwapBuffers` | `endEncoding`, `presentDrawable`, `commit`, pump AppKit events |

`hal/macos/display_macos.cc:14-16` already anticipates exactly this ("When the real Metal renderer + window land, this becomes the macOS analogue of metal_view.mm").

**Rejected:** the iOS architecture (`CADisplayLink` on the main thread driving a separate engine thread, with a synchronised encoder handoff). It buys nothing on a desktop where the engine already owns `main()`, and it is the piece that has been stuck unbuilt on iOS since April.

### D3 — The Metal backend moves to `gfx/metal/`, shared by both Apple targets

`hal/ios/backend_metal.mm` imports only `<Metal/Metal.h>`, `<simd/simd.h>`, and engine headers (`:24-34`). There is no UIKit in it. It is misfiled: it is not iOS HAL code, it is the Metal sibling of `gfx/glpipeline/backend_modern.cc`.

Move it to `wfsource/source/gfx/metal/backend_metal.mm` and compile it from both the `IOS` and `APPLE` arms. Pure relocation — no behaviour change, no risk, and it stops every subsequent shared fix from looking like an iOS change.

**Rejected:** leave it in `hal/ios/` and reference it by path from the macOS arm. Works, but bakes in a lie about ownership, and the next person deleting "iOS-only" code breaks macOS.

### D4 — Textures get a backend-mediated handle; this is the one genuine design item

`PixelMap` is welded to GL: `pixelmap.hp:92` stores a `GLuint _glTextureName`, `pixelmap.cc:61,106,196-232` call `glGenTextures`/`glDeleteTextures`/`glTexImage2D`/`glTexParameteri` directly, and `pixelmap.hpi:133-142` (`SetGLTexture`) calls `glBindTexture`. On macOS all seven of those resolve to no-ops in `hal/macos/gl_stubs.cc`, so textures currently upload into nothing.

This cannot be papered over — it is the difference between flat-shaded geometry and the actual game. Two shapes, and **this is a decision worth surfacing rather than silently picking** (see O3):

- **(a) Widen the `RendererBackend` seam.** Add `CreateTexture(w, h, fmt, pixels) → opaque handle`, `DestroyTexture(handle)`. `PixelMap` stores the opaque handle instead of a `GLuint`; the GL backend returns a texture name, the Metal backend an `MTLTexture`. `DrawTriangle` already takes a `const PixelMap*` (`gfx/renderer_backend.hp:73-80`), so the draw side needs no signature change. Cost: touches `pixelmap.{hp,hpi,cc}` on *every* platform, including Linux/Android/Web — a real regression surface on code that currently works.
- **(b) Metal-side sidecar.** Leave `PixelMap` alone; the Metal backend keeps a `PixelMap* → MTLTexture` map, uploading lazily on first `DrawTriangle` with an unseen pointer. Zero change to shared code, zero Linux risk. Cost: the sidecar must be invalidated when a `PixelMap` is destroyed or re-uploaded, which `pixelmap.cc:106` does not currently announce — so it needs a notification hook anyway, and pointer reuse after free is a live hazard.

Neither is clean. (a) is the right long-term shape and the wrong thing to do while the renderer is unproven; (b) is a hazard shaped exactly like a use-after-free. My lean is **(b) behind an explicit destroy-notification callback for Phase 3, converting to (a) in a follow-up once Metal is drawing** — but this is close enough that it is written up as an open decision, not a settled one.

### D5 — Windowing: GLFW, with a stated escape hatch

GLFW is already in-tree at `third_party/glfw` and already linked by the editor (`CMakeLists.txt:1244`, `:1303`) — but configured **X11-only** (`GLFW_BUILD_WAYLAND OFF`, and the surrounding block at `:1210-1244` is explicitly the editor's X11/GLX host). Using it for `wf_game` on macOS means enabling its Cocoa backend and linking it into the *game* target for the first time.

Recommended: `glfwWindowHint(GLFW_CLIENT_API, GLFW_NO_API)` + `glfwGetCocoaWindow()` → attach a `CAMetalLayer`. Benefits: one windowing/input path for `wf_game` and `wf_edit` on macOS, GLFW gamepad support for free, and the `-width`/`-height`/`-fullscreen` flags (`hal/linux/platform_init.cc:100-137`) map onto `glfwSetWindowSize`/`glfwSetWindowMonitor` — which unblocks `TODO.md:7`.

The escape hatch, if GLFW's Cocoa backend proves awkward against `CAMetalLayer`: a ~150-line `NSWindow` + `NSView` host in `hal/macos/`. Cheap to write, but it forks input handling from the editor.

**Rejected:** `MTKView`. It wants to own the frame loop via its own draw callback, which fights D2.

### D6 — Fix `TODO.md:15` (`__LINUX__` aliasing) *before* the window, not after

`TODO.md:15` already says *"Trigger: before macOS Metal work starts."* There is now a concrete instance, and it is probably a live build break:

`hal/linux/platform_init.cc:50-52` includes `<X11/Xlib.h>` guarded only by `#if !defined(__EMSCRIPTEN__)`, and `:117-128` calls `XOpenDisplay`/`DisplayWidth`/`DisplayHeight` under the same guard. That file **is compiled into the macOS build** (`CMakeLists.txt:363`). The include landed in `42b4c665` (2026‑06‑04); `codemagic.yaml` was last touched 2026‑05‑27 and the macOS workflow is manual-trigger only (`triggering: events: []`, `codemagic.yaml:372-374`). So it has almost certainly not been built since the break was introduced.

**Confidence: high, but not verified** — I cannot compile for Darwin from here. It is exactly what Phase 0 is for.

## 4. Phases

Each phase is a green CI run. Phase numbering is chosen so the cheap, high-information runs come first — see §5 for why that ordering is forced by the budget.

### Phase 0 — Re-establish a green macOS baseline (no Metal at all)

Nothing below is diagnosable on top of a red build.

- ~~Guard `hal/linux/platform_init.cc:50-52` and `:117-128` for Darwin. Introduce `WF_POSIX` per `TODO.md:15` rather than adding another ad-hoc `#if defined(WF_TARGET_MACOS)`~~ — **done 2026‑09‑20.** `pigsys/pigsys.hp` now defines `WF_POSIX` (Linux/Android/iOS/macOS/Web) and `WF_HAS_X11` (desktop Linux only), immediately after `#include _MKINC` since that is what defines `__LINUX__` in the first place. Both `platform_init.cc` sites moved from `!defined(__EMSCRIPTEN__)` to `#if WF_HAS_X11`. The broader ~80-site `__LINUX__` sweep stays open in `TODO.md` — each site needs classifying by hand, and none of it blocks this plan.
- ~~Refresh the stale docs and comments the headless bring-up left behind~~ — **done 2026‑09‑20:** `codemagic.yaml`'s Jolt cache comment now says Jolt *is* the macOS physics engine; both `CMakeLists.txt` arms now say `gfx/glpipeline` is excluded as a not-yet-done rather than a GL dependency, naming `backend_modern.cc` as the only GL-bound file; [`2026-05-26-macos-port-runtime-bringup.md`](2026-05-26-macos-port-runtime-bringup.md):4 records that the first Codemagic macOS build ran on 2026‑05‑27 with its three fix commits, and its Deferred section strikes the satisfied Jolt/scripting note.
- ~~**In parallel, off the Mac‑min budget:** land the usage monitor from [2026-05-12-codemagic-budget-monitor.md](2026-05-12-codemagic-budget-monitor.md) §2~~ — **code landed 2026‑09‑20:** [`.github/workflows/codemagic-budget.yml`](../../.github/workflows/codemagic-budget.yml) + [`scripts/codemagic-budget.sh`](../../scripts/codemagic-budget.sh), exercised end-to-end against a stub API for accounting, at-most-once alerting, and month rollover. **Still inert** until the one-time secrets exist: `secrets.CODEMAGIC_API_TOKEN`, `secrets.PAGERDUTY_ROUTING_KEY`, `vars.WF_CODEMAGIC_APP_ID` (budget plan Implementation steps 4 + 5).
- ~~**Run `macos-desktop-debug` to green. Estimated cost: 1–2 runs, ~10–20 Mac‑min.**~~ — **done 2026‑09‑20.** The token gap is closed (`task setup`, `docs/SETUP.md`) and the run is green on build `6aafcf69903254faf05d7835` (`18188fd1`). Actual cost **15 Mac‑min across 8 runs** — the estimate was right per-run, wrong on run count, because the workflow had never executed: it surfaced six genuine defects one at a time. Five were build/config (missing Jolt extraction step; Jolt's PCH vs `-fno-rtti` under every Clang family; a Fennel UTF‑8 narrowing error, answered by scoping macOS to Forth-only; REST‑API immediate-mode GL; three missing debug-bridge GL stubs). The sixth was **not** a porting issue at all but a dormant 1998–2003 heap-corruption bug that only an arm64 ABI could expose — `MEMORY_DELETE_ARRAY` hardcoding an 8‑byte array cookie where the ARM C++ ABI uses 16. Full log: [2026-09-20-macos-phase0-green-baseline.md](2026-09-20-macos-phase0-green-baseline.md); the dormant bug: [BUGS.md](../BUGS.md).

Exit: `--frame-step-smoke=30 --cycles=1` exits 0 on the current headless backend. **MET — 2026‑09‑20.** Both halves of §8 are green (local steps 1–4, Codemagic steps 5–6). **Phase 1 is unblocked.**

### Phase 1 — Geometry reaches a backend (still headless, still no Metal)

The cheapest possible proof that §2.1 is right.

- Add `gfx/glpipeline` to the macOS `WF_DIRS` (`CMakeLists.txt:228-236`), with `backend_modern.cc` added to `WF_SKIP` for the `APPLE` arm (it is the only GL-bound file).
- Drop `renderpoly3d_stubs.cc` from the macOS source list (`CMakeLists.txt:360`).
- Instrument `HeadlessBackend` (`engine/stubs/renderer_stub.cc`) to count `DrawTriangle` calls and print the total at `EndFrame`.

Exit: the smoke run reports a **non-zero, stable per-frame triangle count** for snowgoons. This single number retires the largest uncertainty in the whole plan, on a headless build, for one CI run. If it comes back zero, the "backend-agnostic geometry" thesis is wrong and everything after this needs rethinking — better to learn it here than after the window exists.

**Estimated cost: 1–2 runs. Do not proceed past a zero.**

**DONE — 2026‑09‑20, `ec6c5e4d`, one run (3 Mac‑min).** The number came back
**1563 triangles per frame, identical on every rendered frame** — see §8 step 7. §2.1 is
confirmed: the eight geometry files are backend-agnostic, they compile and link on macOS with
no GL, and real snowgoons geometry reaches `RendererBackend::DrawTriangle` on a build with no
window and no renderer. **"Write eight Metal `RenderPoly3D` implementations" is work that does
not exist.** Phase 2 may start.

Landed exactly as specified, plus two things the spec implied but did not name:

- `backend_factory.cc` also came off the macOS explicit source list — it lives in
  `gfx/glpipeline`, so the new directory glob now supplies it; leaving both would double-add it.
- That `backend_modern.cc` is the *only* GL-bound file in the directory was **verified by grep,
  not assumed**: no `gl*()` call appears in any of the eight, nor in `glpipeline/rendobj3.cc`.

Two link hazards were cleared statically rather than by spending a run on them: `renderer.hp`
already has a `WF_TARGET_MACOS` arm supplying GL *types* via `<OpenGL/gl.h>` with the framework
unlinked (`renderer.hp:38-44`), and `globalRendererVariables` is defined in
`glpipeline/rendobj3.cc:48`, which `gfx/rendobj3.cc:36` already `#include`s on macOS.

### Phase 2 — Metal renders offscreen to a PNG (no window)

Still no windowing, still driven by `--frame-step-smoke`, but now through real Metal.

- Move `backend_metal.mm` → `gfx/metal/` (D3); compile it from both Apple arms; link Metal/QuartzCore on macOS (`CMakeLists.txt:922-933`).
- Point `backend_factory.cc:16-30`'s `WF_TARGET_MACOS` arm at `MetalBackendInstance()`.
- Add the **depth attachment** (§2, item 5): `depthAttachmentPixelFormat = MTLPixelFormatDepth32Float` on the pipeline, a depth `MTLTexture` sized to the target, and an `MTLDepthStencilState` with `depthCompareFunction = Less`, `depthWriteEnabled = YES`. Shared with iOS.
- Add an **offscreen render target** to the backend: render into an `MTLTexture` instead of a drawable, plus a blit-to-CPU readback. Drive it from `display_macos.cc` under a new `--capture-frame=N=<path.png>` flag.

Exit: CI artifacts a PNG of snowgoons frame N. **This is the milestone that turns CI from a build gate into a visual gate** — see §5. Expect several runs of first-light debugging here (winding order, column-vs-row-major MVP, NDC Z range `[0,1]` on Metal vs `[-1,1]` on GL).

The offscreen target is not throwaway: the editor's viewport embed (`wf_edit`) needs exactly this, and `docs/investigations/2026-05-26-macos-port-estimate.md` §E2 already identifies it as the editor's critical path.

### Phase 3 — Textures

Per D4 / O3. Exit: the Phase 2 PNG is texture-correct against a Linux GL capture of the same level and frame.

### Phase 4 — Window and input

- GLFW `GLFW_NO_API` window + `CAMetalLayer` (D5); `Display` switches from offscreen target to `nextDrawable`.
- Drawable size vs. window point size (Retina) — `contentsScale`, and the viewport/scissor math that `gfx/gl/viewport.cc` does on the GL side.
- Feed `_HALSetJoystickButtons` (the seam `gfx/gl/mesa.cc:496` uses on Linux) from GLFW key/mouse/gamepad callbacks.
- Implement `HALWindowCloseRequested`/`HALCloseWindow` for real in `hal/macos/window_macos.cc` (today they are atomics with no window behind them).
- `-width=N` / `-height=N` / `-fullscreen` → `glfwSetWindowSize` / `glfwSetWindowMonitor`, closing `TODO.md:7`.

Exit: an interactive `.app` that plays snowgoons.

### Phase 5 — Cleanups the renderer unblocks

- Re-enable WAMR on macOS (`CMakeLists.txt:119` → remove the `WF_WASM_ENGINE none` force; `:464-472` is already correct). Closes the last stale clause of `TODO.md:9`.
- Delete `hal/macos/gl_stubs.cc` and the macOS arm of `gfx/renderer.hp:38-45` once nothing calls GL.
- Feed the shared work back to iOS (Phase 2C‑B per D1) — **separate plan, separate TODO item.**
- `TODO.md:79` (`LIGHTING_PRELIT` for the sky dome) explicitly names "the glpipeline/Metal draw" and becomes a one-line change in both backends once both exist.

## 5. Build and test strategy under the existing conserve-minutes discipline

This is not a fresh problem: there is already a tracked budget position, and this plan has to fit inside it.

**No local Mac.** Searched the repo for any macOS dev-machine reference — none exists. `scripts/setup-debug-ssh.sh` is a Linux collaborator key, not a Mac. Every macOS artifact in this repo was authored from Linux and verified on Codemagic; `2026-05-26-macos-port-runtime-bringup.md:41` states it outright ("macOS-only new files can't be compiled off-Mac — that's the Codemagic build's job"), and `codemagic.yaml:161-162` calls the simulator screenshot step a *"Phase 1 Verify proxy for users without a local Mac"*.

**The existing discipline, and the hole in it.** [2026-05-12-codemagic-budget-monitor.md](2026-05-12-codemagic-budget-monitor.md) records the account hitting ~490 of 500 Mac‑min by day 12 of May 2026. Its **stop-bleed step landed** — `ios-simulator-debug` now has `events: []` with its `branch_patterns` commented out (`codemagic.yaml:108-115`), and `macos-desktop-debug` is manual-only for the same reason (`:372-374`). *Every Mac workflow in this repo is manual-trigger.* That is the conserve-minutes discipline, and it is the whole of it. The rest of that plan is still **OPEN** — its own status line says "no budget workflow; mac trigger not gated", and `.github/workflows/` contains only `blender-addon-tests.yml`. **So there is no quota visibility at all today.** Opening a renderer iteration loop against a pool nobody is measuring is the actual risk here, more than the raw minute count.

`macos-desktop-debug` does already carry the caching the budget plan asked for (`build-macos` build dir + the Jolt vendor extraction, `codemagic.yaml:360-368`) — a head start `ios-simulator-debug` never got.

**The arithmetic.** `codemagic.yaml:7-11` records 500 free Mac‑min/month on the individual plan; the public [pricing page](https://codemagic.io/pricing/) puts overage at $0.10/min and a dedicated M2 seat at $3,990/yr. `macos-desktop-debug` caps at 20 min (`codemagic.yaml:357`) but a warm-cache incremental build should land in the 3–6 min band. Call it **~80–120 useful macOS runs per month**, shared with whatever iOS and Android work is in flight.

**iOS Simulator draws on the *same* pool — this is settled, not a question.** The budget plan's entire causal story is that `ios-simulator-debug` *pushes* burned the 490 Mac‑min. Codemagic meters Mac instance-minutes, not products, and both workflows request `mac_mini_m2` (`codemagic.yaml:88` and `:356`). So "prototype the Metal work on iOS Simulator because it is unmetered relative to the Mac‑min budget" is **refuted**: it is the same budget, historically the *dominant consumer* of it, and it is the slower loop of the two (Xcode generator, simulator boot, install, launch — `codemagic.yaml:160-200`) on the platform with the unbuilt thread handoff (§2). It also has no cache. Prototyping there would cost more minutes per look, not fewer.

That leaves a budget that is *decent* for a gate and *terrible* for a shader loop. A renderer's natural loop is tens of edit-compile-look cycles per session at sub-minute latency; CI gives minutes-per-cycle with no interactive inspection, no Metal frame capture, no shader debugger. **Budget scarcity is therefore not a footnote — it dictates the phase order in §4.** Three consequences, already baked in above:

1. **Every phase exits on a machine-checkable signal, not on "it looks right."** Phase 1's exit is *an integer* (triangle count). Phase 2's is *a file* (a PNG). Both survive a batch-only workflow.
2. **The visual gate arrives before the window.** Phase 2 renders offscreen to a PNG precisely so that "does it look right" becomes a downloadable artifact comparable against a Linux GL capture, rather than something requiring an interactive session. Deferring pixels until the window exists would mean burning Mac‑min on a loop with no observable output.
3. **Each phase is a *single* CI run's worth of change.** Bundling Phases 2–4 into one push means a failure tells you only "something in the renderer is wrong" after a 6‑min run.

**Local pre-flight is free and must be exhausted first.** Before any Mac‑min is spent: the Linux build must stay green (source edits are shared), `cmake` configure must parse, and `codemagic.yaml` must be valid YAML — exactly the protocol `2026-05-26-macos-port-runtime-bringup.md:41` used successfully to land the headless port from Linux. Compile errors that a Linux build would have caught are the single most wasteful way to spend the budget.

**Options for a real interactive loop, and what to do about them** — these feed decision O1:

| Option | Assessment |
|---|---|
| **Land the budget monitor first** | [2026-05-12-codemagic-budget-monitor.md](2026-05-12-codemagic-budget-monitor.md) §2 (usage monitor via `GET /builds`, 50/80/95% alerts) is designed and unimplemented. **This is the cheapest item on the list and the only one that is pure upside** — it costs zero Mac‑min, it is a GitHub Actions workflow, and without it every option below is being chosen blind. Recommend landing it as a Phase‑0 sibling, or at latest before Phase 2. |
| **Prototype on iOS Simulator instead** | **Refuted above** — same Mac‑min pool, historically the dominant consumer of it, slower per look, no cache, and the platform with the unbuilt thread handoff. |
| **Codemagic interactive/remote access** | Codemagic documents a remote-access/VNC facility for debugging builds, but I have **not verified** whether it is available on the free individual plan, or how it meters against the 500‑min pool. **This is the single highest-value thing to check before committing to a build strategy** — if it exists and is affordable, it converts the problem from "batch-only" to "a few slow interactive sessions", and Phase 2's offscreen-PNG scaffolding becomes a convenience rather than a necessity. Verify against current docs; do not assume either way. |
| **Pay for Mac time** | Overage at $0.10/min makes an extra ~5 h/month cost ~$30 — cheap, and the right first escalation *once the monitor exists to tell you the 500 are actually gone*. The $3,990/yr seat is a different order of commitment and should be **milestone-gated**: justified only once Phase 2 is green and the work has demonstrably become an iteration-bound visual loop rather than a build-bound one. Do not buy it up front. |
| **Other providers already in the stack** | GitHub Actions is already wired in this repo (`.github/workflows/blender-addon-tests.yml`) and offers `macos-14`/`macos-15` arm64 runners — **free for public repositories**, with `tmate`-style SSH-into-the-runner actions giving a genuine interactive shell on a real Mac. It is also where the budget monitor was designed to live. If this repo is (or can be) public, or a paid-minutes GHA plan is acceptable, this is plausibly a *better* macOS bench than Codemagic for this specific work, on a **separate** budget from the Mac‑min pool. The option I would investigate first after the monitor. |
| **Borrowed/second-collaborator Mac** | The investigation references a second collaborator on the iOS port. If that person has Mac hardware, an afternoon of real interactive Metal debugging is worth more than a month of CI minutes. Worth asking before spending anything. |

## 6. Open decisions — these need the user's call

**O1 — Does a Metal renderer fit inside the existing conserve-minutes discipline, or does it justify a scope change?** Today that discipline is one rule: every Mac workflow is manual-trigger. That is adequate for a build gate and inadequate for a renderer's edit-compile-look loop, and the choice changes the *sequencing*, not just the cost — if a real interactive Mac (GitHub Actions runner + SSH, Codemagic remote access, or borrowed hardware) is available, Phase 2's offscreen-PNG harness can be trimmed and Phases 2–4 can merge; if it is batch-CI-only, the §4 ordering is mandatory. **Recommend, in order: (1) land the budget monitor from [2026-05-12-codemagic-budget-monitor.md](2026-05-12-codemagic-budget-monitor.md) — zero Mac‑min, and nothing else on this list should be decided blind; (2) check GitHub Actions macOS-runner eligibility for this repo and Codemagic's remote-access terms, before Phase 2 starts; (3) treat the $3,990 seat as a Phase‑2‑gated decision, never an upfront one.** Step (1) is a recommendation I am confident in; the choice among (2) and (3) I have deliberately not made.

**O2 — Is a macOS renderer the goal, or is the editor?** The investigation's §8 makes a sharp point: *"the playable game is a near-free byproduct of building the editor"*, and the editor's viewport embed needs the same offscreen `MTLTexture` target as Phase 2. If macOS `wf_edit` is the real destination, Phase 2's offscreen target should be designed as the editor's handshake surface from the start (replacing the GLX-typed `gfx/host_gl_context.h`) rather than retrofitted. That is a scope question about *why* this work is happening, and it is not mine to answer.

**O3 — Texture ownership: widen the seam, or sidecar?** D4(a) vs D4(b). (a) is the correct shape and puts working Linux/Android/Web texture code at risk while the Metal path is still unproven; (b) is contained but is a pointer-keyed cache over objects that do not announce their own destruction (`gfx/pixelmap.cc:106`). I lean (b)-then-(a) and flag that I am genuinely unsure.

**O4 — GLFW-for-`wf_game`, or a bespoke `NSWindow` host?** D5 recommends GLFW for editor/runtime parity, which means enabling GLFW's Cocoa backend and linking GLFW into `wf_game` for the first time on any platform (today only `wf_edit` links it, `CMakeLists.txt:1303`). A ~150-line AppKit host avoids that coupling at the price of forking input. This is an ergonomics-vs-sharing trade of the exact kind the brief says not to guess at.

**O5 — Does iOS get fixed in this work, or after?** D1 says macOS first and iOS inherits. That leaves iOS at cornflower blue for the duration. If shipping iOS matters sooner, the phase order changes.

## 7. Out of scope

`wf_edit` on macOS (CRDT, AVFoundation capture, collab transport — investigation §6). Universal binary / `lipo`. Code signing, notarization, Gatekeeper, `.dmg`. Steam macOS depot. iOS Phase 2C‑B itself (D1 makes it *easier*, does not do it). Shader hot-reload (`RendererBackend::ReloadProgram`, `gfx/renderer_backend.hp:89-96`) on the Metal path.

## 8. Verification

Steps a future implementation pass runs, in order. Per `~/CLAUDE.md` **Plan verification format**: keep these numbered steps verbatim, paste raw output in a code block under each, add PASS/FAIL, and write the result back into this file. Do not reorganize or summarize them.

**Local (free — run before every push that costs Mac‑min):**

1. `cd /home/will/WorldFoundry-wbniv && ./build_game.sh` — Linux build green (shared source edits must not regress Linux). Exit 0.

    ```
    $ cd /home/will/WorldFoundry-wbniv && ./build_game.sh
    /bin/bash: line 1: ./build_game.sh: No such file or directory
    EXIT=127
    ```

    **Deviation:** `build_game.sh` does not exist in the tree — the step as written cites a stale path. The canonical Linux build is `task build` (`Taskfile.yml:17`). Re-run with the working equivalent:

    ```
    $ task build
    ... (2760 lines; 0 occurrences of "error:" or "undefined reference")
      skip /home/will/WorldFoundry-wbniv/engine/stubs/physics_jolt.cc
      CC /home/will/WorldFoundry-wbniv/wfsource/source/physics/jolt/jolt_backend.cc

    === Linking ===

    Built: /home/will/WorldFoundry-wbniv/engine/wf_game
    Run:   cd /home/will/WorldFoundry-wbniv/wfsource/source/game && DISPLAY=:0 /home/will/WorldFoundry-wbniv/engine/wf_game
    EXIT=0
    ```

    **PASS** (via `task build`). The `WF_POSIX` / `WF_HAS_X11` introduction and the `platform_init.cc` guard change do not regress Linux — `WF_HAS_X11` is 1 on desktop Linux, so the X11 `-fullscreen` screen-size query still compiles and links exactly as before. The step's command should be corrected to `task build` in a future edit of this plan.

2. `cmake -S . -B /tmp/wf-cfgcheck -DCMAKE_BUILD_TYPE=Debug` — CMake branches parse. Exit 0.

    ```
    -- Found assembler: /usr/bin/cc
    -- Looking for mremap
    -- Looking for mremap - found
    -- Configuring done (7.2s)
    -- Generating done (1.0s)
    -- Build files have been written to: /tmp/wf-cfgcheck
    EXIT=0
    ```

    **PASS.**

3. `python3 -c 'import yaml,sys; yaml.safe_load(open("codemagic.yaml"))'` — workflow YAML valid. Exit 0.

    ```
    $ python3 -c 'import yaml,sys; yaml.safe_load(open("codemagic.yaml"))'
    step3 EXIT=0
    ```

    **PASS.** The new `.github/workflows/codemagic-budget.yml` parses too (checked in the same call).

4. `./build/wf_game --frame-step-smoke=30 --cycles=1 -L wflevels/snowgoons-blender/snowgoons-standalone.iff; echo $?` — Linux reference run still exits 0.

    ```
    $ ./build/wf_game --frame-step-smoke=30 --cycles=1 -L wflevels/snowgoons-blender/snowgoons-standalone.iff; echo $?
    /bin/bash: line 1: ./build/wf_game: No such file or directory
    127
    ```

    **Deviation:** the binary is at `engine/wf_game`, not `build/wf_game`, and the engine must run from `wfsource/source/game` with an absolute `-L` path (same convention `codemagic.yaml`'s macOS smoke step uses). Re-run corrected:

    ```
    $ cd wfsource/source/game && /home/will/WorldFoundry-wbniv/engine/wf_game \
        --frame-step-smoke=30 --cycles=1 \
        -L/home/will/WorldFoundry-wbniv/wflevels/snowgoons-blender/snowgoons-standalone.iff
    rest_api: server stopped
    delta too large: 1.000930786
    ...
    Tasker shutting down
    EXIT=0
    ```

    **PASS** (with the corrected path). The `delta too large` lines are the pre-existing wall-clock-vs-frame-step warning from the headless driver, not a regression.

**Codemagic `macos-desktop-debug` (manual trigger — one run per phase):**

5. *(Phase 0)* Ninja configure + `cmake --build --target wf_game` under Apple Clang — exit 0, no X11 references in `macos-build.log`.

    ```
    $ python3 ~/.claude/skills/codemagic-build/codemagic.py build \
        --app-id <WF_APP_ID> --workflow macos-desktop-debug
    [codemagic] no API token found — run the bootstrap subcommand, or set CODEMAGIC_API_TOKEN / CODEMAGIC_SSM_TOKEN
    ```

    **PASS — 2026‑09‑20** (`Build wf_game: success` on build `6aafcf69903254faf05d7835`). The
    original blocker below is kept for the record; it is resolved.

    ~~**BLOCKED — not run.**~~ No WorldFoundry Codemagic API token is reachable from this machine: nothing at `~/.config/codemagic/token`, `$CODEMAGIC_API_TOKEN` unset, and no `codemagic` parameter in SSM under any configured AWS profile. (`~/gustos-colores` has its own token at `/gc-app/codemagic-api-token`, but per `~/CLAUDE.md` **Per-domain / per-project credentials** that must not be borrowed for WorldFoundry.) Minting the token is the one irreducible manual step — Codemagic → account Settings → Integrations → Codemagic API → Show — after which `python3 ~/.claude/skills/codemagic-build/codemagic.py bootstrap` stores it and this step runs headlessly. The WF Codemagic `appId` is likewise not recorded anywhere in the repo and is needed both here and for `vars.WF_CODEMAGIC_APP_ID`.

    Everything this step would catch that *can* be checked off-Mac has been: the X11 break is guarded out by construction, verified by preprocessing the new macro block under each platform's defines —

    ```
    linux    -> RESULT WF_POSIX=1 WF_HAS_X11=1
    macos    -> RESULT WF_POSIX=1 WF_HAS_X11=0
    ios      -> RESULT WF_POSIX=1 WF_HAS_X11=0
    android  -> RESULT WF_POSIX=1 WF_HAS_X11=0
    web      -> RESULT WF_POSIX=1 WF_HAS_X11=0
    none     -> RESULT WF_POSIX=0 WF_HAS_X11=0
    ```

    — and no other file in the macOS source set includes an X11 or desktop-GL header (`gfx/display.hp:63`'s `<GL/gl.h>` sits under `VIDEO_MEMORY_IN_ONE_PIXELMAP`, which is not defined; `gfx/renderer.hp:44` is the intended `<OpenGL/gl.h>` arm).

6. *(Phase 0)* `wf_game.app/Contents/MacOS/wf_game --frame-step-smoke=30 --cycles=1 -L<snowgoons-standalone.iff>` — exit 0.

    ```
    build 6aafcf69903254faf05d7835 (18188fd1)   status: finished
        Build wf_game                      success
        Run headless frame-step smoke      success
    ```

    **PASS — 2026‑09‑20.** The token blocker above is closed (`task setup`, see
    `docs/SETUP.md`), and steps 5 and 6 were then carried the rest of the way to green in
    [2026-09-20-macos-phase0-green-baseline.md](2026-09-20-macos-phase0-green-baseline.md),
    which logs the six real failures Codemagic surfaced along the way — five build/config
    breaks and one genuine runtime heap corruption (a dormant 1998–2003 array-cookie bug that
    only an arm64 ABI could expose; see [BUGS.md](../BUGS.md)).

    **Phase 0's exit criterion is met. Phase 1 is unblocked.**

7. *(Phase 1)* Same smoke run — `macos-smoke.log` reports a non-zero, frame-stable `DrawTriangle` count. **Gate: a zero here invalidates §2.1; stop and re-plan.**

    Build `6aafd761e700ec9d4c515095` (`ec6c5e4d`), `macos-desktop-debug`, `mac_mini_m2` /
    AppleClang 21 / arm64 — `Build wf_game: success`, `Run headless frame-step smoke: success`.

    ```
    $ grep -c '^headless: frame' macos-smoke.log
    29

    $ grep '^headless: frame' macos-smoke.log | head -3
    headless: frame 1 DrawTriangle=1563 (total 1563)
    headless: frame 2 DrawTriangle=1563 (total 3126)
    headless: frame 3 DrawTriangle=1563 (total 4689)

    $ grep '^headless: frame' macos-smoke.log | tail -2
    headless: frame 28 DrawTriangle=1563 (total 43764)
    headless: frame 29 DrawTriangle=1563 (total 45327)

    $ grep -o 'DrawTriangle=[0-9]*' macos-smoke.log | sort | uniq -c
         29 DrawTriangle=1563

    $ grep -c 'ASSERTION\|corrupt' macos-smoke.log
    0
    ```

    **PASS — non-zero and exactly stable.** One distinct value across every rendered frame, zero
    variance; 45 327 triangles submitted in total. The gate is cleared, §2.1 is confirmed, and
    Phase 2 is unblocked.

    Two details worth carrying forward rather than glossing:

    - **29 `EndFrame` calls, not 30.** `StepFrame` runs the render block only under
      `if(_curLevel->camera() && _curLevel->camera()->ValidView())` (`game/game.cc:584`), and
      `EndFrame` is reached from `Display::RenderEnd` inside it — so one of the 30 steps drew
      nothing. The likely cause is the first frame, before the camera handler has produced a
      valid view. **Not proven from this log**: the counter numbers `EndFrame` calls, not
      `StepFrame` calls, so it cannot say *which* step was skipped. Harmless for this gate
      (non-zero + stable are both satisfied), but Phase 2 compares Metal's count against this
      reference, so a silently dropped frame would muddy that comparison — count `StepFrame`s
      alongside `EndFrame`s before leaning on the number.
    - **The `--memory-test` guard still passes on this build**, and prints
      `this ABI's compiler array cookie = 16 bytes`, so the Phase 0 arm64 fix is unaffected by
      pulling eight new TUs into the macOS build.
8. *(Phase 2)* `--capture-frame=30=$CM_BUILD_DIR/macos-frame30.png` — PNG artifacted, non-blank, geometry recognisably snowgoons.
9. *(Phase 2)* Depth correctness: the Phase 2 PNG shows no back-face bleed-through versus the Linux GL capture of the same level and frame.
10. *(Phase 3)* Texture correctness: Phase 2 PNG is texture-matched against the Linux GL capture.
11. *(Phase 4)* Interactive `.app` launches, renders, accepts keyboard/gamepad input, and closes cleanly (`HALWindowCloseRequested` path, `game/game.cc:296`).
12. *(Phase 4)* `-width=800 -height=600` and `-fullscreen` produce correctly sized windows — closes `TODO.md:7`.
13. *(Phase 5)* `-DWF_WASM_ENGINE=wamr` configures and links on arm64 Darwin; smoke run exits 0.

## 9. References

- [`TODO.md`](../../TODO.md):7, :9, :15, :79 — the four entries this plan touches
- [`CMakeLists.txt`](../../CMakeLists.txt):115-123 (macOS option gate), :157-161 (defs), :221-236 (source dirs), :300-305 (skip), :347-368 (stub sources), :464-472 (WAMR Darwin/AARCH64), :612-662 (Jolt), :765-770 (shell), :845-851 + :1130-1155 (`.app` bundle), :922-933 (frameworks), :1210-1244 + :1303 (GLFW)
- [`wfsource/source/gfx/renderer_backend.hp`](../../wfsource/source/gfx/renderer_backend.hp) — the seam every backend implements
- [`wfsource/source/gfx/glpipeline/rendfcl.cc`](../../wfsource/source/gfx/glpipeline/rendfcl.cc):13-22, :57-63 — proof the geometry files are backend-agnostic
- [`wfsource/source/gfx/glpipeline/backend_factory.cc`](../../wfsource/source/gfx/glpipeline/backend_factory.cc):14-31 — the per-platform selection arm
- [`wfsource/source/hal/ios/backend_metal.mm`](../../wfsource/source/hal/ios/backend_metal.mm):13-21, :110, :339-350, :432, :466 — the Metal backend and every place it stops short
- [`wfsource/source/hal/ios/native_app_entry.mm`](../../wfsource/source/hal/ios/native_app_entry.mm):62, :76-77 — "the Metal backend drops any batched triangles because no encoder is set"
- [`wfsource/source/hal/macos/display_macos.cc`](../../wfsource/source/hal/macos/display_macos.cc):14-16, :91-106, :131-136 — the headless `Display` that becomes the Metal frame owner
- [`wfsource/source/gfx/gl/display.cc`](../../wfsource/source/gfx/gl/display.cc):796, :818, :1027, :1167 — the Linux frame shape macOS mirrors
- [`wfsource/source/gfx/pixelmap.cc`](../../wfsource/source/gfx/pixelmap.cc):61, :106, :196-232 + [`pixelmap.hp`](../../wfsource/source/gfx/pixelmap.hp):68, :92 — the GL-welded texture path (D4)
- [`wfsource/source/hal/linux/platform_init.cc`](../../wfsource/source/hal/linux/platform_init.cc):50-52, :117-128 — the unguarded X11 include compiled into macOS (D6)
- [`codemagic.yaml`](../../codemagic.yaml):7-11 (budget note), :108-115 (iOS trigger gated off), :160 (iOS screenshot proxy), :354-420 (`macos-desktop-debug`), :360-368 (caching), :384-394 (configure — no physics override)
- [2026-05-12-codemagic-budget-monitor.md](2026-05-12-codemagic-budget-monitor.md) — the tracked budget position; stop-bleed landed, monitor/caching/dedupe still OPEN
- [2026-05-26-macos-port-runtime-bringup.md](2026-05-26-macos-port-runtime-bringup.md):4 (stale status), :41 (Linux-side pre-flight protocol), :58 (the deferral this plan picks up)
- [Codemagic pricing](https://codemagic.io/pricing/) — 500 free Mac‑min/month, $0.10/min overage, $3,990/yr M2 seat
