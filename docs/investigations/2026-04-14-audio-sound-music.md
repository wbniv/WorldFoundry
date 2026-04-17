# Investigation: Audio — sound effects, music, positional sound

**Date:** 2026-04-14
**Status:** Active — Phase 0 complete; Phase 1 next.
**Related:** `docs/investigations/2026-04-14-mobile-port-android-ios.md` (mobile backends), `docs/investigations/2026-04-14-jolt-physics-integration.md` (actor position source for 3D audio).

## Context

WF ships with the *skeleton* of an audio system but no working implementation on Linux:

- `wfsource/source/audio/device.hp` / `buffer.hp` — `SoundDevice` / `SoundBuffer` classes.
- `wfsource/source/audio/linux/device.cc` / `buffer.cc` — **stubs**. `SoundBuffer::play()` is empty.
- `wfsource/source/audio/orig.cc` — the original DirectSound-backed implementation (PSX/PC heritage) preserved as reference.
- `wfsource/source/audiofmt/` — vendored `sox` (1990s) format converters: WAV, AIFF, 8SVX, VOC, AU, hcom, maud, resampler. Builds but is not wired up.
- `wfsource/source/game/level.cc:610` loads `_sfx[128]` via `SoundDevice::CreateSoundBuffer(binis)` per-level.
- `wfsource/source/game/actor.cc:1342` calls `theLevel->_sfx[soundEffect]->play()` — the one existing SFX hook.

There is no music subsystem at all. No mixer, no streaming, no 3D panning, no occlusion, no volume control, no pause-on-focus-loss. Snowgoons is silent.

Intended outcome: `wf_game` produces sound. Actors' existing `play(soundEffect)` calls emit audible one-shots; a level's music track plays in the background; 3D-positioned SFX pan relative to the camera; scripts can trigger sounds via mailbox writes. All of this ships with a vendored, statically linked audio stack — no system package dependency (same rule we applied to Lua and wasm3).

## Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Backend library | **miniaudio** (single-header, MIT, ~30 KLoC) | Covers playback + 3D spatialization + decoding (WAV/FLAC/MP3/Vorbis) in one TU. No system deps on Linux/Android/iOS/macOS/Windows. Vendors cleanly alongside wasm3/quickjs/lua. |
| 3D spatialization | **miniaudio's built-in `ma_sound_set_position`** (HRTF optional, vector-pan default) | Zero additional code. HRTF adds ~40 KB for the IR dataset; defer until a level actually wants it. |
| Music format | **Ogg Vorbis** for new/recorded tracks; **MIDI + TinySoundFont** for original game music (see MIDI section below) | Ogg: free, patent-clear, miniaudio-native. MIDI: tiny file size, authentic to original game; TSF renders MIDI → PCM via a bundled SF2 soundfont. |
| SFX format | **WAV (PCM 16-bit) for short sounds, Ogg Vorbis for long ones** | WAV decode is zero-cost; Ogg for anything >2s saves disk. miniaudio handles both transparently. |
| Existing `audiofmt/` (sox) | **Already deleted** (dead-code removal batch, 2026-04-15). | Was not wired up; miniaudio decodes everything we need. |
| Existing `SoundBuffer`/`SoundDevice` API | **Keep the class names, reimplement internals on miniaudio.** `actor.cc:1342` and `level.cc:610` keep compiling. | Minimizes churn in game code. The header is 17 lines; the impl is the interesting part. |
| Level format encoding | **Keep existing `_sfx[128]` per-level slot loading.** Add a new IFF chunk `MUSX` (music track) if/when levels want per-level music — separate followup. | Current SFX pipeline works mechanically; music can be deferred to a second iteration. |
| Scripting surface | **Mailbox primitives:** `play_sound(sfxIndex, volume=1, pitch=1)`, `stop_sound(handle)`, `play_music(name)`, `stop_music()`. Named SFX constants via the same `INDEXOF_*` registry extended with `SFX_*`. | Fits the existing script surface; scripts already drive actor behaviour this way. |
| Distance model | **Inverse-distance with rolloff, miniaudio default.** Per-sound min/max distance in level data. | Matches every other game engine's default; tunable later. |
| Mixer bus layout | **Three buses: master, sfx, music** (plus per-sound gain) | Enough for a volume slider UI; more buses (voice, UI, ambient) can be added without API break. |
| Music streaming vs. loaded | **Streamed.** miniaudio's `ma_sound_init_from_file` with `MA_SOUND_FLAG_STREAM`. | Music tracks are 2-10 MB each; streaming keeps RAM flat. |
| Pause-on-focus-loss | **Yes by default**, opt-out per-sound | Users hate audio that keeps going when they alt-tab. |
| Determinism | **Audio is non-deterministic and does not feed back into simulation.** | Multiplayer sync (see multiplayer plan) doesn't need audio to be lockstep; each client plays locally. |

