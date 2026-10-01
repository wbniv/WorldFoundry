# Sound effects without Lua: a per-level sound bank any scripting engine can trigger

Status: **proposed** (2026‑10‑01), nothing built yet. The ranks below are recommendations; ranking is set in `TODO.md` by a Fable session.

- [ ] Phase A: spike: how a `.wav` can reach a level's IFF through the `sfx0` to `sfx127` fields that already exist
- [ ] Phase B: a per-level sound bank replaces the seven hardcoded Q\*bert loads in `game.cc`
- [ ] Phase C: a positional play mailbox, so a sound pans and fades with where the actor is
- [ ] Phase D: the first real sounds for the aquarium and the condo, heard on the Chromecast

## Context

The request: sound effects that do not need Lua. Older docs say they do on mobile
([the iOS port plan](2026-04-21-ios-port-codemagic.md), "Audio on iOS", and [the deferred mailbox plan](deferred/2026-04-17-audio-mailbox-api.md)).
**For sound effects that is no longer true**, and this plan starts from what the code does, checked in the source on 2026‑10‑01:

| Question | Answer today | Evidence |
|---|---|---|
| Can a script in a non-Lua engine play a sound effect? | **Yes.** Writing the slot number to mailbox 3017 plays it, from any engine that can write a mailbox. The Q\*bert levels do it from zForth. | `actor.cc:1694` (`case EMAILBOX_SOUND:` calls `SfxLibrary::Play`), `blender_create_qbert.py:638` (`3 3017 write-mailbox`) |
| Is anything still Lua-only? | **Music control only**: `play_music`, `stop_music`, `set_music_volume`. Level music itself starts from the engine. | `engine/stubs/scripting_lua.cc:50-69`, `game.cc:333` |
| Where do the sound files come from? | **A hardcoded list in the engine**: seven `SfxLibrary::Load` calls for `wflevels/qbert_practice/sfx/*.wav`, run for every level. Nothing a level carries. | `game.cc:345-351` |
| Can a level carry its own sounds? | **No.** The `sfx0` to `sfx127` fields are declared in `levelobj.oas`, but `level.cc` never reads them, and `levcomp-rs` filters `.wav` names out of the asset list. | `levelobj.oas:26`, `ini_writer.rs:21` |
| Is the sound positional? | **No.** `SfxLibrary::Play` calls the 2D `play()`. The 3D `play(x, y, z)` exists and the listener already follows the camera, but nothing calls it. | `sfx_library.cc:42`, `buffer.hp`, `level.cc:1005` |
| Do the mobile builds compile it? | Yes: Android and iOS both compile `audio/linux`, which holds `SfxLibrary`, and both create the sound device. Neither has been heard on a device. | `CMakeLists.txt` (`WF_DIRS`), `hal/android/audio.cc`, `hal/ios/audio.mm` |

So the trigger side is done. **The gap is data**: a level cannot carry sounds, so on the Chromecast the aquarium and the condo have nothing to play whatever script engine they use
(their APKs bundle only `cd.iff`), and a sound cannot come from where the actor is.

## Approach

**One design: each level carries its own sound bank in its IFF.** The authoring side fills the existing OAD `sfx` fields (no new OAS fields, which the pre-merge policy gates, see `TODO.md`),
`Level` loads the bank at init, and `EMAILBOX_SOUND` keeps working unchanged. This is the sound-effects half of
[Audio assets from IFF](2026-04-18-audio-assets-from-iff.md), and `SfxLibrary` already delivered the mailbox half of the deferred mailbox plan on 2026‑05‑16
([Q\*bert SFX](../qbert/plans/2026-05-16-qbert-sfx.md)). Music and the soundfont are not touched here.

Rejected: a loose-file manifest (`sfx.txt` per level). It would work everywhere in a day, but it is a second pipeline that Audio assets from IFF exists to delete, and each Android flavor
would still copy the files in by hand.

**Phase A, the spike.** `levcomp-rs` registers IFF files per room and drops `.wav` names from the INI ([`ini_writer.rs`](../../wftools/levcomp-rs/src/ini_writer.rs)), so it is not known how a
filename-typed OAD field would carry the bytes of a `.wav`. The spike answers one question and appends the answer to this plan with file paths: **do the bytes ride the existing asset path
(small Phase B), or do they need a new binary `SFX ` chunk** (as Audio assets from IFF proposes: binary-typed from day one, `iffcomp-rs` inline syntax `{ 'SFX ' [ "x.wav" ] }`).

**Phase B, the bank.** `Level` reads each non-zero `sfx` field, gets the bytes through `GetAssetManager().GetAssetStream`, and hands them to a new `SfxLibrary::Load(slot, bytes, len)`
overload (the library already keeps the bytes alive for `SoundBuffer`). The seven calls in `game.cc` go; Q\*bert's wavs move into its own level source so its sound does not regress.
`SfxLibrary::Clear()` at unload stays. A level with no sounds loads none and stays silent, with no error.

