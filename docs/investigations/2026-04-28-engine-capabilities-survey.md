# Investigation: World Foundry engine capabilities — what the engine is built for

**Date:** 2026-04-28
**Status:** **Snapshot** — descriptive, not normative. Captures what the engine does on `party-games-platform` HEAD; new genres are routinely added.
**Depends on:** `docs/scripting-languages.md`, `docs/investigations/2026-04-14-jolt-physics-integration.md`, `docs/investigations/2026-04-19-snowgoons-build-pipeline.md`

## Context

This survey was prompted by a question about which 1980s arcade/console games would make good conversions to World Foundry 3D. To answer that grounded in the engine's actual shape (rather than nostalgia), this document characterises what WF is, what it natively supports today, and what would have to be added for genres outside its current sweet spot. The user has been explicit that conversions are not constrained to today's capabilities — engine work happens to enable level work — so the framing here is "current strengths vs. what each genre would require," not "what's already possible."

Findings come from reading `wfsource/source/` directory layout, `docs/scripting-languages.md`, the existing investigation set, and a top-level survey of `wflevels/`. Specific numeric claims (object counts, mailbox slot counts, binary sizes) are sourced from the docs cited above; this file does not re-measure them.

## Engine profile

World Foundry is a **third-person 3D action/platformer engine**, room-structured, with a heavily script-driven actor model bridged to the engine through a single shared mailbox bus. The closest mainstream comparison is the late-90s/early-2000s collectathon platformer (Banjo, Mario 64, Spyro), not a modern engine framework like Unity or Unreal — WF is opinionated toward its existing genre, with most non-platformer genres requiring new subsystems rather than new content.

### Verified subsystems (`wfsource/source/` directories)

`anim`, `asset`, `audio`, `baseobject`, `eval`, `game`, `gfx`, `hal`, `iff`, `input`, `mailbox`, `math`, `memory`, `movement`, `oas`, `particle`, `physics`, `pigsys`, `renderassets`, `room`, `scripting`, `streams`, `timer`.

The directory list alone is informative: physics + movement are first-class peers, scripting is a top-level subsystem (not a plugin), `oas` and `pigsys` reflect the engine's IFF-based asset system, and `room` confirms the room-graph world model rather than open-world streaming.

### Native gameplay primitives (today)

- **Character control**: walk, run, jump, crawl, fall, stun/knockdown, hitpoints. Ground/air/falling have separate physics parameters. Jolt's `CharacterVirtual` handles slopes, steps, snap-to-ground (per `2026-04-14-jolt-physics-integration.md`).
- **World structure**: room graph; actors move between rooms. Levels are typically tens of game objects (see snowgoons in `2026-04-19-snowgoons-build-pipeline.md`).
- **Movement on rails**: path-following with ping-pong, stop, jumpback, delete, derail, warp-back endpoints. This is the system that backs the existing `minecart` level.
- **Camera**: multiple `CamShot` objects per level; `BungeeCameraHandler` follow camera; per-frame camera switching via mailbox writes (the script-side Director pattern shown in `docs/scripting-languages.md`).
- **Projectiles**: missiles with arming delay, impact explosion, configurable timing. *Not* a general weapon system — no aiming reticle, ammo model, or hitscan.
- **Audio**: per-level MIDI music; fire-and-forget 3D-positional SFX. (See `docs/investigations/2026-04-14-audio-sound-music.md`.)
- **Inter-actor messaging**: mailbox bus (thousands of slots) — every cross-actor signal goes through it. Scripts only ever read/write mailboxes; the engine reacts.
- **Scripting**: Lua 5.4 (primary), Fennel (compiles to Lua), JavaScript (QuickJS or JerryScript — pick one), WebAssembly (WAMR; thus AssemblyScript / Rust / C / C++ / Zig / TinyGo as source languages), Forth (six interchangeable backends: zForth, ficl, Atlast, embed, libforth, pForth), Wren. Multi-tick scripts via Lua coroutines, JS generators, Wren fibers; Forth and JerryScript are single-tick. Each language is independently selectable at compile time; scriptless builds are valid.

