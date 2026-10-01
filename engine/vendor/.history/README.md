| Date | Change |
|------|--------|
| [2026-04-17](https://github.com/wbniv/WorldFoundry/commit/e183d834) | feat(audio): Phase 2 — MIDI via TinySoundFont + MusicPlayer |
| [2026-04-17](https://github.com/wbniv/WorldFoundry/commit/f4dc979b) | feat(audio): Phase 1 — vendor miniaudio, SoundDevice/SoundBuffer, startup beep |
| [2026-04-16](https://github.com/wbniv/WorldFoundry/commit/4430ffa6) | chore: move engine + vendor to top-level engine/ directory |
| [2026-04-16](https://github.com/wbniv/WorldFoundry/commit/b9834958) | feat(levcomp): compute per-object OADSize from class schema |
| [2026-04-15](https://github.com/wbniv/WorldFoundry/commit/f89c0c56) | cleanup: move iffwrite from wfsource/source to wftools |
| [2026-04-15](https://github.com/wbniv/WorldFoundry/commit/fff88f5c) | scripting: add Wren, WAMR, zForth engines; restore snowgoons IFF; all engines on by default |
| [2026-04-15](https://github.com/wbniv/WorldFoundry/commit/529675b7) | scripting: vendor six Forth engines + nanoFORTH + plans for Wren and Forth |
| [2026-04-14](https://github.com/wbniv/WorldFoundry/commit/790dc745) | vendor Lua 5.4.8, drop system liblua5.4-dev dependency |
| [2026-04-14](https://github.com/wbniv/WorldFoundry/commit/cfa739c5) | wasm3 scripting engine: base64-wrapped modules on the #b64 sigil |
| [2026-04-14](https://github.com/wbniv/WorldFoundry/commit/8384f902) | JavaScript on the // sigil: QuickJS + JerryScript engines |

<!--history-meta v1
e183d834	author	Will Norris
e183d834	added	9
e183d834	deleted	0
e183d834	files	1
e183d834	body	- engine/vendor/tsf/: tsf.h v0.9 + tml.h v0.7 (public domain)\n- audio/music.hp + linux/music.cc: MusicPlayer owns tsf* + tml_message*;\n  implements a miniaudio custom data source that renders MIDI → stereo\n  float PCM on the audio callback thread; looping, volume control, stop\n- linux/audio.cc: create/destroy gMusicPlayer alongside gSoundDevice\n- game.cc: smoke-test plays test_scale.mid (C-major scale) on startup\n- wfsource/source/game/test_scale.mid: 105-byte generated MIDI for testing\n- wfsource/source/game/.gitignore: exclude *.sf2, *.deb, *.bak from repo\n- vendor/README.md: document tsf + runtime soundfont setup (TimGM6mb.sf2,\n  GPL, 5.7 MB — obtain via timgm6mb-soundfont package; not committed)\n\nSoundfont: TimGM6mb.sf2 (136 GM presets, loads and renders correctly).\nVerified: "MusicPlayer — soundfont loaded" + "playing test_scale.mid"\non startup; C-major scale audible through PulseAudio.\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
f4dc979b	author	Will Norris
f4dc979b	added	2
f4dc979b	deleted	0
f4dc979b	files	1
f4dc979b	body	- engine/vendor/miniaudio-0.11.25/: single-header miniaudio v0.11.25 (MIT-0)\n- audio/device.hp + linux/device.cc: SoundDevice owns ma_engine + sfx group;\n  init/shutdown via _InitAudio()/_TermAudio() in hal.cc around PIGSMain()\n- audio/buffer.hp + linux/buffer.cc: SoundBuffer wraps raw WAV/Ogg bytes;\n  fire-and-forget play() via heap PlayInstance (decoder + sound) freed by\n  the ma_sound end callback — no lifetime hazard\n- audio/linux/miniaudio_impl.cc: one-TU MINIAUDIO_IMPLEMENTATION instantiation\n  with MA_NO_ENCODING + MA_NO_FLAC (WAV + Ogg Vorbis only)\n- audio/linux/audio_internal.hp: private header with Impl definition and\n  ma_engine_get()/ma_sfx_group_get() inlines; never included by game code\n- hal/linux/audio.h + audio.cc: _InitAudio/_TermAudio; plugs into hal.cc\n  the same way Steam does\n- level.cc::updateSound(): ticks gSoundDevice listener (origin for now)\n- game.cc: smoke-test plays test_beep.wav on startup\n- build_game.sh: -I vendor/miniaudio-0.11.25 added to CXXFLAGS;\n  audio/linux/ already in DIRS so all TUs compile automatically\n\nVerified: "audio: miniaudio v0.11.25 ready" + beep queued on startup.\nNo system audio package — miniaudio dlopens ALSA/PulseAudio at runtime.\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
4430ffa6	author	Will Norris
4430ffa6	added	53
4430ffa6	deleted	0
4430ffa6	files	1
4430ffa6	body	wftools/wf_engine/ → engine/\nwftools/vendor/    → engine/vendor/\nwftools/wf_viewer/stubs/   → engine/stubs/\nwftools/wf_viewer/include/ → engine/include/\nwftools/wf_engine/PLAN.md  → docs/plans/2026-04-engine-start-snowgoons-directly.md\n\nengine/ is the runnable game; wftools/ is now strictly dev tooling.\nUpdated build_game.sh path vars, Taskfile.yml, .gitignore, and ~45 doc files.\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
b9834958	author	Will Norris
b9834958	added	53
b9834958	deleted	0
b9834958	files	1
b9834958	body	Adds oad_loader module that reads compiled .oad files and computes\nper_object_size() — the byte length of the per-object OAD data block.\nWalks the schema: fields outside a COMMONBLOCK contribute their\nButtonType-specific width (4 for Fixed32/Int32/ObjectReference/etc.,\n2 for Fixed16/Int16, 1 for Int8, variable for String, 4 for an XData\nfield with an active conversion action); the COMMONBLOCK marker itself\ncontributes 4 (the common-block offset); fields inside a COMMONBLOCK\ncontribute nothing here (they live in the level's common data area).\n\nCLI now takes an optional 4th arg pointing at a directory of <class>.oad\nfiles; when supplied, every object's OADSize in the output .lvl matches\niff2lvl's byte-for-byte (37/37 on snowgoons). OAD payload bytes are still\nplaceholder zeros pending Phase 2b (actual field value serialization and\ncommon data block population).\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
f89c0c56	author	Will Norris
f89c0c56	added	0
f89c0c56	deleted	0
f89c0c56	files	0
f89c0c56	body	iffwrite is a tool-side IFF writer library with no game callers.\n- git mv wfsource/source/iffwrite/ → wftools/iffwrite/\n- GNUpigs.dep: update build rule to cd to wftools/iffwrite/\n- GNUMakefile.tool: add -I$(WF_DIR)/../wftools so <iffwrite/...>\n  includes resolve for the old C++ tool builds (iffcomp, prep, etc.)\n\nregexp is tool-only too (only wftools/prep/source.cc uses it).\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
fff88f5c	author	Will Norris
fff88f5c	added	0
fff88f5c	deleted	0
fff88f5c	files	0
fff88f5c	body	Engine stubs:\n- scripting_wren.cc/hp — Wren 0.4.0 via //wren\n sigil\n- scripting_wamr.cc/hp — WAMR 2.2.0 via #b64\n sigil\n- scripting_zforth.cc, scripting_forth.hp, zfconf.h — zForth via \ sigil\n- scripting_stub.cc — updated ScriptRouter dispatch for all engines\n\nbuild_game.sh:\n- All engines now on by default (Fennel, QuickJS, zForth, WAMR, Wren)\n- Added WF_PHYSICS_ENGINE flag with legacy/jolt options\n\nwflevels/snowgoons:\n- Restore working IFF from original (5 KB slot expansion broke _Common struct)\n- Regenerate iff.txt via iffdump with correct script slot comments and warnings\n- Add snowgoons.iff.map.yaml documenting all chunk offsets and TOC entries\n\ndocs: compile-time-switches, command-line-switches, plans for Forth/WAMR/Wren/Lua\nscripts: IFF patcher scripts for each engine (Forth, JS, WAMR, Wren)\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
529675b7	author	Will Norris
529675b7	added	0
529675b7	deleted	0
529675b7	files	0
529675b7	body	Vendors zForth (41db72d1), ficl 3.06 (7ff58de3), Atlast (08ff0e1a),\nembed (154aeb2f), libforth (b851c6a2), pForth (63d4a418), and\nnanoFORTH (3b9c3aab) into wftools/vendor/. Adds SHA256s and upstream\nURLs to vendor/README.md.\n\nAlso adds the Wren 0.4.0 and Forth scripting-engine plan documents\n(docs/plans/). Forth plan covers all six WF_FORTH_ENGINE backends,\nfull open-source survey with disqualified rows struck through, per-\nbackend comparison table, sigil (\), bootstrap snippets, and Phase 1\nnow marked done.\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
790dc745	author	Will Norris
790dc745	added	0
790dc745	deleted	0
790dc745	files	0
790dc745	body	Lua is now compiled from wftools/vendor/lua-5.4.8/src/ and linked\nstatically into wf_game. No system liblua5.4-dev is required.\n\nbuild_game.sh changes:\n- LUA_DIR="$VENDOR/lua-5.4.8" alongside WASM3_DIR\n- -I"$LUA_DIR/src" added to CXXFLAGS\n- 32 Lua library TUs compiled via gcc with -DLUA_USE_POSIX\n  -DLUA_USE_DLOPEN (require() / dlopen() support, no readline)\n- -llua5.4 removed from link line; -ldl added (for loadlib dlopen)\n\nscripting_stub.cc: <lua5.4/lua.h> -> <lua.h> (three include lines)\n\ndocs:\n- scripting-languages.md: update Lua runtime column\n- dev-setup.md: remove liblua5.4-dev from apt install list\n- vendor/README.md: add Lua 5.4.8 entry + SHA256\n\nAlso commit all untracked investigation and plan docs written this\nsession: audio, Jolt physics, constraints, mobile port, multiplayer,\nparty game, remove-audio, rest-api-box, compile-time switches, wasm3,\nand the vendor-lua plan itself.\n\nldd wf_game | grep lua → empty (no system Lua at runtime)\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
cfa739c5	author	Will Norris
cfa739c5	added	0
cfa739c5	deleted	0
cfa739c5	files	0
cfa739c5	body	- WF_WASM_ENGINE=none|wasm3 in build_game.sh (default none, zero delta).\n  wasm3 build drops ~136 KB text/data (stripped) onto the binary: mostly\n  m3_compile.c (~67 KB), m3_env/m3_parse for the rest. Upstream's ~65 KB\n  figure is for stripped Cortex-M; on x86_64 -O2 the core is ~100 KB.\n- scripting_wasm3.{hp,cc}: single IM3Environment + IM3Runtime; per-script\n  we strip the `#b64\n` tag, base64-decode, m3_ParseModule + m3_LoadModule\n  + m3_LinkRawFunction for env.read_mailbox / env.write_mailbox, then\n  m3_FindFunction("main") + m3_CallV. i32 or f32 return coerced to Scalar.\n- Dispatcher: scripting_stub.cc's RunScript gains a `#b64\n` arm next to\n  `;` (Fennel) and `//` (JS). The sigil is the full 5 bytes, not bare `#`,\n  because cd.iff still ships TCL shell fragments starting with `##` that\n  must fall through to Lua. Bare `#` is a follow-up (see memory note).\n- Selftest: tiny `(func (export "main") (result i32) i32.const 42)` module\n  embedded via xxd-i; opt-in via WF_WASM_DEBUG=1. Pure-compute because\n  runtime init fires before any actor mailbox is live — host-import\n  coverage comes from real scripts.\n- Snowgoons director ported to WAT (100/99/98 → CAMSHOT), 133 B wasm →\n  180 B base64 → 185 B with header, fits the director's 439 B slot.\n  Patched into both wflevels/snowgoons.iff and wfsource/source/game/cd.iff\n  via scripts/patch_snowgoons_wasm.py (reuses pad_to + chains after Fennel\n  patcher). Player is NOT patched: 77 B slot can't hold any valid wasm\n  module's base64 form (~108 B floor); snowgoons_player.wat is kept as a\n  reference for when a binary iff chunk lands.\n- Vendored wasm3 v0.5.0 (MIT) at wftools/vendor/wasm3-v0.5.0/; hand-\n  authored selftest + snowgoons WAT sources and committed .wasm artifacts\n  at wftools/vendor/wasm3-v0.5.0-wf/. wat2wasm is author-time only; not\n  linked into wf_game.\n\nVerified end-to-end: `WF_WASM_ENGINE=wasm3 bash build_game.sh` links clean\n(~140 KB stripped delta vs none). Startup with WF_WASM_DEBUG=1 prints\n`wasm3: selftest OK (parse/load/call)`. Snowgoons runs with the wasm\ndirector live: read_mailbox(100, actor=9) -> 12, write_mailbox(1021, 12)\nevery frame (matches the Fennel/Lua director's trace exactly).\n\nCo-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
8384f902	author	Will Norris
8384f902	added	0
8384f902	deleted	0
8384f902	files	0
8384f902	body	Adds a third scripting engine alongside Lua and Fennel. Selection is\ncompile-time via WF_JS_ENGINE={none,quickjs,jerryscript}; default `none`\nkeeps today's binary byte-identical. The // sigil routes to whichever JS\nengine is linked in.\n\nVendors QuickJS v0.14.0 (quickjs-ng) and JerryScript v3.0.0 (with a new\nwf-minimal profile). New `scripting_js.hp` declares the plug ABI; the\ntwo engine TUs share read_mailbox / write_mailbox / INDEXOF_* / JOYSTICK_BUTTON_*\nwith the Lua side. LuaInterpreter forwards constants and the // dispatch\narm under #ifdef WF_WITH_JS — no scripting_dispatch refactor yet, that\nwaits for WASM.\n\nVerified live with QuickJS: `quickjs smoke: 1+2 -> 3` at boot.\nJerryScript build path is wired but not yet smoke-tested.\n\nCo-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
-->
