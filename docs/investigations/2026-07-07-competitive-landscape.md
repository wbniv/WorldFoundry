# Investigation: competitive landscape — browser-collaborative-3D, and where WorldFoundry's slot actually is

**Date:** 2026-07-07
**Status:** Deep-research output (verified, 107 agents). Maps the browser / real-time-collaborative 3D editor field and locates WorldFoundry's defensible ground. Companion to the [A/V + collaboration validation](2026-07-07-av-and-collab-validation.md) (which found Spline holds the *design* corner) — this pass finds the game-worlds corner is held too.

## Bottom line: the collaboration is commoditized — the moat is the engine

Two passes now converge on one uncomfortable, clarifying fact:

> **Real-time collaborative browser 3D editing is no longer a differentiator.** It ships in *at least three* adjacent products — **PlayCanvas** (game engine), **Spline** (design), **Tabula Sono** (VTT). WorldFoundry cannot claim "Figma-for-3D, in the browser, together" as novel; that lane is occupied.

But the same research confirms the flip side:

> **No competitor occupies WorldFoundry's *specific* slot:** a **fixed-point, tiny, deterministic engine that runs everywhere down to ESP32-class hardware**, with **one-click export to a shippable retro game** and **VTT *authoring***. The moat rests entirely on the **engine + export target**, not on the editor.

This is not a demotion of the strategy — it's a **relocation of the moat onto exactly what the [sim-env doc](2026-07-05-worldfoundry-default-sim-environment.md) already called the deepest asset**: footprint + determinism ("the engine is the moat, not the editor"). The competitive field vindicates that thesis and retires the "browser collaboration is our edge" framing.

## The competitive map

| Slot | Who owns it | Browser? | Real-time co-edit? | What they *lack* vs WorldFoundry |
|---|---|:--:|:--:|---|
| **Browser game-worlds** (the direct analog) | **PlayCanvas** (Snap-owned) | ✅ | ✅ ("at the heart of the Editor") | Fixed-point / tiny / ESP32-embedded; retro one-click-shippable export; VTT features. It's a **WebGL/WebGPU float** cloud engine. |
| **Design / web-3D** | **Spline** | ✅ | ✅ (Figma-style) | Game-engine export, level building, VTT, retro/embedded. Output is static-mesh interchange (glTF/USDZ/STL), not a game. |
| **VTT *play*** | **Tabula Sono** | ✅ | ✅ (invite-link) | Collaborative **play** (moving minis), **not** collaborative *building* or export. |
| **Retro-export (proof the niche is real)** | **GB Studio** | ⬇ desktop | ❌ | One platform only (Game Boy ROM); single-author; no 3D/collab. But its itch.io + physical-cartridge ecosystem **proves retro one-click export is demanded.** |
| **Heavyweight pro engines** | UEFN / Unreal / Unity / Roblox Studio | ❌ (30–40GB desktop) | mixed (Unity → version control) | Not browser; not tiny/embedded; not the long tail. |
| **Fixed-point + embedded + retro-export + VTT-*authoring*** | **— nobody —** | — | — | **This is WorldFoundry's ground.** |

## The competitors that matter

**PlayCanvas — the direct analog, and it already ships (high confidence).** *"Real-time collaboration is at the heart of the PlayCanvas Editor… Multiple users can work together to build a scene"* — Figma-style presence bar, per-user colors, live selection, colored camera frustums in the viewport. Snap-owned (acquired 2017, reported 2018); **Free $0 / Personal $15/mo / Org $50/seat/mo**, with real-time collaboration on *even the free tier* (paid gates privacy, not collab); used by King, Disney, Nickelodeon. **Verdict: the generic "browser + collab + game engine" slot is taken.** What it is *not*: a fixed-point/tiny/embedded engine, and it has no retro-ROM export or VTT features (an absence inference from its WebGL/WebGPU float architecture — technically sound, but worth spot-checking against any PlayCanvas embedded roadmap; see open questions).

**Spline — the design lane (high confidence).** Browser, no-code, collaborative 3D for websites / product / brand — explicitly "an alternative to Unreal/Unity *for designers*." Funding, corrected: **$15M seed (Jul 2023, Gradient Ventures) + $10M Series A (Aug 2024, Third Point Ventures)**; cumulative ~$32M+ (approximate). The widely-cited "~$15M" is the *seed*, not the total. Gaps: no game-engine export, no level building, no VTT, no retro/embedded — it cannot follow WorldFoundry into games.

**Tabula Sono — the VTT threat (high confidence, with a crucial nuance).** A browser, no-install 3D virtual tabletop with single-invite-link multiplayer. **But it's collaborative *play* (moving minis at the table), not collaborative *building* or export.** So the VTT-*play* slot is occupied; the VTT-*authoring* + export slot the [VTT plan](../plans/2026-07-07-vtt-wedge.md) targets is not — but Tabula Sono is the incumbent to beat and the first competitor to name in that plan.

**GB Studio — the demand proof (high confidence).** One-click export to real Game Boy ROMs that run on DMG/Pocket/Color hardware and flash carts, plus web builds, with a thriving itch.io and commercial physical-cartridge scene. It **proves the retro/hardware-export niche is real and demanded** — the single best evidence for WorldFoundry's differentiator — though only for one platform, single-author, 2D.

## WorldFoundry's defensible ground — and its weakest flank

