# Tooling & Claude configuration for arcade-faithful conversions

**Status:** DONE — arcade-faithful tooling/skills live under `~/wf-games/.claude`.

## Context

WF + wf-games is converting **38 classic arcade games** (Q✱bert in-flight; Marble Madness, Donkey Kong, Centipede, Asteroids, Boulder Dash, etc. queued) to 3D World Foundry. The engine-side pipeline (Blender → `levcomp-rs` → `iffcomp-rs` → engine, with zForth scripts) is mature and proven on `mm_practice` and Q✱bert.

The **input side is thin**: every game brief in `wf-games/docs/*.md` currently sources its behavior spec from Wikipedia, manuals, and gameplay video — not from the cartridge ROM. That's adequate for shape-level briefs but won't produce faithful timing/feel ([feedback_mm_faithful_means_copy]] / [[feedback_oracle_mirror_first]]). For 38 games across 6 different CPUs and ~10 sound chips, we need ROM archaeology to be a first-class workflow, not a one-off scramble per game.

The single tool used today is MAME (`/usr/games/mame`, allowlisted in settings.local.json). MAME is the right **runtime oracle** but it's only half the toolchain — it doesn't help author the spec from the binary.

Hardware mix across the 38-game roster (drives tool selection):

| CPU | Games | Sound chips |
|-----|-------|------------|
| **6502** (×11) | Asteroids, Centipede, Battlezone, Yars, Pitfall!, Boulder Dash, Crystal Castles, Tempest, Pinball Construction Set, Lode Runner, Vectrex | POKEY, SID, custom |
| **Z80** (×12) | Donkey Kong, Dig Dug, Galaga, Omega Race, Zaxxon, Scramble, Rally-X, Frogger, Qix, Bubble Bobble, Pole Position | AY-3-8910, SN76489/96, YM2203 |
| **6809** (×5) | Q✱bert, Miner 2049er, Joust, Bomberman, Tron | AY-3-8910, SN76496, Williams audio board |
| **68000** (×5) | Marble Madness, Paperboy, Rampage, Prince of Persia, OutRun | YM2151, OKI M6295 |
| **8080** (×1) | Space Invaders | SN76477 + discrete |
| **vector/custom** (×4) | Star Castle, Vectrex titles, Asteroids vector | custom |

Special audio cases: **Votrax SC-01** (Q✱bert phoneme speech — already extracted, sample archive `votrsc01a.7z`); **Ensoniq ES5505** (Rampart).

## Recommended additions

### 1. System tools (apt-installable today)

```
sudo apt install \
  mame-tools \                    # chdman, romcmp, jedutil, ldverify, srcclean
  binutils-m68k-linux-gnu \       # m68k-linux-gnu-objdump for 68k games
  radare2 \                       # multi-arch disassembler (Capstone: 6502/Z80/68k/8080)
  binwalk \                       # ROM-pair carving, entropy/structure scans
  dasm xa65 cc65 \                # 6502 assemble (oracle round-trip), da65 dis
  z80dasm z80asm \                # Z80 disassemble + reassemble
  sox                             # WAV manipulation downstream of mame -wavwrite
```

`cc65` bundles **da65** (6502 disassembler). `radare2` covers Z80/68k/8080/6502 via Capstone and is the workhorse for one-off binary inspection.

### 2. System tools (source / download)

