| Date | Change |
|------|--------|
| [2026-05-05](https://github.com/wbniv/WorldFoundry/commit/74008c54) | chore: accumulated session work — docs, qbert scripts, engine tweaks |
| [2026-04-17](https://github.com/wbniv/WorldFoundry/commit/2d341390) | docs(audio): mark Phase 5 done; add mailbox-wired audio API plan |
| [2026-04-17](https://github.com/wbniv/WorldFoundry/commit/e183d834) | feat(audio): Phase 2 — MIDI via TinySoundFont + MusicPlayer |
| [2026-04-17](https://github.com/wbniv/WorldFoundry/commit/f4dc979b) | feat(audio): Phase 1 — vendor miniaudio, SoundDevice/SoundBuffer, startup beep |
| [2026-04-17](https://github.com/wbniv/WorldFoundry/commit/3a3c421b) | docs(audio): console audio is in 2026 scope; point to AudioBackend seam plan |
| [2026-04-17](https://github.com/wbniv/WorldFoundry/commit/e6a50008) | docs(audio): add AudioBackend pimpl seam for clean console porting |
| [2026-04-17](https://github.com/wbniv/WorldFoundry/commit/8f71040a) | docs(audio): reorder phases — MIDI→Phase 2, 3D SFX→Phase 5; add console audio note |
| [2026-04-17](https://github.com/wbniv/WorldFoundry/commit/c31d251b) | docs(audio): expand MIDI score sources with classical research |
| [2026-04-16](https://github.com/wbniv/WorldFoundry/commit/dfde2672) | docs(audio): platform soundfont decisions + CC MIDI score sources |
| [2026-04-16](https://github.com/wbniv/WorldFoundry/commit/4c3dee0b) | docs(audio): expand synthetic-waveform SF2 tier description |
| [2026-04-16](https://github.com/wbniv/WorldFoundry/commit/8c35b79c) | docs(audio): Phase 0 done; add MIDI/TinySoundFont research; mark active |
| [2026-04-16](https://github.com/wbniv/WorldFoundry/commit/4430ffa6) | chore: move engine + vendor to top-level engine/ directory |
| [2026-04-14](https://github.com/wbniv/WorldFoundry/commit/790dc745) | vendor Lua 5.4.8, drop system liblua5.4-dev dependency |

<!--history-meta v1
74008c54	author	Will Norris
74008c54	added	8
74008c54	deleted	8
74008c54	files	1
74008c54	body	docs: new plans and investigations (qbert palette, round-clear, fall/lives,\n  cube-palette, camera-path revival, qbert-autopilot, zforth-coroutines);\n  updated level-building.md, level-design-troubleshooting.md, scripting-languages.md;\n  reference screenshots for per-round palette; session transcripts\n\nscripts/research/mame/qbert_palette_capture.lua: fix nil palette_dev —\n  emu.register_start is deprecated and fires before devices are ready;\n  moved DIP set + device lookup to frame 1 inside register_frame_done\n\nwflevels/qbert_practice/blender_create_qbert.py: apex respawn signal (mb[426])\n  replacing broken INDEXOF_X/Y/Z director writes\n\nengine/stubs/zfconf.h: dict size bump\nwfsource/source/mailbox/mailbox.inc: global mailbox range cap 0..998\nwfsource/source/gfx/gl/display.cc, main.cc: display/startup tweaks\nwflevels/marble-madness/*.iff, wfsource/source/game/cd.iff: binary level artifacts\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
2d341390	author	Will Norris
2d341390	added	41
2d341390	deleted	6
2d341390	files	1
2d341390	body	wf-status.md and the audio investigation now reflect that Phase 5\n(3D positional SFX + listener tracking) is complete, including the\nthree miniaudio gotchas surfaced during verification. Calls out the\nremaining gap: audio is Lua-only today — the other seven scripting\nengines can't trigger music or SFX.\n\ndocs/plans/2026-04-17-audio-mailbox-api.md proposes closing that\ngap. The engine originally had exactly this: EMAILBOX_SOUND=3017\nand a per-level _sfx[128] slot table loaded from OAD sfx0..sfx127.\nThe handler and loader were deleted in 460a3fd ("remove audio\nsubsystem (was entirely stubbed on Linux)") — the deletion was\ncorrect at the time because the backend was Linux-stubbed\nDirectSound. With miniaudio in place, the upstream plumbing can\nbe restored on top of a real backend.\n\nPlan phases:\n- A: restore _sfx[128] loader + EMAILBOX_SOUND handler that plays\n  at the actor's position (Phase 5 listener tracking gives it\n  positional audio for free).\n- B: new EMAILBOX_MUSIC_{PLAY,STOP,VOLUME} mailboxes; Lua closures\n  become thin forwarders.\n- C (optional): named SFX_* constants via the existing\n  IntArrayEntry mechanism.\n\nThe mailbox enum values (SOUND, CD_TRACK, MIDI, LOCAL_MIDI) and\nthe OAD sfx0..sfx127 fields still exist — data-format wires are\nalready pulled through the wall; the plan is mostly handlers and\na level-side loader.\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
e183d834	author	Will Norris
e183d834	added	2
e183d834	deleted	2
e183d834	files	1
e183d834	body	- engine/vendor/tsf/: tsf.h v0.9 + tml.h v0.7 (public domain)\n- audio/music.hp + linux/music.cc: MusicPlayer owns tsf* + tml_message*;\n  implements a miniaudio custom data source that renders MIDI → stereo\n  float PCM on the audio callback thread; looping, volume control, stop\n- linux/audio.cc: create/destroy gMusicPlayer alongside gSoundDevice\n- game.cc: smoke-test plays test_scale.mid (C-major scale) on startup\n- wfsource/source/game/test_scale.mid: 105-byte generated MIDI for testing\n- wfsource/source/game/.gitignore: exclude *.sf2, *.deb, *.bak from repo\n- vendor/README.md: document tsf + runtime soundfont setup (TimGM6mb.sf2,\n  GPL, 5.7 MB — obtain via timgm6mb-soundfont package; not committed)\n\nSoundfont: TimGM6mb.sf2 (136 GM presets, loads and renders correctly).\nVerified: "MusicPlayer — soundfont loaded" + "playing test_scale.mid"\non startup; C-major scale audible through PulseAudio.\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
f4dc979b	author	Will Norris
f4dc979b	added	2
f4dc979b	deleted	2
f4dc979b	files	1
f4dc979b	body	- engine/vendor/miniaudio-0.11.25/: single-header miniaudio v0.11.25 (MIT-0)\n- audio/device.hp + linux/device.cc: SoundDevice owns ma_engine + sfx group;\n  init/shutdown via _InitAudio()/_TermAudio() in hal.cc around PIGSMain()\n- audio/buffer.hp + linux/buffer.cc: SoundBuffer wraps raw WAV/Ogg bytes;\n  fire-and-forget play() via heap PlayInstance (decoder + sound) freed by\n  the ma_sound end callback — no lifetime hazard\n- audio/linux/miniaudio_impl.cc: one-TU MINIAUDIO_IMPLEMENTATION instantiation\n  with MA_NO_ENCODING + MA_NO_FLAC (WAV + Ogg Vorbis only)\n- audio/linux/audio_internal.hp: private header with Impl definition and\n  ma_engine_get()/ma_sfx_group_get() inlines; never included by game code\n- hal/linux/audio.h + audio.cc: _InitAudio/_TermAudio; plugs into hal.cc\n  the same way Steam does\n- level.cc::updateSound(): ticks gSoundDevice listener (origin for now)\n- game.cc: smoke-test plays test_beep.wav on startup\n- build_game.sh: -I vendor/miniaudio-0.11.25 added to CXXFLAGS;\n  audio/linux/ already in DIRS so all TUs compile automatically\n\nVerified: "audio: miniaudio v0.11.25 ready" + beep queued on startup.\nNo system audio package — miniaudio dlopens ALSA/PulseAudio at runtime.\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
3a3c421b	author	Will Norris
3a3c421b	added	1
3a3c421b	deleted	1
3a3c421b	files	1
3a3c421b	body	Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
e6a50008	author	Will Norris
e6a50008	added	29
e6a50008	deleted	0
e6a50008	files	1
e6a50008	body	No ma_* types in public headers; AudioBackend interface sits between\nSoundDevice and miniaudio so a console port only needs a new hal/<platform>/\naudio_backend.cc. Rules, ASCII diagram, and critical-files entries added.\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
8f71040a	author	Will Norris
8f71040a	added	22
8f71040a	deleted	18
8f71040a	files	1
8f71040a	body	Phase 2 is now MIDI player (tsf.h + miniaudio custom source — all deps available\nafter Phase 1). 3D positional SFX moved to Phase 5, after scripting surface lands.\nMobile and Docs renumbered to Phase 6/7. Console audio (miniaudio custom backend\nfor libSceAudio/XAudio2/nn::audio) added to Phase 6. Voice chat links to multiplayer\ninvestigation. Per-SFX metadata open question updated with IFF audio chunk research\n(AIFF, 8SVX, SMUS precedents; SFXM proposal).\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
c31d251b	author	Will Norris
c31d251b	added	33
c31d251b	deleted	18
c31d251b	files	1
c31d251b	body	Add two-layer copyright note (composition vs. MIDI arrangement).\nPrimary classical sources: OpenScore CC0 (Bach — Goldberg/WTC, no\nattribution), Mutopia Project CC-BY/PD (broad coverage, filter out NC),\npiano-midi.de CC-BY-SA (expressive piano, Bernd Krueger attribution).\nAvoid: Kunstderfuge (NC), Classical Archives (subscription), BitMidi,\nIMSLP bulk use.\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
dfde2672	author	Will Norris
dfde2672	added	36
dfde2672	deleted	5
dfde2672	files	1
dfde2672	body	Android: synthetic SF2 (zero PCM samples, floor). Linux: florestan-subset\ninitially, optional step-up to TimGM6mb after evaluation. Add MIDI score\nsource table: CC0 (OpenGameArt, CC0-midis, itch.io) and CC-BY\n(Piano-midi.de for classical — Bernd Krueger, CC-BY-SA, best classical\nsource). Mark sources to avoid (BitMidi, Kunstderfuge, VGMusic).\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
4c3dee0b	author	Will Norris
4c3dee0b	added	10
4c3dee0b	deleted	3
4c3dee0b	files	1
4c3dee0b	body	Zero PCM samples — sine/triangle/sawtooth modulators only. Absolute\nfloor for MIDI playback size; ~100-200 KB total, no sample data at all.\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
8c35b79c	author	Will Norris
8c35b79c	added	29
8c35b79c	deleted	12
8c35b79c	files	1
8c35b79c	body	Phase 0 (audio/ + audiofmt/ deletion) was already completed in dead-code\nremoval batch 2026-04-15. Add MIDI section: TinySoundFont (tsf.h + tml.h,\nMIT, single-header) renders MIDI→PCM via bundled SF2; RAM is dominated by\nsoundfont size (~2-4 MB for a curated subset). Update music format decision,\ncritical files table, and wf-status.\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
4430ffa6	author	Will Norris
4430ffa6	added	5
4430ffa6	deleted	5
4430ffa6	files	1
4430ffa6	body	wftools/wf_engine/ → engine/\nwftools/vendor/    → engine/vendor/\nwftools/wf_viewer/stubs/   → engine/stubs/\nwftools/wf_viewer/include/ → engine/include/\nwftools/wf_engine/PLAN.md  → docs/plans/2026-04-engine-start-snowgoons-directly.md\n\nengine/ is the runnable game; wftools/ is now strictly dev tooling.\nUpdated build_game.sh path vars, Taskfile.yml, .gitignore, and ~45 doc files.\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
790dc745	author	Will Norris
790dc745	added	162
790dc745	deleted	0
790dc745	files	1
790dc745	body	Lua is now compiled from wftools/vendor/lua-5.4.8/src/ and linked\nstatically into wf_game. No system liblua5.4-dev is required.\n\nbuild_game.sh changes:\n- LUA_DIR="$VENDOR/lua-5.4.8" alongside WASM3_DIR\n- -I"$LUA_DIR/src" added to CXXFLAGS\n- 32 Lua library TUs compiled via gcc with -DLUA_USE_POSIX\n  -DLUA_USE_DLOPEN (require() / dlopen() support, no readline)\n- -llua5.4 removed from link line; -ldl added (for loadlib dlopen)\n\nscripting_stub.cc: <lua5.4/lua.h> -> <lua.h> (three include lines)\n\ndocs:\n- scripting-languages.md: update Lua runtime column\n- dev-setup.md: remove liblua5.4-dev from apt install list\n- vendor/README.md: add Lua 5.4.8 entry + SHA256\n\nAlso commit all untracked investigation and plan docs written this\nsession: audio, Jolt physics, constraints, mobile port, multiplayer,\nparty game, remove-audio, rest-api-box, compile-time switches, wasm3,\nand the vendor-lua plan itself.\n\nldd wf_game | grep lua → empty (no system Lua at runtime)\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
-->
