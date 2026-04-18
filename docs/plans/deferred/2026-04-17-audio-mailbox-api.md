# Plan: Mailbox-wired audio API (music + SFX)

**Date:** 2026-04-17
**Status:** Deferred

## Context

Audio Phases 1–5 are complete: miniaudio is the backend, MIDI music streams
per-level, `SoundBuffer::play()` one-shots are audible, and positional SFX
pan correctly via the camera-driven listener (`d1e913d`). But the scripting
surface is **Lua-only**: `play_music` / `stop_music` / `set_music_volume` are
C closures registered in `engine/stubs/scripting_lua.cc`. The other seven
scripting engines (Fennel, QuickJS, JerryScript, WAMR, Wren, zForth, and the
five alternate Forth backends) cannot trigger any audio. And SFX are not
scriptable at all — actors fire `_sfx[index]->play()` internally, but there
is no mailbox or closure for scripts to play a sound.

Mailboxes are the cross-engine scripting primitive: every engine can read
and write them with a uniform pair of verbs. Wiring audio into the mailbox
surface is what Phase 4 of the original audio plan
(`docs/investigations/2026-04-14-audio-sound-music.md`) called for before
shipping as a Lua-only stopgap.

The engine originally had exactly this integration. It was deleted on
2026-04-14 as part of the dead-code sweep (commit `460a3fd` — "remove audio
subsystem (was entirely stubbed on Linux)"). The deletion was correct at
the time: the audio impl was a DirectSound Win32 leftover with empty Linux
stubs, so the mailbox write fanned out to a no-op. With miniaudio now in
place, the upstream plumbing can be restored on top of a real backend.

Two encouraging findings survey the damage:

- The **mailbox enum constants still exist**:
  `wfsource/source/mailbox/mailbox.inc` lines 16/47/61/65 still declare
  `MAILBOXENTRY(MIDI, 1002)`, `(LOCAL_MIDI, 3003)`, `(SOUND, 3017)`,
  `(CD_TRACK, 3021)`. The names `EMAILBOX_SOUND`, `EMAILBOX_MIDI`, etc.
  already resolve. Nothing reads them today (only `EMAILBOX_CD_TRACK` has
  a case, and it's an empty no-op at `actor.cc:1338`).
- The **OAD asset table fields still exist**:
  `wfsource/source/oas/levelobj.oas` declares `sfx0 … sfx127` with
  `TYPEENTRYFILENAME(..., "Windows Sound File (*.wav)\0*.wav\0")`. Levels
  that were authored against this layout still carry the pointers in
  `levelobj.ht`; they just aren't loaded.

So the wires for SFX are already pulled through the wall on both ends —
data format and mailbox enum. What's missing is the level-side loader and
the handler inside `WriteMailbox`.

## Goal

Every scripting engine can trigger music and SFX by writing a mailbox. The
existing Lua C closures become thin wrappers over those mailbox writes (so
the Lua surface keeps working unchanged) and the seven other engines reach
parity automatically.

## Design

### SFX

Re-introduce the 128-slot SFX table per level, loaded from the existing
`_levelOad->sfx0 … sfx127` asset IDs. On level load, for every non-zero
slot, decode the WAV into a `SoundBuffer` via `SoundDevice::createBuffer()`
(reusing the current `buffer.hp` surface). Slots stay valid for the
lifetime of the level; freed with the level.

Scripts play a sound by writing the slot index to `EMAILBOX_SOUND` (3017).
Because mailbox writes happen on an actor, the handler has the actor's
transform in hand and plays the SFX **positionally** at the actor's world
position via `SoundBuffer::play(x, y, z)`. The listener is already driven
from the camera in `Level::updateSound()`, so the panning is free.

Special case: if the actor doesn't have a valid position (e.g., the level
shell itself), fall back to `SoundBuffer::play()` — non-positional.

Range-check the slot (0..127) and fail gracefully on an empty slot with a
warning in debug builds only (production must not crash a script run).

### Music

Three mailboxes for symmetry with the current Lua closures:

| Mailbox | Value | Action |
|---------|-------|--------|
| `EMAILBOX_MUSIC_PLAY`   | int: string-table index (see below) | `gMusicPlayer->play(name)` |
| `EMAILBOX_MUSIC_STOP`   | any (ignored)                        | `gMusicPlayer->stop()`     |
| `EMAILBOX_MUSIC_VOLUME` | Scalar (0.0–1.0)                     | `gMusicPlayer->setVolume(v)` |

These are **new** enum entries (not the existing `EMAILBOX_MIDI` /
`EMAILBOX_LOCAL_MIDI`, which carry PSX-era semantics that don't match).
Pick values in the existing 3xxx global-write range. `EMAILBOX_CD_TRACK`
and `EMAILBOX_MIDI` can be retired in the same pass — they're no-ops today
and the names leak PSX assumptions.

Music track names come from a per-level string table. The engine doesn't
currently have a level-scope string table, so the first cut uses a small
hardcoded constant table: `MUSIC_0`, `MUSIC_1` map to `level0.mid`,
`level1.mid`, etc. (The per-level music loader already uses this naming
convention — `game.cc:262`.) A future iteration can add a real
`MNAM`-style IFF chunk with named strings, matching how SFX slots work.

### Retire the Lua-only path

After the mailbox handlers are in place, rewrite the three Lua closures
in `engine/stubs/scripting_lua.cc` to be thin forwarders that do mailbox
writes instead of direct `gMusicPlayer` calls. That keeps the Lua surface
source-compatible for any scripts already using it, while routing
everything through the cross-engine path so nothing drifts.

Optionally, delete the closures outright and rely on the mailbox primitive
Lua scripts already have (via the ScriptRouter). The Lua-specific sugar is
nice but adds a maintenance axis that none of the other seven engines will
benefit from. Decision deferred to implementation — first pass keeps the
sugar.

## Phases

### Phase A — SFX slot loading and `EMAILBOX_SOUND`

1. Add `SoundBuffer* _sfx[128]` back to `Level` in `level.hp`, with
   construction/destruction in `level.cc` mirroring the pre-`460a3fd`
   loader: iterate `_levelOad->sfx0..sfx127`, call
   `GetAssetManager().GetAssetStream(slotN)`, decode into `SoundBuffer`.
   Null out empty slots.
2. Add `SoundDevice::createBufferFromStream(binistream&)` (or the
   equivalent on the current miniaudio `buffer.hp` API) if it doesn't
   already exist in a form that takes an asset stream.
3. Handle `case EMAILBOX_SOUND:` in `actor.cc::WriteMailbox`: range-check,
   nullptr-check the slot, and call either `_sfx[i]->play(actor_pos)` (if
   the actor has a position) or `_sfx[i]->play()`.
4. Delete the empty `case EMAILBOX_CD_TRACK:` handler and remove the enum
   entry from `mailbox.inc` — it's lied about being wired for years.
5. **Verify:** pick a level that has at least one SFX slot populated
   (snowgoons sfx0 likely exists as leftover data). Write a one-line
   script in Forth — `3017 0 actor-write-mailbox` — and confirm the beep
   plays positioned at the actor.

### Phase B — Music mailboxes

1. Add three `MAILBOXENTRY` lines in `mailbox.inc`:
   `MUSIC_PLAY`, `MUSIC_STOP`, `MUSIC_VOLUME`.
2. For `MUSIC_PLAY`: hardcode the small integer→filename table
   (`level%d.mid`) for the first cut. Document the future `MNAM`
   extension point.
3. Handle the three new cases in `WriteMailbox`. Call the existing
   `gMusicPlayer` methods verbatim — this is a fanout, not new logic.
4. Rewrite the three Lua closures in `scripting_lua.cc` to be mailbox-
   write forwarders. Confirm existing Lua scripts still play music.
5. **Verify:** smoke-test from Forth, Wren, and one JS engine — in each,
   write `MUSIC_PLAY` with value 0, hear Für Elise; write `MUSIC_STOP`,
   music stops; write `MUSIC_VOLUME` with 0.25, volume drops.

### Phase C — Named SFX constants (optional)

The original plan wanted `SFX_<name>` integer constants so scripts can
refer to slots by name instead of magic numbers. The engine has an
`IntArrayEntry` mechanism that the mailbox names already use. Register
one slot per `SFX_<name>` constant, driven from a new
per-level string table. **Defer** unless snowgoons' script surface starts
needing it — a 128-entry integer slot is a fine interim API.

## Critical files

| File | Change |
|------|--------|
| `wfsource/source/mailbox/mailbox.inc` | Add `MUSIC_PLAY`/`MUSIC_STOP`/`MUSIC_VOLUME`; remove `CD_TRACK`. |
| `wfsource/source/game/level.hp` | `SoundBuffer* _sfx[128]` member. |
| `wfsource/source/game/level.cc` | Load SFX slots from `_levelOad->sfx0..sfx127` on level init; free on teardown. |
| `wfsource/source/game/actor.cc` | New `EMAILBOX_SOUND` / `EMAILBOX_MUSIC_*` cases in `WriteMailbox`; delete `EMAILBOX_CD_TRACK` case. |
| `wfsource/source/audio/buffer.hp` | Confirm `SoundBuffer` can be constructed from an asset stream (or add an overload). |
| `wfsource/source/audio/linux/buffer.cc` | Stream-based constructor implementation. |
| `engine/stubs/scripting_lua.cc` | Rewrite `lua_play_music` / `lua_stop_music` / `lua_set_music_volume` as mailbox-write forwarders. |

## Reuses

- `SoundBuffer::play()` and `SoundBuffer::play(x, y, z)` — current
  miniaudio backend, unchanged (`wfsource/source/audio/buffer.hp`).
- `MusicPlayer::play(name)` / `stop()` / `setVolume(v)` — current MIDI
  backend, unchanged (`wfsource/source/audio/music.hp`).
- `GetAssetManager().GetAssetStream(packedAssetID)` — existing asset
  stream loader that already serves the rest of the level.
- Mailbox dispatch in `actor.cc::WriteMailbox` — already a `switch` over
  `EMAILBOX_*`; we add cases to a pattern that handles 30+ today.
- OAD `sfx0..sfx127` fields in `levelobj.oas` — already declared, already
  carry data in existing levels.

## Verification

- **Phase A, end of:** Forth script `3017 0 actor-write-mailbox` plays a
  sound positioned at the actor's world space. The old `EMAILBOX_SOUND`
  integration path is alive again, with positional audio as a free
  upgrade thanks to the Phase 5 listener tracking.
- **Phase B, end of:** A Lua script calling `play_music(0)` still works
  (sugar intact). A Forth script writing `MUSIC_PLAY = 0` also plays
  Für Elise. Wren and QuickJS parity confirmed.
- **Phase C, if landed:** `SFX_BEEP` resolves to a slot index the same
  way `INDEXOF_PLAYER` resolves to an actor slot. Script parity held.

## Not in scope

- HRTF / reverb / occlusion. Phase 5 follow-ups in the audio investigation.
- Per-slot metadata (min/max distance, loop flag, bus routing). Requires
  a new `SFXM`-style IFF chunk; design deferred.
- Voice chat ([multiplayer/voice/mobile-input investigation](../../investigations/2026-04-14-multiplayer-voice-mobile-input.md)), dynamic music stems, beat-synced gameplay. Separate plans.
- Retuning the mailbox enum numbering. Stability of the mailbox IDs
  matters for compiled scripts; keep `EMAILBOX_SOUND = 3017` as-is and
  pick new values in the neighbouring range for the music triplet.

## Risks and gotchas

- **Compiled scripts may already encode `EMAILBOX_SOUND = 3017`.** That's
  fine — we're restoring the handler, not moving the number. The only
  observable change is that the write stops being a no-op.
- **Empty SFX slots must not crash.** `actor.cc` pre-cleanup used
  `AssertMsg` which would abort debug builds; use a warning-and-return
  path so a script reading stale data can't brick a run.
- **Level load time may grow.** 128 slots × WAV decode per level adds up.
  miniaudio decodes on play by default (streaming), so level load just
  copies bytes — fine. Don't pre-decode.
- **OAD compat.** The `sfx0..sfx127` fields are already present; nothing
  new to add on the OAD side for Phase A. The music mailboxes don't
  require an OAD change either until Phase C / `MNAM` lands.
