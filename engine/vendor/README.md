# Vendored third-party sources

Checked-in mirrors of third-party libraries that get statically linked into the
engine. The CD / embedded target has no runtime filesystem, so everything ships
as source and is linked in at build time.

## Contents

| Directory | Version | License | Upstream |
|-----------|---------|---------|----------|
| `quickjs-v0.14.0/` | 0.14.0 (2025-04-13) | MIT | https://bellard.org/quickjs/ |
| `jerryscript-v3.0.0/` | 3.0.0 | Apache-2.0 | https://github.com/jerryscript-project/jerryscript/releases/tag/v3.0.0 |
| `wasm3-v0.5.0/` | 0.5.0 | MIT | https://github.com/wasm3/wasm3/releases/tag/v0.5.0 |
| `lua-5.4.8/` | 5.4.8 | MIT | https://www.lua.org/ftp/lua-5.4.8.tar.gz |
| `zforth-41db72d1/` | commit `41db72d1` | MIT | https://github.com/zevv/zForth |
| `ficl-3.06/` | ficl306 tag | BSD-2-Clause | https://github.com/jwsadler58/ficl |
| `atlast-08ff0e1a/` | commit `08ff0e1a` | Public Domain | https://github.com/Fourmilab/atlast |
| `embed-154aeb2f/` | commit `154aeb2f` | MIT | https://github.com/howerj/embed |
| `libforth-b851c6a2/` | commit `b851c6a2` | MIT | https://github.com/howerj/libforth |
| `pforth-63d4a418/` | commit `63d4a418` | 0-clause BSD (PD) | https://github.com/philburk/pforth |
| `nanoforth-3b9c3aab/` | commit `3b9c3aab` | MIT | https://github.com/chochain/nanoFORTH |
| `wren-0.4.0/` | 0.4.0 | MIT | https://github.com/wren-lang/wren/releases/tag/0.4.0 |
| `jolt-physics-5.5.0/` | 5.5.0 | MIT | https://github.com/jrouwe/JoltPhysics/releases/tag/v5.5.0 |
| `miniaudio-0.11.25/` | 0.11.25 (2026-03-04) | MIT-0 / Public Domain | https://github.com/mackron/miniaudio |
| `tsf/` | tsf v0.9 + tml v0.7 | Public Domain | https://github.com/schellingb/TinySoundFont |

## Tarball SHA256

- `jolt-physics-5.5.0.tar.gz` — `b2dbc3c41398f22b2914112a962f286643d1c74bac8418eae772e267392c1313` (upstream GitHub tarball)

- `jerryscript-v3.0.0.tar.gz` — `4d586d922ba575d95482693a45169ebe6cb539c4b5a0d256a6651a39e47bf0fc` (upstream GitHub tarball)
- `wasm3-v0.5.0.tar.gz` — `b778dd72ee2251f4fe9e2666ee3fe1c26f06f517c3ffce572416db067546536c` (upstream GitHub tarball)
- `lua-5.4.8.tar.gz` — `4f18ddae154e793e46eeab727c59ef1c0c0c2b744e7b94219710d76f530629ae` (upstream www.lua.org tarball)
- `zforth-41db72d1.tar.gz` (commit `41db72d165c1539d57f3f79970fc57ea881a79dc`) — `34c578ec2aa979786387e5f244fa933b6b040f9a6f18888ed2cc4273ef06df8d`
- `ficl-3.06.tar.gz` (ficl306 tag, commit `7ff58de370ffdfc066daceffbcd2341ae07235a5`) — `ac3bc105cab8f770dfbc2b3bcd7ca258da25cae638e790d9b0f07dc3976ebbe7`
- `atlast-08ff0e1a.tar.gz` (commit `08ff0e1aa90310e401510e843540786ac97d2f4f`) — `807ac62e966e6dc11f3e360beceb670103ddb6542766e204c80c11650e311e10`
- `embed-154aeb2f.tar.gz` (commit `154aeb2faba01106c2324fb7b46cf5fe236e6a81`) — `4312df38dc216c65d8acb2aec96c73c63657c22657504802d311061af21861c6`
- `libforth-b851c6a2.tar.gz` (commit `b851c6a25150e7d2114804fc8712664c6d825214`) — `26271b77ef930799e399157d65f50f6dc2c44149314d5f206c852bd2639669bc`
- `pforth-63d4a418.tar.gz` (commit `63d4a4181b39dda123bd63fed4c56bc8e3d47b1c`) — `239a32e02cacc3b52702b939a59c4eca599cb23eac2052055d819736aa22e218`
- `nanoforth-3b9c3aab.tar.gz` (commit `3b9c3aab053b7082c695af5a600f6e55021a2320`) — `e2795764ab9aae91c1c72bf59fe6f6780fdb2dd2d6d7b3787fbea577d4038acc`
- `miniaudio-0.11.25/miniaudio.h` — `ac7af4de748b7e26b777f37e01cee313a308a7296a3eb080e2906b320cc55c89` (fetched from mackron/miniaudio main 2026-04-17)
- `tsf/tsf.h` — `70d55963c98f60ebb81518eaa1f25d46888d5180eb5f5289fd6b74ffc177d197` (fetched from schellingb/TinySoundFont main 2026-04-17)
- `tsf/tml.h` — `93257db259e0efb2ea2037d7157841bec8cb4a2d7986286e43c8090705326546` (fetched from schellingb/TinySoundFont main 2026-04-17)

## Runtime assets (not committed)

| File | Notes |
|------|-------|
| `wfsource/source/game/TimGM6mb.sf2` | Dev soundfont (GPL, 5.7 MB). Download via `apt-get download timgm6mb-soundfont && dpkg-deb -x *.deb . && mv usr/share/sounds/sf2/TimGM6mb.sf2 wfsource/source/game/`. Ship target will use a custom WF-subset SF2. |

## Notes

- Optional. Only one JS engine (or none) links into a given build. Selection
  happens in `wftools/wf_engine/build_game.sh` via `WF_JS_ENGINE`.
- Optional. Only one wasm engine (or none) links into a given build. Selection
  happens in `wftools/wf_engine/build_game.sh` via `WF_WASM_ENGINE`.
- Optional. Only one Forth engine (or none) links into a given build. Selection
  happens in `wftools/wf_engine/build_game.sh` via `WF_FORTH_ENGINE`.
  Note: atlast source is under `atlast-<sha>/atlast-64/`; zForth core is under
  `zforth-<sha>/src/zforth/`.
- See `docs/plans/2026-04-14-pluggable-scripting-engine.md` for the JS dispatch
  contract and the JerryScript `wf-minimal` profile,
  `docs/plans/2026-04-14-wasm3-scripting-engine.md` for the wasm3 plan, and
  `docs/plans/2026-04-14-forth-scripting-engine.md` for the Forth backends.
