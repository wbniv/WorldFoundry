# Plan — Q*bert ROM-extracted SFX (deferred)

**Date:** 2026-05-10 (deferred 2026-05-11 by user request)
**Status:** Deferred — user paused audio work entirely; plan retained for the eventual return.
**Scope:** Two-part. Part A is ROM extraction tooling (Lua + bash + ffmpeg). Part B is engine wiring (~50 LOC C++ + 3 LOC zForth).

## Context

User wants authentic Q*bert SFX (hop, land, fall, plus the iconic Votrax "swearing" voice on death) instead of synthesized placeholders or soundfont-rendered MIDI notes. We have:

- MAME 0.264 at `/usr/games/mame` (Lua scripting + `-wavwrite` for full-mixer audio capture)
- `assets/arcade-roms/qbert.zip` (25 KB main + sound ROMs — 6502 main CPU + 6502 audio CPU + AY-3-8910 chip)
- `assets/arcade-roms/votrsc01a.7z` (598 B Votrax SC-01 phoneme ROM)
- 32 existing Lua scripts in `scripts/research/mame/` (palette/state hunters; `qbert_bot.lua` is a proven gameplay automation, ~452 LOC) — none capture audio yet
- `EMAILBOX_SOUND` slot (3017, [mailbox.inc:66](/home/will/WorldFoundry.2026-new-level/wfsource/source/mailbox/mailbox.inc)) declared but with the unimplemented stub at [actor.cc:851](/home/will/WorldFoundry.2026-new-level/wfsource/source/game/actor.cc)
- The miniaudio backend at [audio/linux/buffer.cc:62](/home/will/WorldFoundry.2026-new-level/wfsource/source/audio/linux/buffer.cc) decodes WAV bytes via `ma_decoder_init_memory` — drop-in for the extracted WAVs

This plan supersedes the synthesized-placeholder version of [docs/plans/2026-05-10-qbert-hop-sfx.md](/home/will/WorldFoundry.2026-new-level/docs/plans/2026-05-10-qbert-hop-sfx.md). Files I already wrote during the wrong-turn detour (will be deleted before Part A starts):

- `wflevels/qbert_practice/sfx/gen_sfx.py` (Python WAV generator) — DELETE
- `wflevels/qbert_practice/sfx/qbert_hop.wav` / `qbert_land.wav` / `qbert_fall.wav` — DELETE (replaced by ROM-extracted versions)
- The plan doc itself will be rewritten in-place with the new approach.

Q*bert sound architecture: main 6502 CPU writes a 1-byte sound command to a latch register; sound 6502 picks it up and drives the AY chip + Votrax SC-01. Each command (`0x01`, `0x02`, etc.) maps to a discrete effect — hop, land, swear-on-death, etc. We don't need to reverse-engineer the command table; we just trigger gameplay events and capture the resulting audio.

## Approach

### Part A — ROM extraction tooling

A tiny new Lua script under `scripts/research/mame/`, plus a bash driver and an ffmpeg post-process step.

**A.1.** New file `scripts/research/mame/qbert_capture_audio.lua` (~80 LOC):
- Boots qbert in MAME with `-wavwrite` capturing the full session.
- Logs sound-command writes (Lua mem hook on the audio-command latch register address — exact address found via MAME's `qbert.cpp` driver source / disassembly, or by trial: hooking on every write to the audio CPU's I/O space and filtering for byte commands during known events).
- Drives the bot through scripted actions in known order with known frame gaps:
  - frame 0: idle on apex (silence — gives a clean "no SFX" baseline)
  - frame N: trigger a single hop (records the hop SFX)
  - frame N+M: another hop landing on a fresh cube (records land)
  - frame N+M+K: deliberate hop-off-edge (records fall + Votrax swear)
- Outputs a sidecar CSV `scripts/research/mame/qbert_audio_events.csv` with `frame,sample_offset,event_label` so the post-process step knows where to slice the WAV.

**A.2.** New file `scripts/research/mame/extract_sfx.sh` (~30 LOC):
- Runs MAME headless: `/usr/games/mame qbert -rompath ... -script qbert_capture_audio.lua -wavwrite /tmp/qbert_session.wav -window 0 -seconds_to_run 30 -nothrottle`
- Reads the events CSV, computes WAV byte offsets per event from MAME's sample rate (typically 48 kHz).
- Calls `ffmpeg -ss <start> -to <end> -i /tmp/qbert_session.wav -c:a pcm_s16le -ar 22050 -ac 1 wflevels/qbert_practice/sfx/qbert_<event>.wav` for each event.
- Outputs final WAVs to `wflevels/qbert_practice/sfx/qbert_hop.wav`, `qbert_land.wav`, `qbert_fall.wav`, `qbert_swear.wav`.
- Prints a checksum + duration summary so the user can sanity-check.

