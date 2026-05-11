---
plan: qbert-hop-sfx
date: 2026-05-10
status: Deferred 2026-05-11
scope: ~50 LOC engine (audio API + mailbox handler) + 3 placeholder WAVs + ~3 LOC script writes
---

# Q*bert hop / land / fall sound effects

**Status:** Deferred 2026-05-11 — focus is on enemy AI / cube logic before audio polish; revisit once gameplay loop is closer to arcade-complete.

## Context

Phase 1 + Phase 1.5 + Phase 2 of the Q*bert player polish (rotation, hop arc, stretch-and-squash) all shipped. The character now visibly hops, rotates, and squashes — but the world is silent. miniaudio is initialised and functional ([per memory `project_engine_runnable`](../../../.claude/projects/-home-will-WorldFoundry/memory/project_engine_runnable.md)) and `SoundBuffer::play()` works ([wfsource/source/audio/linux/buffer.cc:62-94](../../wfsource/source/audio/linux/buffer.cc)) — but `EMAILBOX_SOUND` (3017, [mailbox.inc:66](../../wfsource/source/mailbox/mailbox.inc)) has no write-handler today; the comment at [actor.cc:851](../../wfsource/source/game/actor.cc) explicitly notes this is unimplemented.

This plan wires three hop-relevant SFX through that gap:

- **Hop boing** — fires at `do-hop` start (frame 0).
- **Landing thud** — fires on the LANDED-promote frame (cd=2, ~1 frame before exact landing — same anticipation timing as the cube colour flip).
- **Death fall scream** — fires at off-edge fall trigger (mb 419 = 1 set in do-hop's off-edge branch).

Per memory `project_audio_verify`: actual sound needs a different machine to verify (HDMI-only audio on dev box). The wiring is testable via stderr logs from the new handler — verifies plumbing even if the user can't hear it locally.

## What this does NOT do (out of scope)

- **Q*bert "swearing" voice samples** (the iconic Votrax SC-01 vocals) — `assets/arcade-roms/votrsc01a.7z` exists but extraction + WAV conversion is its own plan; placeholder for Phase 2 follow-up.
- **Music** — the `florestan-subset.sf2` MIDI soundfont path exists but is unused by qbert; separate concern.
- **3D positional audio** — using 2D `SoundBuffer::play()` (no spatialization) for Phase 1; positional via `play(x,y,z)` is a trivial follow-up if needed.
- **Asset bundling into the level IFF** — Phase 1 loads WAVs directly from `wflevels/qbert_practice/sfx/` via `HALGetAssetAccessor()`, same path the music loader uses ([music.cc:41-55](../../wfsource/source/audio/linux/music.cc)). IFF-bundled SFX is a future infrastructure plan.
- **ROM-extracted authentic Q*bert sounds** — Phase 1 uses placeholder WAVs (programmatically generated tones with envelopes). Authentic sounds via ROM extraction is a follow-up.

## Approach

### Part A — Engine wiring (~50 LOC)

1. **New file: [wfsource/source/audio/sfx_library.cc/hp](../../wfsource/source/audio/) (~30 LOC)** — a tiny global `std::vector<std::unique_ptr<SoundBuffer>>` indexed by integer ID. API:
   - `SfxLibrary::Load(int id, const char* assetPath)` — opens the asset via `HALGetAssetAccessor()` (mirrors `loadAssetBytes()` at [music.cc:41-55](../../wfsource/source/audio/linux/music.cc)), constructs a `SoundBuffer` from the bytes, stores at `g_sfx[id]`. Logs success/failure to stderr.
   - `SfxLibrary::Play(int id)` — looks up `g_sfx[id]`, calls `->play()` if present, logs which id played to stderr.
2. **Hardcoded SFX init in `Level::Construct()` or game init**: load IDs 0/1/2 from `sfx/qbert_hop.wav`, `sfx/qbert_land.wav`, `sfx/qbert_fall.wav`. Engine boot logs which sounds loaded.
3. **EMAILBOX_SOUND (3017) write handler** in [actor.cc](../../wfsource/source/game/actor.cc) — alongside the other LOCAL_SYSTEM mailbox cases. Calls `SfxLibrary::Play((int)value.WholePart())`. Read-handler returns Scalar::zero (write-only).

### Part B — Placeholder WAV generation (~20 LOC of Python)

Three sounds, ~0.2-0.5s each, mono, 16-bit PCM, 22050 Hz (small files). Generated programmatically via Python `wave` + `struct` module — no external deps. A small `gen_sfx.py` script in `wflevels/qbert_practice/sfx/` produces the WAVs deterministically:

- `qbert_hop.wav` — short rising tone (~150ms): linear sweep 200→400 Hz with quick attack + decay envelope. Cartoon "boing" feel.
- `qbert_land.wav` — short falling tone (~200ms): noise burst + quick low-thump (~80 Hz pulse). Cartoon "thud."
- `qbert_fall.wav` — descending tone (~500ms): downward swept square wave 400→100 Hz, cartoon "Wilhelm-lite" fall scream.

Placeholder fidelity is not the point — verifies the wiring works. Authentic sounds replace the placeholders later.

### Part C — Script consumer (~3 LOC of zForth)

In [blender_create_qbert.py](../../wflevels/qbert_practice/blender_create_qbert.py)'s player wf_Script, three writes:

1. **In `do-hop`'s else branch** (on-pyramid hops only, alongside the `1 434 write-mailbox` PENDING_LAND): `0 3017 write-mailbox` (hop sound).
2. **In the lerp's LANDED promote line** (cd=2, alongside the `mb 434 → mb 411` promotion): `1 3017 write-mailbox` (land sound). Off-edge hops have `mb 434 = 0` so this would write `1` regardless — guard the SFX with `mb 434 != 0` so off-edge doesn't double-fire (the fall sound below covers it).
3. **In `do-hop`'s off-edge branch** (alongside `1 419 write-mailbox` FALL_PHASE start): `2 3017 write-mailbox` (fall sound).

## Critical files

| File | Change |
|---|---|
| [wfsource/source/audio/sfx_library.hp](../../wfsource/source/audio/) | new file — Load/Play API |
| [wfsource/source/audio/sfx_library.cc](../../wfsource/source/audio/) | new file — implementation, global vector storage |
| [wfsource/source/game/actor.cc](../../wfsource/source/game/actor.cc) | add EMAILBOX_SOUND read+write handlers |
| [wfsource/source/game/level.cc](../../wfsource/source/game/level.cc) (or similar) | one-shot init of qbert SFX library at construction |
| [wflevels/qbert_practice/sfx/gen_sfx.py](../../wflevels/qbert_practice/sfx/) | new file — Python WAV generator |
| [wflevels/qbert_practice/sfx/qbert_hop.wav](../../wflevels/qbert_practice/sfx/) | new asset (generated) |
| [wflevels/qbert_practice/sfx/qbert_land.wav](../../wflevels/qbert_practice/sfx/) | new asset (generated) |
| [wflevels/qbert_practice/sfx/qbert_fall.wav](../../wflevels/qbert_practice/sfx/) | new asset (generated) |
| [wflevels/qbert_practice/blender_create_qbert.py](../../wflevels/qbert_practice/blender_create_qbert.py) | 3 mailbox writes in player script |
| `engine/build_game.sh` | add new sfx_library.cc to compile list (or relies on glob-include) |

No new mailboxes (3017 already exists, just unimplemented). No new OAS fields. No `mailbox.inc` changes.

## Existing facts to reuse

- `EMAILBOX_SOUND = 3017` already declared at [mailbox.inc:66](../../wfsource/source/mailbox/mailbox.inc) — handler is unimplemented, see comment at [actor.cc:851](../../wfsource/source/game/actor.cc).
- `SoundBuffer::SoundBuffer(const void* data, unsigned len)` ctor at [audio/buffer.hp:10](../../wfsource/source/audio/buffer.hp) accepts WAV bytes directly (miniaudio decodes via `ma_decoder_init_memory`).
- `SoundBuffer::play()` 2D variant at [audio/linux/buffer.cc:62](../../wfsource/source/audio/linux/buffer.cc) is the right call for non-positional SFX.
- `loadAssetBytes()` pattern at [music.cc:41-55](../../wfsource/source/audio/linux/music.cc) — `HALGetAssetAccessor() → OpenForRead → Size → Read → Close`. Copy this verbatim into sfx_library.cc.
- Existing `0 411 write-mailbox` style mailbox writes throughout the qbert player script — same shape for `0 3017 write-mailbox`.

## Verification

1. **Build clean** with `bash engine/build_game.sh` — new sfx_library.cc compiles.
2. **Generate WAVs**: `python3 wflevels/qbert_practice/sfx/gen_sfx.py`. Verify 3 .wav files appear, each ~5-20 KB, valid WAV header (`xxd` first 44 bytes).
3. **Boot snowgoons**: regression check — no SFX writes anywhere → silent → no SfxLibrary calls → engine boots clean. (SfxLibrary should fail to load qbert SFX silently in non-qbert contexts; logs a warning but doesn't crash.)
4. **Boot qbert**: SfxLibrary loads 3 SFX at level init, stderr logs "audio: loaded sfx[0] = sfx/qbert_hop.wav (N bytes)", etc.
5. **Drive Q*bert through hops**: stderr logs "audio: play sfx[0]" at each hop start, "audio: play sfx[1]" at each landing. Hop off-edge: logs "audio: play sfx[2]" at fall start.
6. **Audio verification on different machine** (per memory `project_audio_verify`): user takes the built binary + assets to an audio-capable machine and confirms the boings, thuds, and falls actually play.

## Out of scope (Phase 2+)

- **Authentic Q*bert SFX from arcade ROM** — `assets/arcade-roms/qbert.zip` likely contains the original samples (the AY-3-8910 sound chip output + Votrax SC-01 voice samples). Extraction needs ROM-archaeology tooling; separate plan.
- **Q*bert swearing on death** — Votrax SC-01 voice samples in `assets/arcade-roms/votrsc01a.7z`. Same extraction problem as above.
- **Music** — qbert arcade had a level-clear jingle and a death fanfare. Out of scope; Phase 2.
- **3D positional audio** — 2D for now; trivial swap to `play(x,y,z)` later if cubes get directional sound.
- **IFF-bundled SFX** — current plan loads WAVs from disk. Future: bundle into the level IFF, load from `binistream`.
- **Volume / pitch / variation per hop** — hops all sound identical. Cycling 3-4 variants or pitch-randomising is a small follow-up.
