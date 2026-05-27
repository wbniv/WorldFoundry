# macOS Port — Effort & Time Estimate (Runtime, then Engine delta)

**Date:** 2026-05-26
**Author:** investigation (Claude)
**Status:** Estimate only — no macOS branch exists yet. Greenfield. **Recommends targeting Metal directly** (see premises).
**Repo:** [github.com/wbniv/WorldFoundry](https://github.com/wbniv/WorldFoundry)

## Decision premises

Two facts set after the first draft, and they drive the renderer recommendation:

1. **No schedule pressure** on the macOS version — there is no reason to ship it early.
2. **The iOS Metal renderer will be finished before the macOS port begins.** Metal does *not* render game content today (iOS is at "cornflower blue", Phase 2B3), but iOS Phase 2C+ completes on its own schedule, ahead of any macOS work.

Together these reverse the v1 recommendation. v1 recommended OpenGL because Metal was unfinished and GL ships *now*. With no rush and a *proven* Metal renderer available at macOS-start-time, the only thing the GL-first path buys is throwaway: **OpenGL-now-then-Metal-later wastes ~1.5–2 weeks on the runtime (~2.5–3.5 weeks full-stack)** redoing the renderer-coupled layer twice (see §4). So: **go Metal-direct.**

## TL;DR

| Pass | Scope | Effort (avg programmer) | Wall-clock |
|------|-------|-------------------------|------------|
| **1 — Runtime** | `wf_game` plays a level natively on macOS, on Metal | **≈ 15 working days** (range 12–25) | **≈ 3 weeks** (2–5) |
| **2 — Engine delta** | `wf-edit` collaborative editor + CRDT + collab A/V, *given* the runtime works | **≈ 20 working days** (range 16–28) | **≈ 4 weeks** (3–6) |
| **Both, sequential** | Full macOS desktop story | ≈ 35 working days | ≈ 7–9 weeks |

The effort envelope is the **same whether the runtime targets GL or Metal directly** — Metal-direct trades "debug GL core-profile first-light on macOS" for "adapt the iOS Metal view-host to AppKit." What's *not* the same is the **GL-then-Metal** path, which is GL-direct **plus ~1.5–3.5 weeks of rework** and is the option these premises rule out.

These numbers are on the **average-programmer scale** per [estimate convention](../../CLAUDE.md). This project's *historical* velocity is far above that (iOS went Phase 0 → all-sources-compiling in ~2 days), so actuals will likely beat these — but the estimate does not bake in that speed.

**Prerequisite:** iOS Metal renderer complete and proven (iOS Phase 2C onward). Per the sequencing above this is a *satisfied precondition* at macOS-start, not a risk carried by this estimate. Finishing iOS Metal is iOS-side work, out of scope here.

---

## 1. Scope & interpretation

"macport (runtime only)" then "the engine … a delta from the runtime" maps cleanly onto the codebase's real seam, the **`WF_ENABLE_EDITOR` boundary** ([`CMakeLists.txt:60`](../../CMakeLists.txt), [feedback_editor_code_compile_gate](../../CLAUDE.md)):

- **Pass 1 — Runtime** = the shipped game engine: `wf_game` boots `cd.iff`, loads a level, renders, takes input, plays. `WF_ENABLE_EDITOR=OFF`. This is "the World Foundry game engine" as a player experiences it.
- **Pass 2 — Engine delta** = everything a *shipped runtime build* leaves out: the `wf-edit` collaborative editor app, the CRDT/Yjs stack, in-editor voice/video chat, and the host-side authoring tools. `WF_ENABLE_EDITOR=ON`. This is a strict superset that *links* the Pass-1 engine library and adds to it.

> Note on what is **not** in the delta: the TCP debug bridge, REST API, and the full scripting-engine roster (Lua/Fennel/QuickJS/WAMR/Wren) are **on by default in a desktop runtime build** — they're gated off only on Android/iOS ([`CMakeLists.txt:66`](../../CMakeLists.txt)), not by `WF_ENABLE_EDITOR`. So they come along *for free* in Pass 1 on macOS. The honest Pass-2 delta is the **editor app + collaboration + Rust/CRDT + AVFoundation capture**.

"macOS port" here means a **native desktop `.app`** (GLFW-Cocoa window, keyboard/mouse/gamepad, runs like any Mac app), targeting **Apple Silicon (arm64) first** — that's what Codemagic's `mac_mini_m2` runners and 2026-era Macs are. A universal (arm64 + x86_64) binary is a later distribution concern, not a porting concern.

## 2. Why macOS is cheap: the HAL is abstracted, and iOS retired the hard risks

Two prior ports already did most of the de-risking:

1. **Apple-Clang compilation is a solved problem.** The iOS port got *all ~120 engine sources* compiling and linking under Apple Clang for arm64 in ~2 days (wf-status: iOS Phase 1 → 2B2, 2026-04-22). The legacy-`register`, `-Wno-register`, `SCALAR_TYPE_FLOAT`, and pool-alignment (`WF_POINTER_ALIGN`) issues are already fixed in-tree. macOS desktop is the *same compiler* with *fewer* restrictions than the iOS Simulator.
2. **The engine is cleanly HAL-split, *including a swappable renderer backend*.** Platform code lives behind three directory swaps in [`CMakeLists.txt:128-162`](../../CMakeLists.txt) — `hal/{linux,android,ios}`, a renderer-backend `#define`, and a per-platform shell file ([`CMakeLists.txt:579`](../../CMakeLists.txt)). The renderer is already pluggable: [`backend_factory.cc`](../../wfsource/source/gfx/glpipeline/backend_factory.cc) picks Metal on iOS vs GL elsewhere via `#ifdef`, with [`backend_metal.mm`](../../wfsource/source/hal/ios/backend_metal.mm) and the GL [`backend_modern.cc`](../../wfsource/source/gfx/glpipeline/backend_modern.cc) as siblings. Adding macOS is *selecting the Metal backend for a 4th platform arm*, not writing a renderer.

The architecture, with macOS's reused-vs-ported split (Metal-direct):

```
                       wf_game  (macOS .app, arm64, Metal)
   ┌──────────────────────────────────────────────────────────┐
   │  game · movement · room · physics (Jolt) · scripting ·     │  REUSED as-is
   │  anim · menu · particle · math · iff · mailbox · asset ·   │  ~56k LOC, already
   │  loadfile · timer · memory · streams                       │  Apple-Clang-clean
   ├───────────────────────── gfx ─────────────────────────────┤  via iOS Phase 2B2
   │  RendererBackend = Metal  (backend_metal.mm + MSL)         │  REUSED from iOS
   │                                                            │  (proven by start)
   ├────────────────────────────────────────────────────────────┤
   │  HAL                                                        │
   │    audio  (miniaudio → CoreAudio) ................. REUSE   │
   │    assets (asset_accessor_posix, Darwin POSIX) .... REUSE   │
   │    savegame (savegame/linux, POSIX) ............... REUSE   │
   │   ┌── windowing  GLFW window (NO_API) + CAMetalLayer ┐ PORT │  ← the actual work
   │   │              + CVDisplayLink present             │      │     (renderer host +
   │   └── input      GLFW key/mouse/gamepad ────────────┘ PORT  │      desktop input)
   └────────────────────────────────────────────────────────────┘
```

The thing being *ported* is the part touching the window system and the Metal drawable. Everything above it is identical to the iOS/Linux builds. **GL fallback:** if the iOS-Metal prerequisite slips, the Linux GL backend (`#version 330 core`) still runs natively under macOS OpenGL 4.1 — a working contingency, just not the plan (see §3).

## 3. The renderer decision — Metal-direct

| | **Metal-direct (recommended)** | **OpenGL (fallback)** | ~~GL-now-then-Metal-later (ruled out)~~ |
|---|---|---|---|
| Renderer code | iOS `backend_metal.mm`, **reused** | Linux GL backend, reused | both, sequentially |
| Shaders | MSL (proven on iOS by start-time) | `#version 330 core` (runs on macOS GL 4.1) | both |
| Windowing | GLFW + `CAMetalLayer` + CVDisplayLink | GLFW-Cocoa + NSGL 3.3-core ctx | GL host, then Metal host |
| Prereq | iOS Metal done (met by sequencing) | none | none |
| Lifespan | **shared renderer with iOS** | a 3rd renderer flavor to maintain | converges late |
| Cost | ~3 wk runtime | ~3 wk runtime | ~3 wk **+ 1.5–2 wk rework** |
| When it wins | no rush + Metal proven first ← **our case** | need to ship *today* / Metal not trusted | never, given our premises |

**Recommendation: Metal-direct for both passes.** Rationale, given the premises:
- With **no rush**, the GL path's "ships now" advantage is worthless.
- With **iOS Metal finishing first**, the renderer macOS would reuse is *already proven* by the time work starts — so Metal-direct carries no more renderer risk than GL, and arguably less (macOS's deprecated GL core profile has its own driver/strictness quirks).
- Metal-direct gives macOS + iOS **one shared renderer** (`backend_metal.mm` + MSL), instead of leaving macOS on a GL path that either lingers forever or gets converted later at the cost in §4.
- Windowing stays on **GLFW** (already vendored, already used by the editor): a `GLFW_NO_API` window with a `CAMetalLayer` attached via `glfwGetCocoaWindow`. This unifies runtime + editor windowing and reuses GLFW input.

**OpenGL remains the documented fallback** — it works on macOS today (GL 4.1 ≥ the 3.3-core shaders) and is the right call *only if* the iOS-Metal prerequisite fails to land before macOS work must start.

## 4. The rework cost of GL-first (why we don't hedge with GL now)

If macOS shipped on GL now and converted to Metal later, the waste is the renderer-API-specific layer, built and then discarded. Most of the port is renderer-agnostic and survives either way:

| Macport runtime work | Survives a GL→Metal switch? | ~days |
|---|---|---|
| CMake branch skeleton, `.app` bundling | yes (only the framework/`#define` line changes) | ~0 waste |
| Input, audio (CoreAudio), assets, WAMR-aarch64, Jolt | **renderer-agnostic — survives** | ~0 waste |
| Integration: boots, input works, level loads | survives | ~0 waste |
| **GL context creation + swap-buffers glue** | **deleted** | ~4–5 |
| **GL core-profile first-light debugging** (VAO strictness, Retina) | **never needed on Metal** | ~1–2 |
| **The conversion**: rip out GL, wire `CAMetalLayer`/CVDisplayLink, re-verify a 2nd time | overhead Metal-direct never pays | ~2 |

Rough totals: **Metal-direct runtime ≈ 13 days; GL-then-Metal ≈ 21 days → ~8 days (~1.5–2 weeks) wasted**, against ~9–10 days of renderer-agnostic work identical either way. Building the Metal windowing (~3–4 days) is *not* waste — it's paid once in both. **The editor adds a similar increment** (~1–1.5 weeks): its viewport is `imgui_impl_opengl3` + the GLX-typed host handshake, which would be redone as `imgui_impl_metal` + a Metal-texture handshake. So full-stack GL-first rework ≈ **2.5–3.5 weeks** — pure loss under our premises.

> The only structural insurance that *would* shrink the waste (use a GLFW window that can later host a `CAMetalLayer`; keep everything behind the `RendererBackend` factory) is exactly what Metal-direct does from day one — so there's no reason to take the GL detour first.

## 5. Pass 1 — Runtime macport (Metal-direct)

Get `wf_game` to boot `cd.iff`, load Snowgoons, render via the reused Metal backend, and respond to keyboard/gamepad — as a native `.app`.

| # | Item | What it touches | Effort | Risk |
|---|------|-----------------|-------:|------|
| R1 | **CMake macOS-desktop branch** — a 4th arm in the platform `if/elseif`: Metal `RENDERER_*` like iOS, Apple frameworks (Metal/MetalKit/QuartzCore/CoreAudio/AudioToolbox), `.app` via `MACOSX_BUNDLE` (reuse the iOS bundle block at [`CMakeLists.txt:835`](../../CMakeLists.txt)), arm64, **Ninja** generator | `CMakeLists.txt`, new `Taskfile` target | 1–2 d | Low |
| R2 | **Metal windowing host** — a `GLFW_NO_API` window with a `CAMetalLayer` attached (`glfwGetCocoaWindow`), driven by CVDisplayLink; wire the iOS-proven [`backend_metal.mm`](../../wfsource/source/hal/ios/backend_metal.mm); adapt the UIKit `metal_view.mm` host to AppKit/CAMetalLayer + add an offscreen-target path for the editor (Pass 2) | new `hal/macos` view host, `backend_factory` arm | 3–5 d | **Med** — UIKit→AppKit + CADisplayLink→CVDisplayLink adaptation (renderer itself proven) |
| R3 | **Input** — GLFW key/mouse/gamepad callbacks → WF input map, mirroring [`hal/linux/input.cc`](../../wfsource/source/hal/linux/input.cc) | new `hal/macos/input` | 2–3 d | Low |
| R4 | **Audio** — miniaudio's CoreAudio backend (proven on Darwin by the iOS build); link `CoreAudio`/`AudioToolbox`. ~0 new code | `CMakeLists.txt` link libs | 0.5–1 d | Low (verify needs a real Mac w/ speakers — [audio_verify](../../CLAUDE.md)) |
| R5 | **Assets / bundle** — `cd.iff` into `.app/Contents/Resources` (reuse the iOS resource-copy pattern); confirm `asset_accessor_posix` on Darwin | `CMakeLists.txt`, `hal/macos` shim | 1 d | Low |
| R6 | **WAMR on Apple Silicon** — `invokeNative_em64.s` is x86_64-only; `invokeNative_aarch64.s` exists → set `WAMR_BUILD_TARGET=AARCH64` for arm64 (or gate WAMR off as mobile does) | [`CMakeLists.txt:313`](../../CMakeLists.txt) | 0.5–1 d | Low |
| R7 | **Physics (Jolt)** — keep Jolt: the iOS fallback to legacy is **Xcode-generator-specific** ([`CMakeLists.txt:447`](../../CMakeLists.txt)); macOS desktop uses Ninja, so Jolt builds like Linux | verify only | 0.5 d | Low |
| R8 | **Integration & first playable** — boot Snowgoons, move the player, debug the inevitable framework/link/focus/Retina issues | end-to-end | 3–5 d | **Med** |
| R9 | **CI** — native-macOS Codemagic workflow (mirror the iOS-sim one, but a desktop target + headless screenshot verify) | `codemagic.yaml` | 1–2 d | Low |

**Total: 12.5–24.5 person-days → central ≈ 15 days ≈ 3 weeks.** Risk concentrates in **R2** (adapting the iOS Metal view-host to an AppKit desktop drawable + an offscreen target) and **R8** (integration). Because the Metal *renderer* arrives proven from iOS, R2 is "windowing/present glue," not "build a renderer" — which is why the envelope matches the GL path despite swapping APIs.

### Notable runtime risks
- **iOS view-host assumes UIKit conventions.** `metal_view.mm` is built around `CADisplayLink` + a `UIView`-backed `CAMetalLayer` + iOS app lifecycle. The desktop host needs `CVDisplayLink` (or the GLFW frame loop), an AppKit/GLFW-owned layer, and desktop activation/focus. The *backend* (`backend_metal.mm`, MSL, draw path) is reused unchanged; the *host* is the new code.
- **Offscreen render target.** iOS only ever renders to the on-screen drawable. The editor (Pass 2) needs the engine to render into an offscreen `MTLTexture`. Add that target path to the Metal backend during R2 so Pass 2 can compose it — the GL path had the analogous FBO need.
- **Retina / HiDPI.** Drawable size ≠ window point size; viewport/scissor math in [`viewport.cc`](../../wfsource/source/gfx/gl/viewport.cc) needs the drawable scale.

## 6. Pass 2 — Engine (editor) delta (Metal-flavored)

Given a working Metal runtime, add the `wf-edit` collaborative editor ([`CMakeLists.txt:910-1021`](../../CMakeLists.txt)). The editor *links the Pass-1 engine library* and composites the engine viewport into a GLFW+ImGui host window. On Metal that means an offscreen `MTLTexture` drawn via `imgui_impl_metal` — the analogue of today's GLX host handshake.

| # | Item | What it touches | Effort | Risk |
|---|------|-----------------|-------:|------|
| E1 | **Rust / Corrosion / CRDT** — `libwfcrdt.a` wrapping `libyrs.a` via Corrosion+Cargo. Cross-platform; Corrosion supports macOS. Mostly "rustup + arm64 target + verify" | [`engine/crdt`](../../engine/crdt), `cmake/Corrosion` | 1–2 d | Low |
| E2 | **Host-context handshake → Metal** — today [`host_gl_context.h`](../../wfsource/source/gfx/host_gl_context.h) carries `Display*`/`Window`/`GLXContext` and [`main.cc:839-851`](../../engine/wf_edit/main.cc) uses `glfwGetGLXWindow`/`glfwGetGLXContext`. Replace with a Metal handshake: editor passes its `MTLDevice`/command queue + target texture; engine renders the viewport into it | `host_*_context.{h,cc}`, `wf_edit/main.cc`, Metal backend offscreen target (from R2) | 4–6 d | **Med-High** |
| E3 | **wf-edit build** — GLFW-Cocoa + ImGui with `imgui_impl_glfw` + **`imgui_impl_metal`** (swap from `imgui_impl_opengl3`); drop the X11-only GLFW config; link Metal frameworks | [`CMakeLists.txt:920`](../../CMakeLists.txt) | 1–2 d | Low |
| E4 | **Camera capture V4L2→AVFoundation** — [`video_track.cc`](../../engine/wf_edit/video_track.cc) does VP8 + **V4L2** capture (Linux-only). Net-new AVFoundation `AVCaptureSession` backend for the Mac camera | new `wf_edit/video_capture_avf.mm` | 4–6 d | **Med-High** |
| E5 | **Mic capture + codecs** — Opus + libvpx via Homebrew (portable C); mic via miniaudio CoreAudio capture | `voice_track.cc`, deps | 1–2 d | Low |
| E6 | **Collab transport on macOS** — UDP-multicast discovery ([`collab_session.cc`](../../engine/wf_edit/collab_session.cc)), WS relay ([`ws_client.cc`](../../engine/wf_edit/ws_client.cc)), and the **mandated** libdatachannel DTLS-SRTP + `wss` encryption ([internet-voice-video investigation](2026-05-26-internet-voice-video-nat-traversal.md), [collab encryption requirement](../../CLAUDE.md)). Sockets portable; verify macOS multicast (entitlement quirks on recent macOS) | transport files, libdatachannel via brew | 2–3 d | Med |
| E7 | **Homebrew dep bootstrap** — a macOS equivalent of the `worldfoundry-editor-dev` apt metapackage (opus, libvpx, libdatachannel; GLFW is vendored); CMake `find_package`/`pkg_check_modules` paths under `/opt/homebrew` | docs + CMake | 1–2 d | Low |
| E8 | **wf-relay** — standalone Cargo binary ([`CMakeLists.txt:1016`](../../CMakeLists.txt)); builds on macOS unchanged | verify | 0.5 d | Low |
| E9 | **Editor test suite + screenshot verify** — `wf_edit_spawn_confirm` / `_undo` / `_add` ([`CMakeLists.txt:993-1012`](../../CMakeLists.txt)) green on macOS; screenshot proof per [screenshots-for-proof](../../CLAUDE.md) | CTest, capture | 2–3 d | Low-Med |

**Total: 16.5–27.5 person-days → central ≈ 20 days ≈ 4 weeks.** Risk concentrates in **E2** (the editor's viewport-embed mechanism, re-expressed in Metal against the offscreen target) and **E4** (a net-new AVFoundation capture path — V4L2 has no Mac analogue to reuse).

### What is *not* a problem in the delta
- **ImGui** has a first-class Metal backend (`imgui_impl_metal`); ImGuizmo, imgui_markdown, nlohmann/json are header-only / portable.
- **Yrs / Yjs** — pure Rust; the [yrs upgrade decision](../../CLAUDE.md) is platform-agnostic.
- **Toolchain bonus:** the editor's Linux Release build *fails* on the engine's Clang-only `-flto=thin` (which is why Linux editor builds are Debug/GCC — [wf_edit build path](../../CLAUDE.md)). On macOS *everything is Clang*, so a Release editor build is actually **easier** than on Linux.
- **The Rust host tools** (iffcomp-rs, levcomp-rs, textile-rs, chargrab-rs) build on macOS trivially, but aren't on the critical path — level-building can stay on a Linux host.

## 7. Cross-cutting concerns

- **Architecture — arm64 first.** Target Apple Silicon (matches Codemagic `mac_mini_m2`, 2026 Macs, and the iOS Metal backend's native target). The only arch-sensitive engine code is WAMR's asm (R6) and the pool-alignment work already landed. A universal binary (`lipo` arm64+x86_64) is a *distribution* task, ~1–2 d, deferrable.
- **CI is already paid for.** Codemagic's Mac runners build native macOS the same way they build the iOS Simulator today ([`codemagic.yaml`](../../codemagic.yaml); iOS builds avg 3.4 min, budget 500 Mac-min/mo). A `macos-desktop-debug` workflow is a near-copy of `ios-simulator-debug`. **No user Mac is required** for build or headless verify.
- **Distribution paths exist.** The [`steam/`](../../steam) dir (controller config) signals desktop-Steam intent; macOS is a first-class Steam target. Steam's macOS redistributable (`libsteam_api.dylib`) would need wiring analogous to the Linux block ([`CMakeLists.txt:716`](../../CMakeLists.txt)) — only if `WF_ENABLE_STEAM=ON`, which is off by default. Direct `.dmg`/notarized `.app` is the other path.
- **Code signing.** Not needed for local dev or Codemagic headless verify (iOS Phase 1 ran unsigned on the Simulator). Needed for Gatekeeper-clean distribution (Developer ID + notarization) — a distribution task, ~1–2 d once an Apple Developer account exists (the [$99 account is still pending](../../CLAUDE.md); the macOS port can proceed unsigned until then).

## 8. Sequencing

```
   (iOS Metal, Phase 2C+ — iOS-side, finishes first) ──────┐
                                                           ▼
Pass 1 (runtime, ~3 wk)                 Pass 2 (engine delta, ~4 wk)
─────────────────────────               ──────────────────────────────
R1 CMake branch        ─┐               E1 Rust/CRDT        ─┐ (parallelizable
R7 Jolt verify          │ week 1         E3 wf-edit build    │  with late Pass 1)
R6 WAMR aarch64        ─┘               E2 host-Metal embed ─┘ ← critical path
R2 Metal view host    ─┐ week 2         E4 AVFoundation cap ─┐
R3 input               │                E5 mic + codecs      │ weeks 2–3
R4 audio / R5 bundle  ─┘               E6 collab transport  ─┘
R8 integration/playable┐ week 3         E7 brew deps / E8 relay  week 3
R9 CI                  ┘                E9 tests + screenshots   week 4
        │                                        │
        ▼                                        ▼
   PLAYABLE .app                          COLLABORATIVE EDITOR .app
```

- **iOS Metal completion gates the start** — but it's expected to land first regardless, so it's a precondition, not a blocker on the critical path.
- **Pass 2 contains Pass 1.** The editor links and runs the engine *and renders its viewport*, so "build the editor" forces "make the engine run on macOS" — which is essentially all of Pass 1's renderer/windowing/input/build work. The ~4-week editor figure is small *only because Pass 2 is scoped as a delta on a finished Pass 1*; built cold, the editor would cost ≈ Pass 1 + Pass 2 ≈ 7 weeks. Practical consequence: **the playable game is a near-free byproduct of building the editor** (~2–3 days of `wf_game`-specific app-shell + bundling + CI on top). So doing both passes is the right plan even if the editor is the real goal.
- **Front-load the two scary items** within each pass: R2 (Metal view host + offscreen target) and E2 (Metal viewport embed). Both are "blank screen until it's exactly right" tasks; failing fast on them de-risks the rest.
- The [iOS port has a second collaborator](../../CLAUDE.md); once R2 lands, the editor's E1/E3 can proceed in parallel.

## 9. Open questions (decisions, not blockers)

1. ~~**GL vs Metal**~~ — **resolved: Metal-direct**, per the premises (§3). GL is the documented fallback only if the iOS-Metal prerequisite slips.
2. **arm64-only vs universal** — recommended arm64-first, universal deferred to distribution.
3. **GLFW-window-hosts-`CAMetalLayer`, or raw AppKit/MTKView?** — recommended GLFW (vendored, editor already uses it, unifies runtime+editor windowing). Raw AppKit is more "native" but unjustified for a windowing shim.
4. **Does the macOS runtime ship the full scripting roster** (Lua/JS/WAMR/Wren) like Linux desktop, or trim to Forth-only like mobile? Desktop has the RAM/flash budget, so default to the full roster; trimming is a one-line `if(APPLE AND NOT IOS)` change if desired.

## 10. Out of scope

App Store / notarized distribution, Steam macOS depot upload, universal-binary lipo, Touch Bar / macOS-specific UI chrome, sandbox entitlements beyond camera/mic for E4/E6, localization, crash reporting. (Parallels the [Android port closure](2026-04-18-android-port-closure.md) "intentionally out of scope" list.)

## References

- [`CMakeLists.txt`](../../CMakeLists.txt) — platform branches (`:103-162`), Jolt/Xcode note (`:447`), iOS bundle (`:835`), wf-edit target (`:910-1021`)
- [`wfsource/source/gfx/glpipeline/backend_factory.cc`](../../wfsource/source/gfx/glpipeline/backend_factory.cc) — the renderer-backend selection seam macOS plugs into
- [`wfsource/source/hal/ios/backend_metal.mm`](../../wfsource/source/hal/ios/backend_metal.mm) + [`metal_view.mm`](../../wfsource/source/hal/ios/metal_view.mm) — the Metal renderer (reused) and UIKit view-host (adapted to AppKit)
- [`wfsource/source/gfx/glpipeline/backend_modern.cc`](../../wfsource/source/gfx/glpipeline/backend_modern.cc) — `#version 330 core` GL backend (the macOS GL *fallback*)
- [`wfsource/source/gfx/host_gl_context.h`](../../wfsource/source/gfx/host_gl_context.h) + [`engine/wf_edit/main.cc`](../../engine/wf_edit/main.cc) — GLX-typed editor handshake to re-express in Metal (E2)
- [docs/plans/2026-04-21-ios-port-codemagic.md](../plans/2026-04-21-ios-port-codemagic.md) — iOS port plan/phasing (the Metal prerequisite lives here)
- [docs/investigations/2026-04-18-android-port-closure.md](2026-04-18-android-port-closure.md) — comparable port closure (calibration)
- [docs/investigations/2026-05-18-collaborative-level-editor-design.md](2026-05-18-collaborative-level-editor-design.md) — editor architecture
- [docs/investigations/2026-05-26-internet-voice-video-nat-traversal.md](2026-05-26-internet-voice-video-nat-traversal.md) — collab encryption requirement (E6)
- [docs/wf-status.md](../wf-status.md) — iOS phase status ("cornflower blue" / Phase 2B3)