**A.3.** Commit the extracted WAVs alongside the extraction script. Per project policy (see [project_rom_extraction_copyright](/home/will/.claude/projects/-home-will-WorldFoundry/memory/project_rom_extraction_copyright.md)): re-encoding from chip-register / phoneme-stream representations into PCM WAV constitutes a new artefact, not a derivative work — the encoding technique is fundamentally different from the original. No `.gitignore` entry; check the WAVs in.

**A.4.** New file `wflevels/qbert_practice/sfx/README.md` — documents the ROM source and the extraction script command. No legal-posture caveats needed (covered by the project memory entry).

### Part B — Engine wiring (~50 LOC)

Identical to the prior synthesized plan, just point at the new WAVs.

**B.1.** New `wfsource/source/audio/sfx_library.{hp,cc}` (~30 LOC):
- Global `std::vector<std::unique_ptr<SoundBuffer>> g_sfx`.
- `SfxLibrary::Load(int id, const char* assetPath)` — opens via `HALGetAssetAccessor()` (mirroring [music.cc:41-55](/home/will/WorldFoundry.2026-new-level/wfsource/source/audio/linux/music.cc) `loadAssetBytes`), constructs `SoundBuffer` from the WAV bytes, slots in at `g_sfx[id]`. Logs success / "missing file" / "decoder failed" to stderr.
- `SfxLibrary::Play(int id)` — bounds-check, valid-ptr check, call `->play()`. Logs play attempt.

**B.2.** Add `EMAILBOX_SOUND` (3017) write handler in [actor.cc](/home/will/WorldFoundry.2026-new-level/wfsource/source/game/actor.cc) (alongside the existing FACE_COLOR / X_SCALE handlers). Calls `SfxLibrary::Play((int)value.WholePart())`. Read-handler returns `Scalar::zero` (write-only).

