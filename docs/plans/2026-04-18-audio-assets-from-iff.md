# Plan: audio assets come from `.iff`, not loose files

**Date:** 2026-04-18
**Status:** Not started
**Goal:** Remove every filesystem / loose-file code path that loads a MIDI,
soundfont, or SFX audio asset at runtime. Audio assets must travel inside
`cd.iff` / `level<N>.iff` the same way meshes, textures, and attribute data
already do. The current `loadAssetBytes(path)` → `AssetAccessor` →
per-asset-file bundling is a developer shortcut that should remain only
behind an opt-in dev/debug switch.

## Why

- **Single source of truth.** `cd.iff` is the shipping asset container
  — every other asset class already lives there. Music and soundfonts
  arriving as separate files on disk / separate APK entries is an
  accidental second pipeline.
- **Patching story.** Byte-preserving patchers (`scripts/patch_*.py`) can
  touch levels' audio the same way they touch scripts.
- **Authoring.** The Blender plugin / `levcomp-rs` / `iffcomp-rs` all
  already know how to thread assets through `.iff`. Audio doesn't.
- **Platform parity.** No more "copy the SF2 into wfsource/source/game/"
  on desktop + "symlink into assets/" on Android — the asset flows
  through the same chunk-based path `DiskFileHD` already reads.

## Scope

Current asset-file loaders we'll need to retire:

| Caller | Loads | Path |
|--------|-------|------|
| `audio/linux/music.cc` `MusicPlayer::play` | MIDI file | `level<N>.mid` via `loadAssetBytes` |
| `audio/linux/music.cc` `MusicPlayer::play` | Soundfont | `WF_MIDI_SOUNDFONT` (default `florestan-subset.sf2`) |
| `audio/linux/buffer.cc` `SoundBuffer` ctor | WAV/Ogg | (not currently file-based, but spec here for completeness) |

Bundling sites today (to delete after the port):

- `wfsource/source/game/*.mid`, `*.sf2` — loose files beside `cd.iff`
- `android/app/src/main/assets/*.mid`, `*.sf2` — symlinks into the APK
  asset dir

## Steps

### 1. IFF chunk design

Add new chunks so level `.iff` and `cd.iff` can carry audio. Candidates:

- `MIDI` — a per-level MIDI stream, replaces `level<N>.mid`.
- `SFNT` (SoundFont chunk) or shared `AUDI` container — soundfont bytes
  embedded in `cd.iff` (one global soundfont is fine; no per-level).
- `SFX ` — per-level or per-room SFX bank.

Keep alignment rules consistent with existing chunks (CD-sector multiples
where it matters).

### 2. Reader side

`audio/linux/music.cc::play` stops taking a path. Instead it takes a
`(const void* midiBytes, int size)` pair pulled from the level's MIDI
chunk by `Level` at load time. Same for the soundfont — loaded once from
the cd.iff-scope SFNT chunk at audio init.

### 3. Authoring side

- `iffcomp-rs`: accept `{ 'MIDI' [ "fur_elise.mid" ] }` syntax so sources
  can inline a .mid file.
- `levcomp-rs`: hook a per-level `music:` field into the level's IFF.
- Blender plugin: OAS field pointing at a MIDI asset path on disk, same
  shape as `MeshName` / `Filename`.

### 4. Opt-in dev/debug switch

Keep the filesystem path behind `-DWF_AUDIO_DEV_LOOSE_FILES=1` or a
runtime CLI flag (`-audio-loose`) so during iteration the dev doesn't
have to recompile `cd.iff` on every MIDI edit. Off by default in shipping
builds.

### 5. Cleanup

After step 4 lands and is the default:
- Delete loose `.mid` / `.sf2` from `wfsource/source/game/`.
- Delete their symlinks under `android/app/src/main/assets/`.
- Drop `WF_MIDI_SOUNDFONT` compile-time path macro.

## Notes

- Tied to the "Binary IFF chunk types" follow-up in wf-status.md
  (`WSM ` / `AOT ` tags, base64 drop) — the audio chunks should be
  binary-typed from day one, not text-encoded.
- iOS port doesn't need its own bundling pipeline if this lands before
  iOS Phase 3 starts.