## Implementation

### Phase 0 — Retire the stubs and sox ✓ DONE

`wfsource/source/audio/` and `wfsource/source/audiofmt/` were both removed in dead-code removal batch 2026-04-15. No action needed. `build_game.sh` succeeds and snowgoons runs silently.

### Phase 1 — Vendor miniaudio, hook up SFX one-shots

Goal: Existing `actor.cc:1342` SFX playback becomes audible.

1. `engine/vendor/miniaudio-<ver>/miniaudio.h` — single header. Record SHA256 in `engine/vendor/README.md`.
2. New TU `wfsource/source/audio/linux/miniaudio_impl.cc` with `#define MINIAUDIO_IMPLEMENTATION` — the one place the implementation is instantiated. Compile with `-DMA_NO_ENCODING` (we don't record), optionally `-DMA_NO_FLAC` / `-DMA_NO_MP3` if we commit to Ogg+WAV only (trims ~100 KB).
3. Reimplement `SoundDevice` / `SoundBuffer`:
   - `SoundDevice` owns a single `ma_engine` configured with sfx+music submixers.
   - `SoundBuffer(binistream&)` reads the bytes into a heap buffer and calls `ma_sound_init_from_data_source` on an `ma_audio_buffer`.
   - `SoundBuffer::play() const` calls `ma_sound_start`. For overlapping one-shots, clone the sound (or use miniaudio's sound groups / inlined sounds API — prefer `ma_engine_play_sound` for fire-and-forget).
4. Link `-ldl -lpthread -lm` (already linked). On Linux miniaudio picks ALSA→PulseAudio→JACK at runtime via dlopen — **no build-time audio dep**.
5. **Verify:** Snowgoons emits its existing SFX when actors fire the existing `play()` paths. Compare CPU usage baseline vs. with audio (expect <2% on idle desktop).

### Phase 2 — 3D positional SFX

Goal: SFX originating from actors pan/attenuate relative to the camera.

1. Extend `SoundBuffer` with `setPosition(const Vector3&)`, `setVelocity(const Vector3&)` (for Doppler if we ever want it — defer the actual Doppler enable).
2. Per-frame: game code that calls `actor->play(soundEffect)` also passes the actor's world position. Update `SoundBuffer` → `ma_sound_set_position`.
3. Listener: each frame, set listener position/orientation from the active camera. Single listener for now (splitscreen gets its own plan).
4. Distance model config: per-sound min/max distance read from level data (new field in whatever authoring structure holds per-sound metadata — TBD; could piggyback on existing mailbox-indexed SFX slots with a parallel array).
5. **Verify:** A stereo test level with sound sources to left/right of the camera pans correctly; walking away attenuates.

### MIDI player

The original WF game shipped with MIDI music. MIDI files are tiny (a few KB each) and fit naturally in an IFF chunk. To render MIDI → PCM for miniaudio we need a software synthesizer.

**Chosen library: TinySoundFont** (`tsf.h` + `tml.h`)
- Single-header, MIT license, pure C, zero dependencies
- `tml.h` parses `.mid` files; `tsf.h` renders them to interleaved PCM via an SF2 soundfont
- Outputs PCM that feeds directly into a miniaudio custom data source
- Confirmed working on Linux and Android arm64

**RAM footprint:**
- `tsf.h` runtime state: ~1–4 KB per TSF instance (voice table, channel state)
- Active voices: each simultaneous note consumes ~200–400 bytes of voice state; a typical GM MIDI track peaks at 32–64 simultaneous voices → ~8–25 KB voice RAM
- Soundfont samples: the loaded SF2 sample data is the dominant cost. **Soundfont choice is the RAM decision**, not TSF itself.

**Soundfont tiers:**

| Tier | File | Loaded RAM | Notes |
|------|------|-----------|-------|
| Dev default | `florestan-subset.sf2` (bundled in TSF repo) | ~400–600 KB | Drop-in, no curation work, acceptable quality. Use while MIDI tracks are being inventoried. |
| Ship target | WF-subset SF2 | ~1–2 MB | Custom SF2 containing only the MIDI program numbers WF's tracks actually use. Requires inventorying all MIDI files first. Smaller and purpose-fit. |
| Synthetic (floor) | Hand-rolled SF2 | ~100–200 KB | **Zero PCM samples.** SF2 built entirely from sine/triangle/sawtooth generator modulators. Absolute minimum possible size — the SF2 format overhead plus patch definitions only, no sample data. Instruments sound thin/electronic but are consistent and free on RAM. Requires authoring a custom SF2 file. This is the smallest MIDI playback option that exists short of dropping MIDI entirely. |

**Integration:** `MusicPlayer` owns a `tml_message*` sequence + `tsf*` instance. A miniaudio custom data source calls `tsf_render_short` into the mix buffer each callback. MIDI playback is driven entirely from the audio thread — no game-thread polling.

**Soundfont license:** must be permissive (CC0 or MIT-equivalent). `florestan-subset.sf2` is public domain.

### Phase 3 — Music subsystem

Goal: Background music track per level.

1. `MusicPlayer` singleton owning a streamed `ma_sound` on the `music` bus.
2. Level load hook: if the level provides a music track (mechanism: new IFF `MUSX` chunk, or a filename on the existing level header — decide per iffcomp-binary-chunk timing), start it; on level unload, fade out and stop.
3. Scripting: `play_music(name)` / `stop_music()` / `music_volume(v)` mailbox entries.
4. Crossfade on music change (miniaudio's fade API — ~200 ms default).
5. **Verify:** Snowgoons plays a test Ogg in the background; switching levels crossfades; `stop_music()` from a script silences it.

### Phase 4 — Scripting surface + mailbox plumbing

Goal: Scripts can trigger SFX directly (not just via actor behaviours).

1. Register `SFX_<name>` integer constants alongside `INDEXOF_*` (same `IntArrayEntry` mechanism the mailbox names use).
2. Lua C functions: `play_sound`, `stop_sound`, `play_music`, `stop_music`, `set_master_volume`, `set_sfx_volume`, `set_music_volume`. Wire through the same `register_closure` pattern already used for `read_mailbox` / `write_mailbox` in `scripting_stub.cc`.
3. Mirror for JS and wasm3 (same pattern each other audio-less API follows).
4. **Verify:** A Fennel script `(play-sound SFX_BEEP)` produces a beep.

### Phase 5 — Mobile backends

Goal: Audio works on Android and iOS. Mostly free — miniaudio already supports both — but verify.

1. Android: miniaudio uses AAudio (API 26+) or OpenSL ES (fallback). No new code; just confirm it links under the NDK toolchain.
2. iOS: miniaudio uses Core Audio / AudioUnit. Same — no new code.
3. Per the mobile-port plan, audio backend selection is a compile-time `#define` in miniaudio; no WF-side changes.
4. **Verify:** The same test level produces audio on a real Android device and a real iPhone.

### Phase 6 — Documentation

1. `docs/audio.md` — authoring guide. File formats, naming conventions for SFX constants, how to add music to a level, volume/rolloff defaults.
2. Update `docs/scripting-languages.md` with the `play_sound` / `play_music` surface.
3. `docs/engine-size-matrix.md` — add audio delta (expect ~50-150 KB depending on decoder configuration).

## Critical files

| File | Change |
|------|--------|
| `engine/vendor/miniaudio-<ver>/` | New — single-header vendor |
| `engine/vendor/README.md` | Add miniaudio entry + SHA256 |
| `engine/build_game.sh` | Add miniaudio impl TU; delete `audiofmt/` references if any; no system audio lib needed |
| `wfsource/source/audio/linux/device.cc` | Rewrite against `ma_engine` |
| `wfsource/source/audio/linux/buffer.cc` | Rewrite against `ma_sound` |
| `wfsource/source/audio/buffer.hp` | Add `setPosition` / `setVelocity` |
| `wfsource/source/audio/device.hp` | Add mixer-bus accessors, listener setter |
| `wfsource/source/audio/music.{hp,cc}` | New — `MusicPlayer` |
| `wfsource/source/game/level.cc` | Load per-level music (Phase 3) |
| `wftools/engine/stubs/scripting_stub.cc` | Register `play_sound` / `play_music` / volume closures |
| `wfsource/source/mailbox/mailbox.inc` | If SFX needs mailbox indices; TBD |
| `wfsource/source/audiofmt/` | **Already deleted** (2026-04-15) |
| `wfsource/source/audio/orig.cc`, `test.cc`, `LOADFILE.CC`, `*.WAV` | **Already deleted** (2026-04-15) |
| `engine/vendor/tsf/` | New — `tsf.h` + `tml.h` (TinySoundFont, MIT) |
| `engine/vendor/tsf/<name>.sf2` | New — bundled soundfont (TBD; permissive license) |
| `docs/audio.md` | New — authoring guide |

## Reuses

- Existing `SoundDevice` / `SoundBuffer` class shape — no churn at call sites.
- Existing per-level `_sfx[128]` loading path in `level.cc` — drop-in.
- Existing `INDEXOF_*`-style constant registry — add `SFX_*`.
- Existing mailbox/scripting surface — same `register_closure` idiom for new C functions.
- miniaudio's built-in decoders (WAV/Ogg) — no separate decoder libs.
- miniaudio's platform backends — no per-platform audio code in WF.

## Verification

1. **Snowgoons stays silent with Phase 0 committed** — no regression from deleting dead code.
2. **Phase 1 produces audible SFX** where the game already calls `play()`.
3. **Phase 2: pan test.** A source 10 units left of camera is ~fully in the left channel; moving to the right pans smoothly.
4. **Phase 3: music plays under SFX** without clipping; volume bus attenuates music independently.
5. **Phase 4: script-driven SFX** — Fennel/Lua/JS/wasm samples in `wftest/` each trigger a beep.
6. **No system audio package.** `ldd wf_game | grep -E 'asound|pulse|jack'` is empty (miniaudio dlopens at runtime).
7. **Size delta** recorded in `docs/engine-size-matrix.md`.
8. **Mobile parity** (Phase 5): same SFX on Android + iOS.

## Follow-ups (out of scope)

1. **HRTF.** Binaural audio for headphone users. miniaudio supports via `ma_hrtf`, dataset is ~40 KB. Ship when a level wants it.
2. **Reverb / occlusion.** Per-zone reverb presets, raycast-based occlusion against level geometry. Needs level-side authoring.
3. **Voice chat.** Covered by the multiplayer plan (WebRTC); separate pipeline from this SFX/music plan.
4. **Dynamic music.** Interactive stems that cross-fade based on game state (combat/exploration). Own design — adaptive-music middleware territory.
5. **Audio-driven gameplay.** Beat detection, sync-to-music gameplay. Speculative.
6. **Editor integration.** In-game volume mixer UI; per-level music picker. Depends on editor plan.
7. **Lossless music for small tracks.** FLAC decode enable flag if we ever ship short high-quality stingers.

## Open questions

- **Authoring of per-SFX metadata.** Min/max distance, volume, bus assignment — where do these live? Options: (a) parallel array alongside `_sfx[128]`, (b) a new IFF chunk `SFXM` with per-sound parameters, (c) inline in a JSON sidecar. Defer until Phase 2 is actually being written.
- **Sample rate policy.** miniaudio resamples on the fly. If all assets ship at 48 kHz we save the resample cost; if we allow mixed rates we pay a small per-sound CPU tax. Default: 48 kHz everywhere, documented in `docs/audio.md`.
- **Threading.** miniaudio runs audio on its own callback thread. `SoundBuffer::play()` currently has no thread safety story — confirm that fire-and-forget calls from the game thread don't race with the audio thread (miniaudio's high-level API is documented thread-safe; worth verifying once).
- **Console platforms.** If WF ever ships on a console, miniaudio doesn't cover it — need a platform-specific backend. Not a concern for the 2026 scope.