**B.3.** One-shot SFX init at level construction (in `Level` ctor, or in main game init): load IDs 0/1/2/3 from `wflevels/qbert_practice/sfx/qbert_{hop,land,fall,swear}.wav`. Init runs once; missing files (e.g. user hasn't run extract_sfx.sh yet) log a warning but don't crash — the game just runs silent for those IDs.

**B.4.** Build hookup: add `sfx_library.cc` to `engine/build_game.sh`'s compile list (or rely on its glob-include if there is one — needs to verify).

### Part C — Script consumer (~3 LOC of zForth)

In [blender_create_qbert.py](/home/will/WorldFoundry.2026-new-level/wflevels/qbert_practice/blender_create_qbert.py)'s player wf_Script:

1. **`do-hop`'s on-pyramid else branch** (alongside the `1 434 write-mailbox` PENDING_LAND): `0 3017 write-mailbox` (hop sound).
2. **Lerp's LANDED promote line** (cd=2, alongside the `mb 434 → mb 411` promotion): `1 3017 write-mailbox` if `mb 434 != 0` (land sound only on on-pyramid landings; off-edge writes 0 to the slot which the SfxLibrary handler treats as "no-op").
3. **`do-hop`'s off-edge branch** (alongside `1 419 write-mailbox` FALL_PHASE start): `2 3017 write-mailbox` (fall sound).
4. **Fall-completion → death** (in the FALL_PHASE state machine, where `1 414 write-mailbox` latches FALL_DEATH): `3 3017 write-mailbox` (swear sound).

## Critical files

| File | Change |
|---|---|
| `scripts/research/mame/qbert_capture_audio.lua` | NEW — bot + sound-command logger + event CSV |
| `scripts/research/mame/extract_sfx.sh` | NEW — MAME launcher + ffmpeg post-process |
| `wflevels/qbert_practice/sfx/README.md` | NEW — extraction instructions + legal note |
| `wflevels/qbert_practice/sfx/qbert_hop.wav` (and `qbert_land.wav`, `qbert_fall.wav`, `qbert_swear.wav`) | COMMITTED — new artefacts per project ROM-extraction policy. |
| `wfsource/source/audio/sfx_library.hp` | NEW — Load/Play API |
| `wfsource/source/audio/sfx_library.cc` | NEW — implementation |
| [wfsource/source/game/actor.cc](/home/will/WorldFoundry.2026-new-level/wfsource/source/game/actor.cc) | EMAILBOX_SOUND read+write handlers (~10 LOC) |
| [wfsource/source/game/level.cc](/home/will/WorldFoundry.2026-new-level/wfsource/source/game/level.cc) | one-shot SFX library init at level load (~5 LOC) |
| [wflevels/qbert_practice/blender_create_qbert.py](/home/will/WorldFoundry.2026-new-level/wflevels/qbert_practice/blender_create_qbert.py) | 4 mailbox writes in player script (hop/land/fall/swear) |
| `engine/build_game.sh` | add `sfx_library.cc` to compile list |
| [docs/plans/2026-05-10-qbert-hop-sfx.md](/home/will/WorldFoundry.2026-new-level/docs/plans/2026-05-10-qbert-hop-sfx.md) | rewrite to match this approach |
| `wflevels/qbert_practice/sfx/gen_sfx.py` (and 3 .wav files) | DELETE — vestigial from the placeholder detour |

No new mailboxes (3017 already exists). No new OAS fields. No `mailbox.inc` changes.

## Existing facts to reuse

- `EMAILBOX_SOUND = 3017` already declared at [mailbox.inc:66](/home/will/WorldFoundry.2026-new-level/wfsource/source/mailbox/mailbox.inc); handler stub at [actor.cc:851](/home/will/WorldFoundry.2026-new-level/wfsource/source/game/actor.cc).
- `SoundBuffer::SoundBuffer(const void* data, unsigned len)` at [audio/buffer.hp:10](/home/will/WorldFoundry.2026-new-level/wfsource/source/audio/buffer.hp) accepts WAV bytes directly.
- `SoundBuffer::play()` 2D variant at [audio/linux/buffer.cc:62](/home/will/WorldFoundry.2026-new-level/wfsource/source/audio/linux/buffer.cc) for non-positional one-shots.
- `loadAssetBytes()` pattern at [music.cc:41-55](/home/will/WorldFoundry.2026-new-level/wfsource/source/audio/linux/music.cc) — `HALGetAssetAccessor() → OpenForRead → Size → Read → Close`. Lift verbatim into sfx_library.cc.
- `qbert_bot.lua` proven gameplay automation in `scripts/research/mame/`; the new `qbert_capture_audio.lua` can either fork or `dofile` it.
- MAME `-wavwrite` and `-script` options confirmed in MAME 0.264.

## Verification

1. **Extract**: run `bash scripts/research/mame/extract_sfx.sh`. Verify 4 WAV files appear in `wflevels/qbert_practice/sfx/`, each ≥1 KB and ≤500 KB, valid WAV headers (`xxd | head`).
2. **Listen** (on an audio-capable machine, per memory `project_audio_verify` — dev box is HDMI-only): play each WAV in `paplay` / `aplay` / `mpv`. Confirm hop sounds like a "boing", land like a thud, fall like a descending tone, swear like the iconic Votrax "@!#?@!".
3. **Engine builds clean** with `bash engine/build_game.sh` after Part B edits.
4. **Snowgoons regression**: boot snowgoons standalone → no scale or sound mailbox writes → SfxLibrary may log "missing qbert sfx" warnings (acceptable) but engine renders + plays normally.
5. **qbert engine smoke**: boot qbert standalone → SfxLibrary logs `loaded sfx[0..3]` for hop/land/fall/swear at level init.
6. **qbert script smoke**: drive Q*bert through hops → stderr logs `play sfx[0]` per hop, `play sfx[1]` per landing, `play sfx[2]` on off-edge, `play sfx[3]` on fall-completion.
7. **Audio verification on a different machine** — actual sound playback. Hop boings, landing thuds, fall scream, and swear-on-death all heard.

## Out of scope

- **Per-event MAME hook for command isolation** — Approach (a) (fork MAME, add sound-command iterator) is more rigorous but heavier. Approach (c) (gameplay-driven capture + post-process slice) gets the same WAVs at far lower complexity. If a future plan needs *every* sound command iterated rather than just the 4 we trigger, that's a follow-up.
- **Per-chip isolation** — `-wavwrite` captures the mixed final output; AY chip + Votrax come out together. Fine for our SFX (each effect uses one chip at a time anyway).
- **IFF-bundled SFX** — Phase 1 loads loose `.wav` files via HAL. Bundling into the level IFF for distribution is a separate plan.
- **Asset distribution** — extracted WAVs are committed (per project policy: PCM WAV re-encoding is a new artefact, not a derivative work). Other devs build from the same WAVs without needing their own ROM copy; the extraction script is committed for archival / re-extraction if the trigger commands need to change.
- **Music** — qbert had a level-clear jingle and a death fanfare. Stretch goal; not in this plan.
- **Per-hop sound variation** — every hop sounds identical here. Cycling through 3-4 captured variants or pitch-randomising is a small follow-up.
- **3D positional audio** — using 2D `SoundBuffer::play()` for now; trivial swap to `play(x,y,z)` later.
