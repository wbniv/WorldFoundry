# A reproducible soundfont: `florestan-subset.sf2` from FluidR3_GM

Status: **implemented and verified on the Chromecast HD** (2026‑10‑01 17:30 (+07) = 10:30 UTC); **one decision is open for the user** (the licence policy, below).

- [x] Phase A: find out why the file is missing and whether it can be recovered (it cannot)
- [x] Phase B: a script that builds it from a permissively licensed base, a task, docs and a test
- [x] Phase C: prove it in the engine's own synth and on the device
- [ ] Phase D: the licence decision, then either commit the 7.6 MB file or generate it in every build (CI included)

## Context

The user asked about the missing soundfont ("i wonder why we didn't check it in?") and then said: **"i don't have soundfont files"**. What the repository showed:

- The engine loads one soundfont, `florestan-subset.sf2` (`audio/linux/music.cc`, `WF_MIDI_SOUNDFONT`, loaded through the asset accessor). **It has been in `.gitignore` since the commit that added MIDI music** (`e183d834`, 2026‑04‑17: "Runtime audio assets (see [engine/vendor/README.md](../../engine/vendor/README.md) for how to obtain)").
- `engine/vendor/README.md` documented how to get a *different* file, `TimGM6mb.sf2` (GPL, 5.7 MB, a dev placeholder), and said the ship target "will use a custom WF-subset SF2". **Nothing anywhere records how `florestan-subset.sf2` was made.** The Android commit that added the snowgoons music (`b2898b9b`) tracked only a **symlink** to it.
- **No copy survives**: the symlink dangles in a fresh checkout and on this machine, `find /` finds no such file, git history holds only the symlink, and the user has none. So the snowgoons flavor's release build failed in `lintVitalAnalyzeSnowgoonsRelease`, and a build with the music wanted would have played nothing.
- The project's asset policy (`wflevels/licence_policy.toml`) **rejects GPL**, so TimGM6mb could never ship.

Why it was left out of git, in plain terms: size (the dev font is 5.7 MB), licence (GPL), and the intent to ship "a custom subset" that was never written up. Nothing was lost from git, because the data was never in git.

## Decision

Since the original is gone, **make it reproducible**: a script that builds the file from a permissively licensed base, in the spirit of "everything must be rebuildable from the repository".

**The base: FluidR3_GM** (Frank Wen), from the Ubuntu/Debian package `fluid-soundfont-gm` (`apt-get download`, no root). Its copyright file says: *"I hereby release Fluid under the MIT license"*. It is 145 MB, so **the script keeps only the presets the MIDI files use**.

Rejected: TimGM6mb (GPL, policy rejects it); the ScummVM Roland SC-55 soundfont on this PC (a proprietary-sample font, not ours to ship); trying to reconstruct the lost file (no recipe, no source, no way to know what "florestan" was).

## Approach

[`scripts/make-soundfont-subset.py`](../../scripts/make-soundfont-subset.py) (`task soundfont`):