**Phase C, positional.** A new write-only local mailbox (`3023` is unused in `mailbox.inc`; the name, for example `SOUND_AT`, is for the implementer to settle) plays slot *n* at the actor's world
position through `SoundBuffer::play(x, y, z)`, via a new `SfxLibrary::Play(id, x, y, z)`. **`3017` stays 2D**, so Q\*bert does not change. Mailbox names reach scripts through whatever consumes
`mailbox.inc`; confirm that path when adding the entry.

**Phase D, content.** The aquarium and the condo have no sounds authored. Which events get one, and whether they are generated beeps (like Q\*bert's, from `gen_sfx.py`) or recorded clips with a
checked licence, is a decision for the user. It also shares its device listen with
[Phase D of the Chromecast plan](2026-09-30-aquarium-chromecast.md) (music and the soundfont).

**Decision asked of you:** is "straight to the IFF, no manifest stopgap" right? The price is that no Chromecast sound arrives until Phase B lands.

There is no visible surface (an engine and tooling change; the result is what the speakers do), so there are no mockups.

## Out of scope

- Music control from non-Lua engines: `MUSIC_PLAY`, `MUSIC_STOP` and `MUSIC_VOLUME` mailboxes (Phase B of the [deferred mailbox plan](deferred/2026-04-17-audio-mailbox-api.md)). The three Lua closures stay as they are.
- Named `SFX_<name>` constants instead of slot numbers (Phase C of that plan).
- Volume, pitch, looping and stopping a sound that is playing; HRTF, reverb, occlusion.
- Moving the music and the soundfont into the IFF (the rest of Audio assets from IFF).
- Hearing audio on iOS: it needs a real device with Apple signing.

## Verification

1. The trigger is already engine-neutral. `grep -n "SfxLibrary::Play\|case EMAILBOX_SOUND" wfsource/source/game/actor.cc`. Expected: a write handler that calls `SfxLibrary::Play`.

    ```
    1397:        case EMAILBOX_SOUND:
    1694:        case EMAILBOX_SOUND:
    1695:            SfxLibrary::Play(static_cast<int>(value.WholePart()));
    ```

    **PASS** (true before any work; line 1397 is the read case, which returns zero).

2. Phase A: the spike's answer is appended to this plan, naming the files that carry a `.wav` into a level's IFF. **PENDING**

3. Linux build, and the hardcoded loads are gone. `task build`, then `grep -n "SfxLibrary::Load" wfsource/source/game/game.cc`. Expected: the build succeeds and the grep prints nothing. **PENDING**
   (today the grep prints seven lines, `game.cc:345` to `351`.)

4. Q\*bert does not regress. Boot `qbert_practice` as in the [Q\*bert SFX plan](../qbert/plans/2026-05-16-qbert-sfx.md) (its steps 2 and 3). Expected: stderr shows `audio: sfx[0] loaded` to
   `audio: sfx[6] loaded` from the level's own bank, and a hop prints `audio: sfx[0] play`. **PENDING**

5. A level with no sounds. Boot snowgoons and the aquarium. Expected: no `audio: sfx` lines and no error. **PENDING**

6. Edge slots are silent and safe. The proposed test `tests/test_sfx_bank.py` (the regression guard): load a one-slot bank, then `Play` slot 0, an empty slot, `-1` and `500`. Expected: only slot 0
   logs `play`; nothing crashes. **PENDING**

7. Positional (Phase C). The same test writes the new mailbox for an actor at a known position. Expected: stderr names the slot and the position; by ear on the desktop, a sound left of the camera
   is heard on the left. **PENDING**

8. On the Chromecast, with no Lua in the build. `task chromecast-aquarium -- <ip>` with a sound authored (Phase D). Expected: `adb logcat` shows the bank loading and the play line when the event
   fires, and the sound is audible from the TV. Evidence: the logcat excerpt and a note of what was heard. **PENDING**

9. Codemagic `android-apk-debug` on the merged branch; the macOS and iOS workflows unaffected. Expected: green. **PENDING**

## Cost

None: local builds and device runs, plus about 6 free Codemagic Mac-minutes per `android-apk-debug` run. No paid service.

## Delegation

| Work | Tier | Why |
|---|---|---|
| Phase A: the spike | T4 | an unknown root cause (how the asset path treats a `.wav`); a wrong answer misdirects Phase B |
| Phase B: bank in the IFF, loader, Q\*bert moved over | T4 | tooling and engine across `levcomp-rs`, `iffcomp-rs` and `Level`; a wrong chunk design is expensive. Drops to T3 if the spike finds the bytes ride the existing path |
| Phase C: positional mailbox | T2 | one handler, one library function and one mailbox entry against a settled design |
| Phase D: which sounds, and from where | T5 | the user's taste and a licence call; generating the placeholder files afterwards is T2 |