**Defensible:** the intersection nobody else holds — **fixed-point deterministic tiny engine (ESP32-class → everywhere) + one-click shippable retro game + VTT authoring + the long tail** that Spline (design) and the heavyweight engines (desktop, AAA) both ignore. GB Studio proves people want retro one-click export; PlayCanvas/Spline/Tabula Sono prove the browser-collab *packaging* is viable. The unique combination is real.

**Weakest flank (state it plainly):** because collaboration is now commoditized across three adjacent products, **the entire moat rests on the export/embedded/retro differentiation — which is unproven at scale.** GB Studio validates *one* platform (Game Boy); the total market for a *general* fixed-point tiny engine, and willingness to pay for it, is unmeasured. If PlayCanvas or Snap ever add a lightweight/embedded target, the differentiated slot narrows fast. The bet is now explicitly on the *engine*, not the *editor*.

## Threat ranking

1. **PlayCanvas** — occupies the generic game-worlds slot; the reference against which "browser collaborative game editing" is judged commodity. Threat is *positioning* (it makes our collab non-novel), not feature-overlap on our differentiators.
2. **Tabula Sono** — the direct VTT-wedge incumbent; already browser + 3D + multiplayer. We differentiate on *authoring* + export, not on "browser 3D VTT."
3. **Spline** — adjacent; a threat only if it ever moves from design into game export (no evidence it will).

## Refuted / thin data / gaps (do not over-read)

- **Refuted:** several specific Spline export-target enumerations (mixed votes) — the general "Spline is design, no game export" holds; the exact integration lists do not. One Spline Series A *participant* list was refuted (the $10M/Aug-2024/Third Point round itself is confirmed).
- **Absence inference (medium):** "PlayCanvas does not do fixed-point/ESP32/retro/VTT" is inferred from its float architecture, not a verified negative — spot-check it.
- **Not covered at all:** Womp, Bezi, Vectary, Gravity Sketch, ShapesXR, Frame/framevr.io, Needle, Hyperfy, Sketchfab, Construct 3, Wonderland, Rogue Engine — the spatial/VR/metaverse and other-browser-tool rows of the map are **gaps**, not confirmed-empty.
- **Not independently verified here:** Roblox Team Create, Unreal Multi-User (though seen in the [previz pass](2026-07-07-a3-previz-validation.md)), Unity's version-control model — treated as installed-desktop by extension from UEFN, not direct evidence.
- **WorldFoundry's own capabilities are assumed,** not verified by this external research (that the fixed-point ESP32 engine and one-click export actually work as described).

## Implications (updates these docs)

- **Sim-env "vacant quadrant" — narrow it again.** It's not "browser + collaborative 3D" that's vacant (PlayCanvas holds it); it's **browser + collaborative + fixed-point/embedded/retro-export + VTT-authoring.** The moat is the *engine combination*, which the doc's own "footprint + determinism = one moat" already argued — so this **confirms the engine-moat thesis and kills the collaboration-as-edge framing.**
- **VTT plan — name Tabula Sono** as the incumbent, and differentiate on authoring + retro export, not "browser 3D VTT."
- **Strategy overall — stop selling collaboration; sell the engine.** The pitch is *"build a tiny game/world together in the browser and ship it to hardware nobody else can reach"* — collab is table-stakes packaging, the fixed-point/everywhere engine is the reason.

## Open questions

1. ~~Does PlayCanvas/Snap have any embedded/tiny/fixed-point roadmap?~~ — **RESOLVED: no** ([2026-07-07 PlayCanvas/Snap embedded-roadmap probe](2026-07-07-playcanvas-snap-embedded-roadmap.md)). PlayCanvas is a GPU-only WebGL/WebGPU engine *doubling down* on the GPU (WebGPU compute), with zero embedded/fixed-point mention; Snap's own hardware runs up-market Snapdragon-XR AR glasses, not microcontrollers. The slot is uncontested from the strongest competitor — the gap is a rewrite, not a feature. (Caveat surfaced: PlayCanvas is *also* ~1–2 MB, so "tiny footprint" isn't the moat — "no GPU, no FPU" is.)
2. **Is there demand for collaborative *building* (not just play)?** Tabula Sono proves play-demand; GB Studio proves single-author retro-export demand; collaborative *authoring* of worlds/tables is still unproven — this is exactly the parallel [demand-validation pass](2026-07-07-game-worlds-vtt-demand.md) (running).
3. **How big/monetizable is the general fixed-point/retro/embedded segment** beyond GB Studio's one-platform proof?
4. **Where do the ~12 uncovered browser/spatial tools sit,** and does any occupy a slice of WorldFoundry's ground?

## Sources

Primary: [PlayCanvas real-time collaboration docs](https://developer.playcanvas.com/user-manual/editor/realtime-collaboration/), [playcanvas.com](https://playcanvas.com/), [PlayCanvas (Wikipedia)](https://en.wikipedia.org/wiki/PlayCanvas), [Snap/PlayCanvas acquisition (Game Developer)](https://www.gamedeveloper.com/game-platforms/snapchat-acquires-cloud-based-engine-playcanvas), Spline funding announcements (Jul 2023 seed / Aug 2024 Series A), GB Studio (gbstudio.dev + itch.io), Tabula Sono site, UEFN docs.
Secondary/flagged: Tracxn (Spline cumulative funding — approximate), competitive trade coverage. Full per-claim votes in the run journal.