### Existing levels (suggest the genre fit, not a hard limit)

`wflevels/` contains directories for: `3dtext`, `aquarium`, `babylon5`, `back`, `basic`, `bubba`, `car`, `clock`, `cube`, `cubemenu`, `cyber`, `cyberthug`, `dominoes`, `kinder`, `main_game`, `mario`, `menu`, `minecart`, `oad`, `old babylon5`, `oldprimitives`, `parallax`, `physics`, `primitives`, `scripts`, `snowgoons-blender`, `streetback`, `streets`, `test`, `whitestar`. Several are infrastructure (`menu`, `cubemenu`, `3dtext`, `primitives`, `test`); the gameplay-shaped ones lean platformer/action-adventure (`snowgoons-blender`, `cyberthug`, `bubba`, `kinder`, `babylon5`, `whitestar`) with vehicle-flavoured exceptions (`car`, `minecart`) and one named after a famous platformer (`mario`). The presence of `dominoes`, `aquarium`, `clock` hints the engine has been used for non-action setpieces too — physics toys, ambient scenes, mechanical demos.

### Things the engine does not natively do (today)

These are not condemnations — each is a known-shape engine project, not a research problem. Listed because they shape conversion difficulty.

- **First-person camera rig**: bungee follow camera is third-person. FPS / Wolfenstein-style games would need a head-mounted camera, mouselook input, and a forward weapon mount. None of those are deep — they're a few weeks of focused work — but they don't exist yet.
- **Vehicle physics**: no wheeled-vehicle controller (Jolt has `VehicleConstraint` but WF doesn't use it yet). Anything car/bike/tank would need this.
- **Hitscan or aimable ranged combat**: missiles exist but there is no aiming/reticle/ammo system. Shooters and gallery games would need one.
- **2D / orthographic gameplay framing**: the engine is fundamentally 3D. A faithful 2D-feel game (single-screen arcade, side-scroller) is achievable via a fixed orthographic camera + locked-axis movement, but nothing in `wflevels/` does this today.
- **Grid / turn-based logic**: no tile grid, no turn manager. Buildable in scripts, but from scratch.
- **Networking / multiplayer**: see `docs/investigations/2026-04-14-multiplayer-voice-mobile-input.md` — exploratory, not landed.
- **AI / pathfinding**: enemies have movement and physics, but there is no nav-mesh or A* in-tree that I observed. Scripted patrols and triggered behaviours, yes; emergent navigation, no.

### Platforms

PC (Linux primary, plus the historical Windows/Mac targets), Android (APK builds), iOS (Metal port in progress per the iOS port notes in the broader doc set). Mobile-readiness puts a soft ceiling on per-frame budget for new gameplay systems.

## How to use this document

When evaluating any candidate level / game / conversion, the relevant questions are:

1. **Camera** — is third-person bungee-follow appropriate, or does the genre demand first-person, top-down, or fixed-orthographic?
2. **Movement** — does the player walk/jump/crawl, or do we need to write a new movement type (vehicle, swim, fly, ski, grapple)?
3. **Combat** — none, missile-only, melee/collision-only, or aimed-ranged? Aimed-ranged is the biggest single gap.
4. **World structure** — does the room graph fit, or is the game one continuous level / open world / single screen?
5. **Scripting fit** — can the gameplay logic live entirely in mailbox-driven actor scripts, or does it need new engine-side systems (turn manager, grid, nav-mesh, etc.)?

A genre clearing all five with "yes, native" is a content-only project. Each "no" is roughly one engine subsystem of work.

## Follow-ups

- This file is a snapshot. Re-survey after any of: a vehicle controller lands; a first-person camera rig lands; an aimable weapon system lands; nav-mesh pathfinding lands. Each of those would substantially expand the natively-supported genre set.
- The companion brainstorm — which 1980s games are good conversion candidates given this profile — is intentionally kept in the conversation/PR description rather than committed as a doc, because it's a creative shortlist, not load-bearing engine reference.