- **Ghidra** ([ghidra-sre.org](https://ghidra-sre.org/)) — heavyweight (~400 MB JRE+jar) but its 6809 processor module is the cleanest path for Q✱bert / Joust / Miner / Bomberman / Tron. Also covers all other target CPUs with one UI. Recommend installing under `~/opt/ghidra-*/`. Optional but high-leverage.
- **f9dasm** (6809 standalone disassembler) — not in apt; small C source on GitHub. Useful as a CLI complement to Ghidra for 6809 ROMs. Build under `~/opt/f9dasm/`.
- **vgmstream-cli** + **libvgm**/**vgm_tag** — for VGM register-stream playback/conversion if we capture chip register logs from MAME `-log` for the SN76489 / AY / YM chips. Build from source; small.
- **Note on PCM extraction policy** — already established in [[project_rom_extraction_copyright]]: re-encoded PCM WAVs are new artefacts and get committed. So `mame -wavwrite` outputs go straight into `assets/arcade-roms/audio/<game>/`.

### 3. In-tree reference material — **vendored under wf-games**

Create per-game reference dirs plus a shared vendored-references pool:

```
wf-games/games/<game>/
  reference.md              # hardware spec, links into shared pool, memmap, RNG, scoring
  disassembly.md            # narrated index of the community-disasm copies in shared pool
  faithfulness.md           # checklist of behaviors to match (speeds, timings, score values)

wf-games/reference/
  mame-drivers/             # vendored MAME driver .cpp/.h snapshots (BSD-3, safe to vendor)
    qbert/gottlieb.cpp …    # one subdir per game with the driver + related audio files
    LICENSE                 # BSD-3-Clause notice copied verbatim from MAME
    SOURCES.md              # git SHA + path of each vendored file from mamedev/mame
  community-disasm/         # permissively-licensed community disassemblies only
    qbert/                  # MIT / CC-BY-SA / public-domain only
    LICENSES.md             # per-disassembly license + upstream URL + author
  hardware-docs/            # public-domain manuals, schematics, datasheets
    LICENSES.md             # per-doc provenance
```

License-tracking discipline (must-have given the vendoring choice):
- **MAME**: BSD-3-Clause — vendor freely; include `LICENSE` and per-file SHA in `SOURCES.md`.
- **Community disassemblies**: vendor *only* if MIT / Apache / BSD / CC-BY / CC-BY-SA / explicit-public-domain. If license is unclear or no-derivatives, **link only** in `reference.md`.
- **Manuals/schematics**: vendor only if publicly distributed by manufacturer or clearly out-of-copyright. Otherwise link.
- ROMs themselves are **never** vendored in wf-games — they live in `WorldFoundry.2026-new-level/assets/arcade-roms/` (same place as the existing `qbert.zip` / `marble.zip`).

`reference.md` per game cites (markdown link, [[feedback_doc_cross_refs_as_links]]):
- The vendored MAME driver under `../../reference/mame-drivers/<game>/`.
- The vendored community disassembly under `../../reference/community-disasm/<game>/`, if license permitted.
- External link to **computerarchaeology.com** / **jrok.com** / KLOV / Wikipedia where vendoring isn't possible.
- For Q✱bert specifically: computerarchaeology.com's Q✱bert disassembly is annotated and downloadable; check its license before vendoring vs linking.

### 4. Claude skills (project-local at `wf-games/.claude/skills/`)

Five new user-invocable skills, each as a single SKILL.md plus an optional helper script. Template: existing `audit-pdf` skill at `WorldFoundry.2026-new-level/.claude/skills/audit-pdf/SKILL.md`.

- **`arcade-rom-inspect`** — given a romset name (e.g. `qbert`, `mappy`), run `unzip -l`, identify CPU+sound chip via MAME `-listcrc` / `-listmedia`, surface the driver source filename, write a starter `reference.md`.
- **`disassemble-rom`** — pick disassembler per CPU (6502→da65, Z80→z80dasm, 6809→Ghidra headless, 68k→m68k-linux-gnu-objdump, generic→radare2). Output annotated `.asm` into `wf-games/games/<game>/disasm/`.
- **`mame-debug-trace`** — invoke MAME `-debug` with a Lua hook to capture register/memory trace across N frames around a behavior trigger ("Coily falls"; "Q✱bert lands on cube"). Output: timestamped log + companion `.md` summarising frame counts, cycle counts, RNG inputs.
- **`sound-rip`** — `mame -wavwrite` for each game's known SFX, plus VGM chip-register dump where MAME supports it (AY/SN76489/SID/YM). Output WAVs to `assets/arcade-roms/audio/<game>/` per the extraction-copyright policy.
- **`faithfulness-spec`** — from MAME driver + reference docs, scaffold a `faithfulness.md` checklist (speeds in pixels/frame → revs/sec, timer values, score table, RNG behavior, lives, level progression).

### 5. Custom subagents (`wf-games/.claude/agents/`)

Two specialised subagent types that handle the open-ended research half of conversion. Both live in **wf-games** per your scope decision; see §11 below for how to reach them from WorldFoundry.

- **`rom-analyst`** (`wf-games/.claude/agents/rom-analyst.md`) — answers timing/behavior questions ("what's Coily's fall speed in cycles?") by combining `mame -debug` traces with disassembly + vendored MAME driver. Tools: Bash, Read, Grep, WebFetch.
- **`arcade-historian`** (`wf-games/.claude/agents/arcade-historian.md`) — researches authoritative external sources for a game's behavior spec (KLOV, computerarchaeology, MAME source, oral history, design retrospectives). Produces a citation-rich `reference.md`. Tools: WebFetch, WebSearch, Read.

Each agent .md is ~80 lines: frontmatter (name, description, allowed tools) + system prompt covering its specialty and the vendored-references layout.

### 6. Permission additions (`wf-games/.claude/settings.local.json` — new file)

Currently wf-games has only `settings.json` (no permissions). Add a `.local.json` allowlist mirroring WorldFoundry's pattern:

```jsonc
{
  "permissions": {
    "allow": [
      "Bash(/usr/games/mame *)",
      "Bash(unzip *)", "Bash(7z *)",
      "Bash(radare2 *)", "Bash(r2 *)", "Bash(rabin2 *)", "Bash(rasm2 *)",
      "Bash(da65 *)", "Bash(dasm *)", "Bash(xa *)", "Bash(z80dasm *)", "Bash(z80asm *)",
      "Bash(m68k-linux-gnu-objdump *)", "Bash(binwalk *)",
      "Bash(chdman *)", "Bash(romcmp *)",
      "Bash(sox *)", "Bash(ffmpeg *)",
      "WebFetch(domain:computerarchaeology.com)",
      "WebFetch(domain:jrok.com)",
      "WebFetch(domain:arcade-museum.com)",
      "WebFetch(domain:atariarchives.org)",
      "WebFetch(domain:atariage.com)",
      "WebFetch(domain:retrocomputing.stackexchange.com)",
      "WebFetch(domain:spritesheet.org)",
      "WebFetch(domain:videogamehistory.org)",
      "WebFetch(domain:wiki.arcadeotaku.com)"
    ]
  }
}
```

### 7. wf-games CLAUDE.md (new file)

wf-games has none today. Add one (~30 lines) covering:
- Stack: docs-only repo of game briefs + investigations
- Per-game directory convention (`docs/<game>.md` brief → `games/<game>/{reference,disassembly,faithfulness}.md`)
- ROMs live in WorldFoundry repo, not here
- Faithfulness policy: mirror MAME driver behavior first, deviate only after a working oracle round-trip ([[feedback_oracle_mirror_first]] / [[feedback_mm_faithful_means_copy]])
- Pointer to `rom-analyst` and `arcade-historian` subagents

### 8. WorldFoundry CLAUDE.md additions (~15 lines)

Append an "Arcade ROM handling" section:
- ROMs live in `assets/arcade-roms/<game>.zip`; never extracted into repo
- PCM extraction policy: re-encoded WAVs are committed under `assets/arcade-roms/audio/<game>/` ([[project_rom_extraction_copyright]])
- MAME is the runtime oracle; `mame-debug-trace` skill for register/timing capture
- Per-game reference docs live in wf-games repo, not here

### 9. Hooks (none new required)

Existing `python-tui-lib/hooks/` covers plan-first, git-add-guard, py-syntax, shell-strict, commit-checklist. Nothing arcade-specific warrants a new hook — the skill/agent layer is sufficient.

### 10. Cross-repo reachability note

You chose "All in wf-games" for skills + agents. Important consequence: Claude Code's `.claude/skills/` and `.claude/agents/` are resolved relative to the **current working directory**. So:

- Sessions started in `/home/will/wf-games/` → all 5 skills + 2 agents available.
- Sessions started in `/home/will/WorldFoundry.2026-new-level/` → **none** of them available by default.

Most actual conversion *implementation* happens in WorldFoundry (Q✱bert engine work). To make them callable from there too, recommended one-time setup after the wf-games skills/agents are written:

```bash
ln -s ~/wf-games/.claude/skills ~/WorldFoundry.2026-new-level/.claude/skills/arcade
ln -s ~/wf-games/.claude/agents ~/WorldFoundry.2026-new-level/.claude/agents/arcade
```

(Or duplicate the files if you prefer no symlinks.) Without this, you'll have to do disassembly/trace work from a wf-games shell and write results into wf-games, then switch back. That's workable if you treat wf-games as the "research" workspace and WorldFoundry as the "implementation" workspace — but call it out.

### 11. Explicitly not recommended right now

- **Custom MCP for MAME-debug** — would be powerful (long-lived MAME-debug Lua session as a stateful interface) but is a multi-day build. Defer until two or three skill-based MAME traces have proved the workflow.
- **IDA Pro / Binary Ninja** — commercial; Ghidra + radare2 are sufficient.
- **Per-CPU emulator-with-debugger projects** (visual6502 etc.) — niche; MAME-debug covers the same ground.

## Critical files to add/modify

| File | Action |
|------|--------|
| `wf-games/CLAUDE.md` | **create** |
| `wf-games/.claude/settings.local.json` | **create** with permissions block above |
| `wf-games/.claude/skills/{arcade-rom-inspect,disassemble-rom,mame-debug-trace,sound-rip,faithfulness-spec}/SKILL.md` | **create** (5 skills) |
| `wf-games/.claude/agents/{rom-analyst,arcade-historian}.md` | **create** (2 subagents, wf-games-scoped) |
| `wf-games/reference/{mame-drivers,community-disasm,hardware-docs}/` | **create** dir scaffolds + LICENSES.md per the vendoring policy |
| `wf-games/reference/mame-drivers/qbert/` | **populate first** as proof-of-vendoring with Gottlieb driver + BSD-3 LICENSE |
| `WorldFoundry.2026-new-level/.claude/skills/arcade` → symlink to `~/wf-games/.claude/skills` | **create symlink** (or duplicate) |
| `WorldFoundry.2026-new-level/.claude/agents/arcade` → symlink to `~/wf-games/.claude/agents` | **create symlink** (or duplicate) |
| `WorldFoundry.2026-new-level/CLAUDE.md` | **append** "Arcade ROM handling" section |
| `WorldFoundry.2026-new-level/.claude/settings.local.json` | **append** disassembler-bash + WebFetch domains to permissions allowlist |
| (system) | `apt install` block from §1; manual install of Ghidra (~400 MB) + f9dasm + vgmstream-cli under `~/opt/` |

## Verification

End-to-end smoke test once installed:

1. `/arcade-rom-inspect qbert` → produces `wf-games/games/qbert/reference.md` populated with CPU=6809, sound=AY-3-8910+Votrax SC-01, MAME driver = `gottlieb.cpp`, mem map link, plus a link to computerarchaeology.com's Q✱bert disassembly.
2. `/disassemble-rom qbert qb-rom0.bin` → emits annotated `wf-games/games/qbert/disasm/qb-rom0.asm` via Ghidra-headless or f9dasm.
3. `/mame-debug-trace qbert "coily-falls"` → captures 60 frames of PC + key registers around the coily-fall event; output usable to back-compute Coily's per-frame movement.
4. `/sound-rip qbert "swearing"` → produces a WAV in `assets/arcade-roms/audio/qbert/swearing.wav` that matches what's in the running cabinet.
5. Use `rom-analyst` subagent to answer: "What is Coily's exact horizontal speed in cubes/sec at level 1?" — should respond with a number derived from disassembly + trace, citing both.

If those five work end-to-end on Q✱bert (which is already mid-conversion), the same workflow scales to the remaining 37 games as they enter active conversion.

## User-confirmed decisions

- **Skill scope**: all skills + agents live in `wf-games/.claude/`. Cross-repo reachability handled via symlinks (§10).
- **Ghidra**: install under `~/opt/`. Best 6809 coverage for Q✱bert, Joust, Miner, Bomberman, Tron.
- **Subagents**: build both `rom-analyst` and `arcade-historian` .md files now (not deferred).
- **References**: vendor MAME drivers (BSD-3) and any permissively-licensed community disassemblies under `wf-games/reference/`, with strict per-file license tracking in `LICENSES.md` / `SOURCES.md`.
