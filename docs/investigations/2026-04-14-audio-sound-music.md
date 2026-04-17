# Investigation: Audio — sound effects, music, positional sound

**Date:** 2026-04-14
**Status:** Active — Phases 1+2 complete; Phase 3 (music subsystem / per-level tracks) next.
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

## Architecture: platform seam

The audio HAL is split into two layers so that console porting touches only the bottom layer:

```
game code / scripts
      |
SoundDevice / SoundBuffer  (wfsource/source/audio/*.hp)   ← public API; no backend types visible
      |
AudioBackend interface     (wfsource/source/audio/backend.hp)
      |  \_____________________________
      |                               |
miniaudio impl                 console impl (future)
hal/linux/audio_backend.cc     hal/ps5/audio_backend.cc
hal/android/audio_backend.cc   hal/xbox/audio_backend.cc
hal/ios/audio_backend.cc       hal/switch/audio_backend.cc
```

**Rules that keep the seam clean:**

1. **No `ma_*` types in public headers.** `SoundDevice.hp`, `SoundBuffer.hp`, and `MusicPlayer.hp` never `#include <miniaudio.h>`. All miniaudio state lives in impl `.cc` files or a pimpl struct.
2. **`AudioBackend` interface.** A thin abstract class (or C-style vtable struct) in `audio/backend.hp` with the minimum surface: `init`, `shutdown`, `play`, `stop`, `set_position`, `set_listener`, `stream_open`, `stream_close`, `tick` (if needed). `SoundDevice` holds a pointer to this; the correct impl is link-selected per platform (same pattern as `hal/linux/` vs. `hal/android/`).
3. **PCM pipeline stays above the seam.** TinySoundFont renders to a `float*` buffer before handing to the backend. Console backends consume the same PCM buffer — no MIDI-awareness needed below the seam.
4. **Build system selects impl TU.** `build_game.sh` / CMake links the right `hal/<platform>/audio_backend.cc`; no `#ifdef PLATFORM` chains in game code.

This mirrors the existing WF HAL pattern (`hal/dfhd.cc` → asset-accessor interface for Android). Console audio ports then reduce to: write `hal/<platform>/audio_backend.cc`, acquire SDK.

## Implementation

### Phase 0 — Retire the stubs and sox ✓ DONE

`wfsource/source/audio/` and `wfsource/source/audiofmt/` were both removed in dead-code removal batch 2026-04-15. No action needed. `build_game.sh` succeeds and snowgoons runs silently.

### Phase 1 — Vendor miniaudio, hook up SFX one-shots ✓ DONE

Goal: Existing `actor.cc:1342` SFX playback becomes audible.

