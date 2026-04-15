# Investigation: Remove audio subsystem

**Date:** 2026-04-14
**Status:** Implemented (2026-04-15).

## Context

WF ships with a large, unused audio subsystem. On Linux it is entirely stubbed — `SoundBuffer::play()` is an empty function body. The `audiofmt/` directory is a vendored 1990s `sox` library that nothing links against. The `audio/orig.cc` file is a retained DirectSound implementation from the PSX/PC era. The net result is ~1.2 MB of dead source that compiles (or doesn't — it's not even in `build_game.sh`), contributes nothing at runtime, and will be replaced wholesale by the miniaudio plan (`docs/investigations/2026-04-14-audio-sound-music.md`) when that work is scheduled.

Goal: delete all of it cleanly so the codebase has no audio surface until a real one is ready to land.

## What exists

### Directories to delete entirely

| Directory | What it is | Size |
|-----------|-----------|------|
| `wfsource/source/audio/` | `SoundDevice`/`SoundBuffer` headers + Linux stubs + test programs + 3 `.WAV` sample files + DirectSound `orig.cc` | ~1.4 MB (mostly WAV files) |
| `wfsource/source/audiofmt/` | Vendored sox — 68 files of audio format converters (WAV, AIFF, G.711, VOC, echo, reverb, resampler…) | ~660 KB |

### Game-code files requiring surgical edits

| File | Lines | What to remove |
|------|-------|----------------|
| `wfsource/source/game/level.hp` | 56–57 | `#include <audio/device.hp>` and `#include <audio/buffer.hp>` |
| `wfsource/source/game/level.hp` | 185–186 | `SoundDevice* _theSoundDevice;` and `SoundBuffer* _sfx[128];` |
| `wfsource/source/game/level.cc` | 460–462 | `SoundDevice` construction + log line |
| `wfsource/source/game/level.cc` | 598–616 | SFX loading loop (128 slots from level OAD) |
| `wfsource/source/game/level.cc` | 674–675 | SFX deletion loop in destructor |
| `wfsource/source/game/level.cc` | 677–679 | `#if defined(MIDI_MUSIC) / DELETE_CLASS(_theSound) / #endif` |
| `wfsource/source/game/actor.cc` | 1336–1343 | `EMAILBOX_SOUND` case in the mailbox switch |
| `wfsource/source/Makefile.inc` | 141 | Remove `audio` and `audiofmt` from the directory list |

`wfsource/source/game/shield.cc` needs no change — its three `EMAILBOX_SOUND` calls are already commented out.

### Level format (`levelobj.ht`)

Lines 21–153 contain 128 consecutive `sfx0`…`sfx127` `int32` fields (packed asset IDs), plus `SoundYon`, `MusicVh`, `MusicVb`, `MusicSeq`. These are part of a generated OAD structure; changing them requires touching `levelobj.oas` and regenerating. Leave them in place for now — they're inert once the game-code references are removed, and touching the OAD format is a separate, non-trivial effort.

### Mailbox constants

`EMAILBOX_SOUND` and `EMAILBOX_LOCAL_MIDI` are defined in the generated OAS output. Leave them — removing the game-code `case` blocks is enough; the constants being defined elsewhere does no harm.

## Implementation

### Step 1 — Delete audio directories

```
rm -rf wfsource/source/audio/
rm -rf wfsource/source/audiofmt/
```

### Step 2 — Edit `level.hp`

Remove the two audio includes and the two audio member fields:

```cpp
// Remove:
#include <audio/device.hp>
#include <audio/buffer.hp>

// Remove:
SoundDevice*    _theSoundDevice;
SoundBuffer*    _sfx[ 128 ];
```

### Step 3 — Edit `level.cc`

1. Remove SoundDevice construction (lines 460–462):
   ```cpp
   DBSTREAM1( cflow << "Level::Level: setting up sound device " << std::endl; )
   _theSoundDevice = new (HALLmalloc) SoundDevice;
   assert( _theSoundDevice );
   ```

2. Remove the SFX loading block (lines 598–616):
   ```cpp
   { // load sound effects
   assert( ValidPtr( _theSoundDevice ) );
   ...
   }
   ```

3. Remove the SFX deletion loop (lines 674–675):
   ```cpp
   for ( int idxSoundEffect=0; idxSoundEffect<128; ++idxSoundEffect )
       delete _sfx[ idxSoundEffect ];
   ```

4. Remove the MIDI cleanup block (lines 677–679):
   ```cpp
   #if defined( MIDI_MUSIC )
       DELETE_CLASS( _theSound );
   #endif
   ```

### Step 4 — Edit `actor.cc`

Remove the `EMAILBOX_SOUND` case (lines 1336–1343):
```cpp
case EMAILBOX_SOUND:
{
    int32 soundEffect = value.WholePart();
    ...
    theLevel->_sfx[ soundEffect ]->play();
    break;
}
```

### Step 5 — Edit `Makefile.inc`

Remove `audio` and `audiofmt` from the directory list on line 141.

### Step 6 — Verify

1. `build_game.sh` succeeds.
2. No references to `SoundDevice`, `SoundBuffer`, `EMAILBOX_SOUND`, `_theSoundDevice`, `_sfx` remain in `wfsource/source/game/`.
3. Snowgoons runs and plays as before (was always silent).

## What this does NOT remove

- `levelobj.ht` SFX/music fields — inert but left to avoid OAD regeneration churn.
- `EMAILBOX_SOUND` / `EMAILBOX_LOCAL_MIDI` mailbox constants in OAS — constants without handlers are harmless.

## CDDA removal (completed 2026-04-15)

`wfsource/source/cdda/` contained a Windows-only CD-DA audio test (`cddatest.cc` using
`playCDTrack(hwnd, …)` and a `win/` subdirectory).  No external includes anywhere in
`wfsource/source/` or `wftools/`.  The directory was deleted entirely.

## Midi removal (completed 2026-04-15)

The `wfsource/source/midi/` directory contained only a standalone test binary
(`miditest.cc`, `miditest.rc`, `Makefile`) — no library, no headers, nothing
linked into the game build.  The directory was deleted entirely.

The three remaining stub cases in game code were also removed:

| File | Change |
|------|--------|
| `game/level.cc` | Removed `case EMAILBOX_MIDI:` no-op TODO block |
| `game/actor.cc` | Removed `case EMAILBOX_LOCAL_MIDI: UNIMPLEMENTED(...)` read case |
| `game/actor.cc` | Removed `case EMAILBOX_LOCAL_MIDI: break;` write case |

The `EMAILBOX_MIDI` and `EMAILBOX_LOCAL_MIDI` constants in `mailbox/mailbox.inc`
are OAS-generated and left in place — removing them requires touching the OAD
format, which is a separate non-trivial effort.

## Follow-up

When the miniaudio plan (`docs/investigations/2026-04-14-audio-sound-music.md`) is scheduled, Phase 0 of that plan is this removal — these are the same set of changes. If this investigation lands first, Phase 0 of the miniaudio plan can be skipped.
