# Plan: Super Mario Bros. — World Foundry conversion brief

## Context

The user has a collection of WF (World Foundry) conversion briefs for classic arcade/console games, each stored as a root-level `.md` file in `/home/will/wf-games/`. These briefs describe how to adapt a classic title to the World Foundry engine using zForth scripting, WF mailboxes, OAD actors, and the existing physics/camera/missile systems. Super Mario Bros. is the natural next entry — it shares the platformer DNA of Donkey Kong (already briefed) and would use or slightly extend many of the same primitives.

## Output file

`/home/will/wf-games/super-mario-bros.md`

## Tier assessment

**Tier 2** — small engine additions required:
- Side-scroll camera with left-lock (camera follows Mario rightward but refuses to scroll back left — not native to WF's relative-offset follow cam)
- Variable-height jump (button-hold duration → jump height) — needs button-hold-duration mailbox or a script approximation
- Swim movement mode (new gravity/movement mode; DK and Rampage cover climb, not swim)
- Block-hit-from-below event (or content workaround via upward-velocity trigger volumes under each block)

Everything else — walk, run, jump, enemy path-follow, projectile/missile, trigger volumes, power-up state via mailboxes, pipe warps — is content + Forth.

## Document structure (all standard sections)

1. **Header** — image, original credits (Nintendo 1985, Miyamoto + Tezuka), tier, closest WF fork (`wflevels/mario/` noted in donkey-kong.md), scripting language
2. **How to Play** — NES controls (D-pad, B=run/fire, A=jump), objective (rescue Peach), key mechanics (scrolling, power-ups, enemies, blocks, flagpole, timer), scoring table, sources
3. **Why this conversion fits** — engine alignment, 3D framing of a 2D icon, power-up state machine as pure Forth, scrolling camera as minor engine addition
4. **Level structure (room graph)** — World 1 (W1-1 through W1-4) as first-pass; table maps rooms to original levels; note World 1 covers all core archetypes (overworld, underground, bridge, castle)
5. **Camera** — side-scroll CamShot (Relative X rigid, Relative Y with slight bungee, absolute left-lock); Mermaid diagram; Forth scripts for camera init and castle-room switch
6. **Movement** — Walk, Run (B-hold), Jump (variable-height via A-hold), Crouch, Swim (W1-underwater variant), Pipe entry (teleport/warp)
7. **Power-up state machine** — Small/Super/Fire state via mailboxes; hit from above handling (damage reverts state); invincibility star (timed buff); Forth state machine snippet
8. **Enemy bestiary** — Goomba, Koopa Troopa (+ shell kick), Piranha Plant, Hammer Bro, Bullet Bill, Lakitu+Spinies, Bowser; table format
9. **Combat** — stomp detection (player descending + overlap from above), fireball missile, shell kick chain scoring, Bowser axe trigger
10. **Mailbox protocol** — table of all symbolic indices
11. **Forth scripts** — Player (walk/run/jump/power-up state), Goomba AI, ? Block (hit-from-below → spawn coin/power-up), Koopa shell kick
12. **Engine work required** — side-scroll left-lock camera (~1 wk), variable-height jump (~2 d), swim mode (~1 wk), block-hit-from-below event (~3 d); total ~3 wk standalone, ~1 wk if DK ships first
13. **Verification** — step-by-step W1-1 build + test sequence
14. **Cast / phone integration** — 1P primary, 2P simultaneous (Mario/Luigi split), phone D-pad + A/B buttons; A-hold timing vs. Cast latency caveat
15. **Risks** — 3D framing vs. 2D icon tension, variable-jump feel, camera left-lock edge cases, power-up state hitbox swap

## Key reuse from existing briefs

- Walk/jump ground mode: same as `donkey-kong.md` + `rampage.md`
- Climb mode groundwork: `donkey-kong.md` (not needed for SMB but shows pattern)
- Missile system for fireballs: `paperboy.md`, `donkey-kong.md`
- Rail/path system: `paperboy.md` (not used, but pipe-warp uses WARP_TO_ROOM pattern)
- Trigger volumes for block-hit: `donkey-kong.md` pickup pattern
- Camera Relative follow: all existing briefs

## Critical files to consult

- `/home/will/wf-games/donkey-kong.md` — closest platformer brief; reuse movement section structure verbatim
- `/home/will/wf-games/paperboy.md` — missile system, Forth scripting patterns
- `/home/will/wf-games/donkey-kong/audio-anim-hud.md` — companion doc format (separate file needed?)
- `/home/will/wf-games/README.md` — check where SMB fits in the dependency graph (may need updating)

## Companion file

Following the pattern of `donkey-kong/audio-anim-hud.md`, create:
`/home/will/wf-games/super-mario-bros/audio-anim-hud.md`

This covers: HUD (score, coins, world/level, time, lives), music tracks (overworld, underground, castle, star, death, game over, etc.), SFX list, animation tables (Small Mario, Super Mario, Fire Mario, enemies).

## Verification plan

The brief itself describes the test sequence. No code to run — this is a design document.