1. `engine/vendor/miniaudio-<ver>/miniaudio.h` — single header. Record SHA256 in `engine/vendor/README.md`.
2. New TU `wfsource/source/audio/linux/miniaudio_impl.cc` with `#define MINIAUDIO_IMPLEMENTATION` — the one place the implementation is instantiated. Compile with `-DMA_NO_ENCODING` (we don't record), optionally `-DMA_NO_FLAC` / `-DMA_NO_MP3` if we commit to Ogg+WAV only (trims ~100 KB).
3. Reimplement `SoundDevice` / `SoundBuffer`:
   - `SoundDevice` owns a single `ma_engine` configured with sfx+music submixers.
   - `SoundBuffer(binistream&)` reads the bytes into a heap buffer and calls `ma_sound_init_from_data_source` on an `ma_audio_buffer`.
   - `SoundBuffer::play() const` calls `ma_sound_start`. For overlapping one-shots, clone the sound (or use miniaudio's sound groups / inlined sounds API — prefer `ma_engine_play_sound` for fire-and-forget).
4. Link `-ldl -lpthread -lm` (already linked). On Linux miniaudio picks ALSA→PulseAudio→JACK at runtime via dlopen — **no build-time audio dep**.
5. **Verify:** Snowgoons emits its existing SFX when actors fire the existing `play()` paths. Compare CPU usage baseline vs. with audio (expect <2% on idle desktop).

### Phase 2 — MIDI player ✓ DONE

Goal: MIDI music playback via TinySoundFont; a level can trigger a track and hear it rendered through miniaudio.

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

| Tier | File | Loaded RAM | Platform | Notes |
|------|------|-----------|----------|-------|
| Synthetic (floor) | Hand-rolled SF2 | ~100–200 KB | **Android** | **Zero PCM samples.** SF2 built entirely from sine/triangle/sawtooth generator modulators. No sample data at all. Instruments sound thin/electronic but consistent and essentially free on RAM. Requires authoring a custom SF2 file. |
| Dev / Linux v1 | `florestan-subset.sf2` (bundled in TSF repo) | ~400–600 KB | **Linux** | Drop-in, public domain, no curation work. Use for initial implementation; evaluate stepping up after hearing it in practice. |
| Step-up (Linux, optional) | TimGM6mb.sf2 | ~6 MB | Linux only | Real PCM samples, GM coverage, noticeably better timbre. Evaluate after florestan-subset is working. License: GPL — check if acceptable for the build. |
| Ship target (future) | WF-subset SF2 | ~1–2 MB | Both | Custom SF2 containing only the MIDI program numbers WF's tracks actually use. Requires inventorying all MIDI files first. Best balance of quality and size. |

**Soundfont selection is a compile-time flag** (`WF_MIDI_SOUNDFONT=florestan|synthetic|path/to/custom.sf2`) so swapping tiers requires no code change.

**Integration:** `MusicPlayer` owns a `tml_message*` sequence + `tsf*` instance. A miniaudio custom data source calls `tsf_render_short` into the mix buffer each callback. MIDI playback is driven entirely from the audio thread — no game-thread polling.

**Soundfont license:** must be permissive (CC0 or MIT-equivalent). `florestan-subset.sf2` is public domain.

## MIDI score sources

### Important legal note

A MIDI file has **two copyright layers**:
1. **The composition** — pre-1928 works (Bach, Mozart, Beethoven, etc.) are public domain everywhere. No issue.
2. **The MIDI arrangement itself** — a new creative work by whoever encoded it. This layer is what we must license, regardless of how old the underlying piece is. MIDI as a format is too young for any file to have expired into PD naturally; every MIDI file is either explicitly licensed or all-rights-reserved.

### CC0 — no attribution required (preferred)

| Source | URL | Content | Quality | Notes |
|--------|-----|---------|---------|-------|
| **OpenScore** (Open Goldberg, Open WTC) | musescore.com / github.com/OpenScore | Bach: Goldberg Variations (BWV 988), Well-Tempered Clavier (BWV 846–893), inventions | Machine-generated from engraving source | **Best for Bach.** Explicit CC0. MIDI export per-score or bulk via MuseScore CLI. Coverage skews heavily Bach; other composers sparse. |
| OpenGameArt.org CC0 Music | opengameart.org | 1,000+ game tracks: orchestral, ambient, RPG, battle | Varies; curated for games | Purpose-built for games; loopable. Diverse genres, not classical-focused. |
| GitHub: CC0-midis | github.com/m-malandro/CC0-midis | Original compositions | Community | Small curated CC0 collection; actively maintained. |
| itch.io CC0 MIDI assets | itch.io/game-assets/tag-cc0/tag-midi | Game music bundles: fantasy, battle, ambient | Generally higher quality than vintage archives | Community-curated. |

### CC BY / CC BY-SA — attribution required (still commercial-friendly)

| Source | URL | Content | Quality | Notes |
|--------|-----|---------|---------|-------|
| **Mutopia Project** | mutopiaproject.org | Bach, Mozart, Beethoven, Haydn, Schubert, Brahms, Handel, and many others | Metronomic (generated from LilyPond engraving) | Mix of PD, CC BY, CC BY-SA. **Filter out CC BY-NC items at download time.** Bulk download available. |
| **piano-midi.de** (Bernd Krueger) | piano-midi.de | Piano solo: Bach, Beethoven, Brahms, Chopin, Debussy, Mozart, Schubert, Tchaikovsky | **Expressive, high quality** — performed timing, not metronomic | CC BY-SA (German jurisdiction). Attribution: "Bernd Krueger, http://www.piano-midi.de". ShareAlike applies to derivative arrangements, not to the game shipping MIDI as a data asset unmodified. |
| Incompetech (Kevin MacLeod) | incompetech.com | 2,000+ cinematic/orchestral/ambient | Professional | CC BY 4.0. Not classical but high quality. |

### NOT suitable for commercial use (avoid)

| Source | Reason |
|--------|--------|
| Kunstderfuge (19,300+ files) | NC-only; 2,192 files are CC BY-NC-SA — still non-commercial |
| Classical Archives | Subscription; no free commercial license |
| BitMidi (113,000+ files) | Personal use only |
| VGMusic | Entertainment purposes only |
| IMSLP MIDI files | Per-file varies; must verify each — too much risk for bulk use |
| FreeMidi | Unclear license, assume restricted |

### Recommendation

- **Bach**: OpenScore CC0 (Goldberg, WTC) — zero friction, no attribution.
- **Broader classical**: Mutopia Project (filter to PD/CC BY/CC BY-SA) — large catalogue, metronomic quality.
- **Expressive piano**: piano-midi.de (CC BY-SA) — best quality, credit Bernd Krueger in game credits.
- **Game-style background**: OpenGameArt.org CC0 — designed for exactly this use case.

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

### Phase 5 — 3D positional SFX ✓ DONE (2026-04-17)

Goal: Actors' SFX play-calls pan relative to the camera; moving sources track smoothly.

1. ✓ `SoundBuffer::play(x, y, z)` overload added in `audio/buffer.hp` / `audio/linux/buffer.cc`. Backed by `ma_sound_set_position`. (`set_velocity` deferred — no current caller needs it.)
2. ✓ `SoundDevice::tick()` takes listener position + forward + up; `Level::updateSound()` feeds it `_camera->cameraPos.position / direction / up` each frame.
3. Default `min_distance=5` on positional sources (see bugs below); per-level SFXM rolloff chunk deferred.
4. HRTF deferred — not needed for current levels.
5. ✓ Verified in snowgoons 2026-04-17: Für Elise plays continuously, REF beep centred, +right-vector beep pans right, −right-vector beep pans left. No regressions to Phase 3 music playback.

Three miniaudio gotchas surfaced during verification (all three were simultaneously broken
in the first Phase 5 cut, commit `c385251`; fixed in `d1e913d`). They share a failure mode:
`ma_sound_start` returns success, `ma_sound_is_playing` returns true, and yet there is
no audible output, so they look identical to real bugs in the source data.

- **End-callback `ma_sound_uninit` corrupts the mixer.** miniaudio forbids destroying a
  sound from inside a callback (callback runs on the audio thread). The Phase 5 cut did
  exactly that, which cut off any concurrently playing sounds (including the MIDI stream)
  a few samples after the one-shot finished. Fix: lock-free atomic stack of done
  PlayInstances, drained from the main thread by `DrainDoneSounds()` in
  `SoundDevice::tick()`.
- **Zero listener direction/up silences spatialization.** Early frames (before the camera
  transform is populated) pass zero vectors; miniaudio accepts them without error and
  produces silent output for every positional sound. Fix: length-check the vectors in
  `SoundDevice::tick()` before forwarding to `ma_engine_listener_set_direction` /
  `_set_world_up`.
- **Default `min_distance=1` attenuates too aggressively.** At min=1 and distance=5
  (typical small-scale sound placement), gain = 1/5 = −14 dB. With a music bed running,
  the one-shot is effectively inaudible. Fix: `ma_sound_set_min_distance(5.f)` on all
  positional sources — a better default for meter-scale worlds.

Recorded for future miniaudio work: `memory/project_miniaudio_gotchas.md`.

### Phase 6 — Mobile backends

Goal: Audio works on Android and iOS. Mostly free — miniaudio already supports both — but verify.

1. Android: miniaudio uses AAudio (API 26+) or OpenSL ES (fallback). No new code; just confirm it links under the NDK toolchain.
2. iOS: miniaudio uses Core Audio / AudioUnit. Same — no new code.
3. Per the mobile-port plan, audio backend selection is a compile-time `#define` in miniaudio; no WF-side changes.
4. Console platforms: miniaudio does NOT natively support PS4/PS5, Xbox, or Switch. Each console SDK exposes its own audio API (libSceAudio, XAudio2, nn::audio). miniaudio's custom-backend extension point (`ma_backend`) is the bridge — write a thin per-console `ma_backend` implementation that calls the platform API. The WF audio abstraction (`SoundDevice` / `SoundBuffer`) stays unchanged above it. Plan separately once developer program access is in hand.
5. **Verify:** The same test level produces audio on a real Android device and a real iPhone.

### Phase 7 — Documentation

1. `docs/audio.md` — authoring guide. File formats, naming conventions for SFX constants, how to add music to a level, volume/rolloff defaults.
2. Update `docs/scripting-languages.md` with the `play_sound` / `play_music` surface.
3. `docs/engine-size-matrix.md` — add audio delta (expect ~50-150 KB depending on decoder configuration).

## Critical files

| File | Change |
|------|--------|
| `wfsource/source/audio/backend.hp` | New — `AudioBackend` interface (pimpl seam) |
| `wfsource/source/audio/linux/audio_backend.cc` | New — miniaudio impl of `AudioBackend` |
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
3. **Phase 2: MIDI plays.** A test MIDI file loops in the background; no skips, consistent with florestan-subset soundfont.
4. **Phase 3: music plays under SFX** without clipping; volume bus attenuates music independently.
5. **Phase 4: script-driven SFX** — Fennel/Lua/JS/wasm samples in `wftest/` each trigger a beep.
6. **Phase 5: pan test.** A source 10 units left of camera is ~fully in the left channel; moving to the right pans smoothly.
6. **No system audio package.** `ldd wf_game | grep -E 'asound|pulse|jack'` is empty (miniaudio dlopens at runtime).
7. **Size delta** recorded in `docs/engine-size-matrix.md`.
8. **Mobile parity** (Phase 6): same SFX on Android + iOS.

## Follow-ups (out of scope)

0. **Mailbox-wired audio API (music + SFX).** Phase 4 as originally planned
   was mailbox primitives reachable from every scripting engine; it shipped as
   Lua-only C closures (`play_music` / `stop_music` / `set_music_volume` in
   `scripting_lua.cc`). The other seven engines can't trigger audio. SFX are
   not scriptable at all — the old `_sfx[]->play()` still fires from actor
   internals but there is no `play_sound` mailbox or closure. The pre-cleanup
   engine had per-level SFX slots (`_sfx[128]`) loaded from level IFF and
   triggered from actor code via `EMAILBOX_CD_TRACK`; the dead-code removal
   batches deleted most of that plumbing. The follow-up plan is to re-wire
   both music and SFX as mailbox writes on top of the current miniaudio
   backend — see the separate plan doc (linked from `wf-status.md` when
   written).
1. **HRTF.** Binaural audio for headphone users. miniaudio supports via `ma_hrtf`, dataset is ~40 KB. Ship when a level wants it.
2. **Reverb / occlusion.** Per-zone reverb presets, raycast-based occlusion against level geometry. Needs level-side authoring.
3. **Voice chat.** Covered by the multiplayer plan (WebRTC); separate pipeline from this SFX/music plan. See `docs/investigations/2026-04-14-multiplayer-voice-mobile-input.md`.
4. **Dynamic music.** Interactive stems that cross-fade based on game state (combat/exploration). Own design — adaptive-music middleware territory.
5. **Audio-driven gameplay.** Beat detection, sync-to-music gameplay. Speculative.
6. **Editor integration.** In-game volume mixer UI; per-level music picker. Depends on editor plan.
7. **Lossless music for small tracks.** FLAC decode enable flag if we ever ship short high-quality stingers.

## Open questions

- **Authoring of per-SFX metadata.** Min/max distance, volume, bus assignment — where do these live? Standard IFF already has well-established audio chunk types as reference: `AIFF`/`AIFC` (Apple/EA IFF85, 1985) carries instrument loop points and markers inline; `8SVX` (Amiga) carries volume, octaves, and attack/release per sample; `SMUS` (EA Simple Musical Score, Amiga) carries tempo, instrument assignments, and score events all in one FORM. For WF's case, a new `SFXM` IFF chunk (one record per SFX slot: min/max distance, volume, bus, loop flag) mirrors this established pattern. Alternative: extend the AIFF-inspired level audio block rather than a sidecar. Decide during Phase 5 implementation when the actual fields are known.
- **Sample rate policy.** miniaudio resamples on the fly. If all assets ship at 48 kHz we save the resample cost; if we allow mixed rates we pay a small per-sound CPU tax. Default: 48 kHz everywhere, documented in `docs/audio.md`.
- **Threading.** miniaudio runs audio on its own callback thread. `SoundBuffer::play()` currently has no thread safety story — confirm that fire-and-forget calls from the game thread don't race with the audio thread (miniaudio's high-level API is documented thread-safe; worth verifying once).
- **Console platforms.** In scope. The `AudioBackend` seam (see Architecture section above) is the plan — write `hal/<platform>/audio_backend.cc` per console using the platform SDK (libSceAudio for PS4/PS5, XAudio2/GDK for Xbox, nn::audio for Switch). Blocked on acquiring developer program access for each platform before any code can be written.
