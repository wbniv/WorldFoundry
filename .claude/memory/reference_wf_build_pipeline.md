---
name: World Foundry level build pipeline
description: Blender→.lev→.iff via 4-stage Rust toolchain (iffcomp→levcomp→textile→iffcomp). Driver script lives at wftools/wf_blender/build_level_binary.sh.
type: reference
originSessionId: 1bb8f4e2-9146-4504-8289-793c96be779b
---
**Driver:** `wftools/wf_blender/build_level_binary.sh <level-name>`. Runs the four stages in order:

1. `iffcomp-rs` (`wftools/iffcomp-rs/target/release/iffcomp`): text-IFF `.lev` → binary `.lev.bin`
2. `levcomp-rs` (`wftools/levcomp-rs/target/release/levcomp`): `.lev.bin` → `.lvl` + asset.inc + `.iff.txt` + `.ini`
3. `textile-rs` (`wftools/textile-rs/target/release/textile`): `.ini` → `palN.tga` + `RoomN.{tga,ruv,cyc}` + `Perm.{tga,ruv,cyc}`
4. `iffcomp-rs` again: `.iff.txt` → final `<name>.iff` (sibling of the level dir, in `wflevels/`)

**One-time setup:** `cargo build --release` in each of the three crates under `wftools/`.

**Engine binary:** `engine/build_game.sh` produces `engine/wf_game`. Feature flags via env vars: `WF_LUA_ENGINE`, `WF_FORTH_ENGINE` (default `zforth`), `WF_JS_ENGINE`, `WF_WASM_ENGINE`.

**Run a level:** `engine/wf_game -L wflevels/<name>.iff`.

**Reference template for a complete modern level:** `wflevels/snowgoons-blender/` — has `.blend`, `.lev`, per-mesh `.iff` files, textures, and embedded Forth scripts in OBJ Script fields. Use this as the structural model, not the legacy Max-pipeline `wflevels/minecart/`.