1. Find or fetch the base (`apt-get download fluid-soundfont-gm`, unpacked with `dpkg-deb` under `~/tmp/sf/`) and **check its SHA-256** against the value pinned in the script.
2. Read the MIDI files (default `wfsource/source/game/level0.mid`) and work out which presets they use: General MIDI program 0 on every melodic channel unless a program change or bank select says otherwise, and the drum kit (bank 128) if channel 10 plays. `level0.mid` is Für Elise: **program 0 only** (Acoustic Grand Piano). `--preset BANK:PROGRAM` adds more.
3. Keep those presets and everything they reference (instruments, samples and each sample's stereo partner), rebuild all the SF2 tables with remapped indices, and write the samples back with the 46 zero samples the format requires after each.
4. Write the result under the **same bank/preset numbers**, so a MIDI file selects it exactly as before, with the **MIT notice embedded in the file's INFO chunk** and in `engine/vendor/README.md`.

The output file name stays `florestan-subset.sf2` because the engine, the CMake bundling steps and the Android symlinks all use it; its content is now a FluidR3 subset. (A rename would touch all of them: a separate, optional change.)

There is **no visible surface** (it is what the music player loads), so there are no mockups.

## Open decision: the licence policy

`wflevels/licence_policy.toml` lists **only CC0 as accepted** (CC-BY is `reject-default`; GPL, LGPL and `unknown` are `reject`). **MIT is not listed**, so under the policy as written it counts as `unknown`. MIT is permissive, but it requires the copyright and permission notice to travel with copies, which the output file and the README now do. This is a project-policy question, so the **generated file stays gitignored** until the user decides:

1. Add MIT as `accept` (with attribution, since `require_attribution_credits = true`), or grant a waiver for this one asset; **and**
2. choose **commit the 7.6 MB file** (simple, CI needs nothing) **or generate it in every build** (a Taskfile dependency, and a download step in Codemagic, whose macOS machines have no `apt-get`; the script would need the `.deb` fetched from the Ubuntu archive by URL).

## Verification

Numbered, runnable steps; each shows its raw output with PASS or FAIL.

1. The recipe runs and the subset is small.

    ```
    $ scripts/make-soundfont-subset.py
    kept presets [(0, 0)]: 1 preset(s), 1 instrument(s), 41 sample(s); 144920 KB -> 7658 KB: /home/will/WorldFoundry-wbniv/wfsource/source/game/florestan-subset.sf2
    ```

    **PASS**: 145 MB down to 7.6 MB. (`level0.mid` analysis: format 1, 3 tracks, channels 1 and 2 only, 517 and 388 note-ons, no program changes, no drums.)

2. The base is the licensed one: `dpkg-deb -x fluid-soundfont-gm_3.1-5.3build1_all.deb`, then read its `copyright` file.

    ```
    Upstream Author: Frank Wen <getfrank@gmail.com>
    License: From README: "I hereby release Fluid under the MIT license, as described in COPYING."
    sha256 FluidR3_GM.sf2 = 74594e8f4250680adf590507a306655a299935343583256f3b722c48a1bc1cb0   (pinned in the script)
    ```

    **PASS**

3. The subset loads and sounds identical in TinySoundFont, the library the engine uses (`engine/vendor/tsf/tsf.h`): render middle C from each.

    ```
    subset:                    presets=1   name=Yamaha Grand Piano rms=0.206552
    full base (GM preset 0):   presets=189 name=Yamaha Grand Piano rms=0.206552
    ```

    **PASS**: the same preset, the same RMS to six places.

4. The regression test.

    ```
    $ python3 -m pytest tests/test_soundfont_subset.py -q
    ..                                                                       [100%]
    2 passed in 4.07s
    ```

    **PASS**: `--help` exits 0 and names FluidR3 and MIT; with the base present it builds the subset, checks the RIFF/`sfbk` structure and size (under 10 MB), that the MIT notice is inside the file, and that TinySoundFont renders the same as the full base. (Skipped where the base is not on disk.)

5. The snowgoons release build, which failed before, now bundles it.

    ```
    $ ./gradlew :app:assembleSnowgoonsRelease
    BUILD SUCCESSFUL in 9s
    assets: [('assets/cd.iff', 1352), ('assets/florestan-subset.sf2', 7658), ('assets/level0.mid', 7)]   (KB)
    ```

    **PASS**. (One snag, not a source problem: Android's incremental asset merge failed with `Cannot invoke "DataFile.getItems()" because "dataFile" is null` after the dangling link became a real file; deleting `app/build/intermediates/incremental/mergeSnowgoons*Assets` fixed it.)

6. On the real Chromecast HD: install the release APK, run it, read the engine log and Android's audio service.

    ```
    wf.log:   audio: MusicPlayer — soundfont not found: florestan-subset.sf2          (the earlier run, before the fix)
              audio: MusicPlayer — soundfont loaded (florestan-subset.sf2, 7842132 B)
              audio: MusicPlayer — playing level0.mid
    dumpsys audio:  AudioPlaybackConfiguration piid:375 deviceId:14 type:AAudio u/pid:10128/3951 state:started attr: usage=USAGE_MEDIA
    frame pacing: 127 frames: min 16.7 ms, median 16.7 ms (59.9 fps)      memory: TOTAL PSS 45098 KB
    ```

    **PASS** for "the music player loads the soundfont and plays", and for the stream being live on the output device. **Not verified: that anyone heard it.** The user's Chromecast is plugged into a monitor with no speakers; hearing it needs Bluetooth headphones, the monitor's headphone jack, an HDMI audio extractor or a TV.

7. The licence decision (above) and where the generated file lives. **PENDING (the user)**

## Out of scope

- The aquarium and condo flavors still bundle no music or sound effects: that is [Phase D of the aquarium-Chromecast plan](2026-09-30-aquarium-chromecast.md) (music) and [the SFX plan](2026-10-01-sfx-without-lua.md) (sound effects).
- Moving the soundfont into the IFF ([Audio assets from IFF](2026-04-18-audio-assets-from-iff.md)); this plan only makes the loose file reproducible.
- Renaming `florestan-subset.sf2`.

## Cost

None: a one-time 128 MB package download to `~/tmp/sf/` (aged out by the disk-hygiene timer after 14 days).

## Delegation

| Work | Tier | Why |
|---|---|---|
| The SF2 subsetter (a binary format with index remapping), its licence reading and the device proof | T4 | a wrong index silently plays the wrong instrument or nothing; done in this session |
| The licence policy decision and where the file lives | T5 | the user's call |
