# Free the cached MIDI SoundFont at shutdown

Status: implemented and ASan smoke-tested. Will explicitly approved this engine change.

The Linux development engine's ASan smoke run reports 15,737,640 leaked bytes in five TinySoundFont allocations originating in `tsf_load_presets` via `MusicPlayer::play`. `MusicPlayer::stop` deliberately retains the synthesizer for subsequent songs, but the destructor currently deletes its implementation without closing the cached synth. This implementation is shared by the miniaudio Linux and Android paths and used by iOS where audio is enabled.

1. Preserve the existing cache across `stop()` and song changes. After stopping the sound and detaching its data source in `MusicPlayer::~MusicPlayer`, close a non-null synth with `tsf_close` before deleting the implementation. This also handles a SoundFont loaded before a later MIDI or sound initialization failure.
2. Confirm audio shutdown destroys the player before its engine and that no callback can use the synth after sound uninitialization. Avoid changing the vendor TinySoundFont code or release behavior.
3. Rebuild the development engine with ASan and run the same smoke path with the SoundFont and MIDI present. Require successful shutdown without the reported TinySoundFont leak. If another unrelated leak or build blocker remains, report it separately. Check that repeated playback can still reuse the cached synth when practical.

## Verification

The `--dev` ASan container build completed. A 30-frame single-cycle bamboo pond smoke loaded `florestan-subset.sf2`, played `level0.mid`, and exited 0 without a LeakSanitizer report. A 15-frame two-cycle smoke also exited 0, logging one SoundFont load and two MIDI plays, confirming reuse. Its local log is `build-docker/music-asan-smoke.log`. Linux audio shutdown deletes `MusicPlayer` before `SoundDevice`; `stop()` uninitializes the sound before the destructor closes the synth.
