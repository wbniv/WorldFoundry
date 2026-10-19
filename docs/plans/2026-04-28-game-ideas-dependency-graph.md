# Plan: dependency graph, table, and order across `docs/game-ideas/` + level-construction tooling brainstorm

## Context

The `docs/game-ideas/` directory now contains **32 conversion briefs** (verified by direct `ls`). The README has tier groupings and a "my picks" recommendation, but **no centralised view of which briefs depend on which**.

Most briefs are *not* standalone — they explicitly reuse engine subsystems introduced by other briefs. Without a dependency graph, the natural reading is "pick three Tier-1 briefs and ship them" — under-using the reuse story. A dependency-aware ordering exposes:
- A small set of *foundational* briefs that unlock many Tier-2/Tier-3 briefs as cheap content extensions
- *Parallel tracks* that don't share subsystems and can be built simultaneously
- *Combinatorial wins* where two seemingly unrelated briefs share a subsystem worth pulling forward

### Deliverables

1. **Mermaid graph(s)** at the top of `docs/game-ideas/README.md` showing brief→brief and subsystem→brief dependencies.
2. **A dependency table** — fully enumerated.
3. **An idealised implementation order** — recommended waves / parallel tracks.
4. **Tooling brainstorm** — skills, Blender plugins, pluggable-LLM ideas, in a separate investigation doc with a pointer from the README.

## Verified inventory (32 briefs)

`asteroids`, `bomberman`, `boulder-dash`, `bubble-bobble`, `centipede`, `crystal-castles`, `dig-dug`, `donkey-kong`, `frogger`, `galaga`, `geometry-wars`, `joust`, `lode-runner`, `marble-madness`, `miner-2049er`, `omega-race`, `paperboy`, `pinball-construction-set`, `pole-position-outrun`, `prince-of-persia`, `qbert`, `qix`, `rampage`, `rampart`, `space-invaders`, `super-off-road`, `tempest`, `tron-light-cycles`, `vectrex`, `yars-revenge`, `zaxxon`, `zork-adventure`.

Plus 12 engine-subsystem **investigations** at `docs/game-ideas/investigations/2026-04-28-*.md`.

## Strategy: parallel subagent fan-out + serial synthesis

32 briefs at ~250 lines each is too much for one context to read deeply *and* synthesise. The plan splits the work into discrete subtasks. The dependency-extraction subtask is parallel-fan-out (4 Explore agents, 8 briefs each); everything downstream is serial synthesis from the structured outputs.

---

## Subtasks

### Subtask 1 — Extract dependency edges from all 32 briefs (parallel fan-out)

Spawn **4 Explore agents in parallel**, each reading a balanced group of 8 briefs. Groupings are chosen so each agent's set is internally cross-referenced (the agent can resolve "reuses Asteroids' X" by reading both Asteroids and the consumer in the same prompt).

| Group | Briefs (8 each) | Theme |
|---|---|---|
| **A** | `joust`, `asteroids`, `omega-race`, `geometry-wars`, `yars-revenge`, `centipede`, `galaga`, `space-invaders` | Foundational HUD/SFX/cross-actor + ship-controller + aimable-shot families |
| **B** | `pole-position-outrun`, `super-off-road`, `tron-light-cycles`, `boulder-dash`, `dig-dug`, `lode-runner`, `bomberman`, `rampart` | Vehicle controllers + grid-harness family |
| **C** | `donkey-kong`, `rampage`, `prince-of-persia`, `bubble-bobble`, `marble-madness`, `paperboy`, `qbert`, `miner-2049er` | Climb-mode + side-scroll + Tier-1 platformers |
| **D** | `tempest`, `zaxxon`, `crystal-castles`, `qix`, `vectrex`, `pinball-construction-set`, `frogger`, `zork-adventure` | Specialty cameras + Tier-3 novel-subsystem briefs |

**Each agent's output (strict shape):**

A markdown response with three sections:

1. **Per-brief rows** (8 rows):
   ```
   | Brief | Tier | Introduces | Reuses (from) | Standalone est. | With-deps est. | Closest fork |
   ```

2. **Edge list** in the form `source-brief --(subsystem-name)--> consumer-brief`. One edge per line, no prose. Edges where the source is *outside this group* are still listed; main-agent will resolve them across groups.

3. **Investigation references** — every `docs/game-ideas/investigations/2026-04-28-*.md` file the brief points at, mapped to the brief that points at it.

The agent prompt explicitly tells it to *quote the brief's own claims* and not infer beyond them. Exact wording in the agent prompt: "Do not invent edges. If a brief says 'reuses Joust's HUD overlay', that's an edge. If a brief looks like it could in principle reuse something, that's not an edge."

**Verification:** Aggregate all 4 agents' edge lists. Every edge `A --(X)--> B` must have `A` and `B` both in the verified inventory of 32 briefs (Spy Hunter / Battlezone are unbriefed and may appear as targets only in narrative text, not graph edges). Sanity-check the count: roughly 50–80 edges expected across 32 briefs.

### Subtask 2 — Build the master subsystem catalog (serial synthesis)

From Subtask 1's aggregated outputs, derive **Table B — per-subsystem**:

```
| Subsystem | Introduced by | Consumed by (briefs) | Investigation plan |
```

Expected ~30 subsystem rows. This is the table that answers "what one piece of engine work unlocks the most briefs?"

Sanity rule: every cell in "Introduced by" must be a brief from the 32; every cell in "Consumed by" must be a brief from the 32; every cell in "Investigation plan" must be one of the 12 verified investigation files (or "—" if no plan exists yet).

### Subtask 3 — Build the per-brief table (serial synthesis)

**Table A — per-brief (32 rows):** assemble from the 4 agent outputs. Same column set as the agents emitted.

Cross-check Table A's "Reuses" column against Table B's "Consumed by" column: every reuse claim in A must round-trip to a row in B.

### Subtask 4 — Design Mermaid graphs (serial synthesis)

A single 32-node DAG is unreadable. Split into:

1. **Master overview** — every brief, color-coded by tier, edges only for *primary* dependencies (the brief's most-load-bearing reuse). One Mermaid block.
2. **Family subgraphs** — one Mermaid block each:
   - Joust EXT family (HUD + SFX + `read-mailbox-of`)
   - Ship-controller family (Asteroids root)
   - Aimable-shot family (Centipede root)
   - Vehicle family (Pole Position root, Tron parallel)
   - Grid harness family (Boulder Dash root)
   - Climb-mode family (Donkey Kong root)
   - Side-scroll camera family (Prince of Persia / Lode Runner / Bubble Bobble cluster)
   - Specialty / engine-novel briefs (Tempest, Zaxxon, Vectrex, Crystal Castles, Qix, Pinball, Zork)

Final count of Mermaid blocks: ~9. Each block is small (≤15 nodes) and renders cleanly on phone-width.

**Verification:** Render `task md -- README.md` after every Mermaid block insertion; visually confirm in browser. If any block fails to render, fix syntax before the next insertion.

### Subtask 5 — Write idealised-order narrative (serial synthesis)

A short prose section under the graphs. Outline:

- **Wave 0 (foundations, parallel tracks)** — Joust, Boulder Dash, Donkey Kong, Asteroids, Centipede, Pole Position+OutRun. Six independent foundational projects.
- **Wave 1 (cheap extensions of Wave 0)** — Dig Dug, Galaga, Omega Race, Super Off Road, Lode Runner, Rampage, Tron Light Cycles. Each ≤ 1 week if Wave 0 has shipped.
- **Wave 2 (multi-foundational)** — Bomberman, Bubble Bobble, Prince of Persia, Geometry Wars, Yars' Revenge, Frogger, Space Invaders. Each requires 2+ Wave-0 subsystems.
- **Wave 3 (engine-novel showcase)** — Tempest, Zaxxon, Crystal Castles, Qix, Vectrex platform-bundle, Pinball, Zork/Adventure. Genuine new engine work.

Each wave explicitly cites which Wave-0 briefs it builds on. Each is presented as a *menu*, not a serial roadmap.

The existing "my picks if I had to choose three" section in the README stays — it's a reasonable user-facing default; this is the deeper analytical view.

### Subtask 6 — Edit README.md (single Edit/Write call)

Insert new sections at the top, between the existing "Working hub" intro and the Tier 1 heading:

1. Existing "Working hub" intro paragraph — unchanged.
2. **NEW:** "Dependency overview" — master Mermaid + parallel-track narrative.
3. **NEW:** "Dependency tables" — Table A + Table B, each inside `<details>` so the at-a-glance flow is preserved.
4. **NEW:** "Per-family subgraphs" — the ~8 thematic Mermaid blocks.
5. **NEW:** "Tooling that would accelerate this" — one paragraph + pointer to the new investigation doc.
6. Existing tier sections, "my picks", "document layout", "IP / licensing" — unchanged. The "document layout" section gets a one-line addition mentioning the new sections.

**Verification:** `git diff docs/game-ideas/README.md` — confirm no Tier-1/2/3 bullet content was modified, only inserted-above. Run `task md -- README.md` and visually verify all Mermaid blocks render and all internal `[link](file.md)` resolve.

### Subtask 7 — Write tooling investigation doc

New file: `docs/investigations/2026-04-28-level-construction-tooling.md`. Same shape as `2026-04-28-vr-ar-headset-support.md`. Contents:

1. **Context** — current snowgoons-blender pipeline (mesh export, IFF compile, texture packing automated; layout, actor placement, Forth scripts, tuning manual). Quote `2026-04-19-snowgoons-build-pipeline.md` rather than re-derive.
2. **The four authoring seams**:
   - Seam 1: Brief → Blender scene whitebox (highest leverage; 10–20h of Blender graft per stage today)
   - Seam 2: Bestiary prose → zForth scripts (well-bounded; briefs already include illustrative Forth)
   - Seam 3: Tuning iteration (play telemetry → suggested constant updates)
   - Seam 4: Asset gen (out of scope until Zork/Adventure's runtime image-gen subsystem exists)
3. **Concrete deliverables ranked by leverage:**
   - `/wf-build-level` Claude Code skill (consumes a brief, lands `.blend` + `.lev` skeleton, runs `build_level_binary.sh`)
   - `/wf-author-script` skill (bestiary prose → zForth using mailbox name table from `wfsource/source/mailbox/`)
   - Blender plugin "Brief import" operator (extends `wftools/wf_blender/operators.py`)
   - **Pluggable LLM backend** — `WF_LLM_PROVIDER=anthropic|openai|local` env var; prompt templates in `wftools/wf_blender/llm_prompts/`. Pattern lifted from parking-space's homoiconic / dispatch-table approach.
   - Tuning-loop harness (Phase D)
   - Asset gen (Phase E, depends on Zork)
4. **Format note** — parking-space rejected `iffcomp` as a scripting format (FOURCC verb names, no native control flow) and chose multi-bracket LISP. The relevant *pattern* (homoiconic source as artifact, dispatch-table extensibility, record-edit-replay) applies to a "level-as-text" pipeline. Don't propose adopting parking-space's LISP for WF level authoring — but borrow the patterns.
5. **Risks** — LLM-generated geometry will need designer-tweaks-after-generation; pluggable provider must not become an excuse for prompt drift across providers; new Blender plugin code must not break the existing snowgoons workflow.
6. **Phased plan** — Phases A → E, each with acceptance criteria and est. effort.

**Verification:** `task md -- 2026-04-28-level-construction-tooling.md`; visually verify in browser. Section headers parse, file path references resolve.

---

## Critical files

- **`docs/game-ideas/README.md`** — main edit target.
- **`docs/investigations/2026-04-28-level-construction-tooling.md`** — new file.
- **`docs/game-ideas/<game>.md`** for `<game>` ∈ all 32 — read-only at execute time, by parallel Explore agents in Subtask 1.

## Reuse / existing tooling to lean on

- Mermaid blocks render in `task md --` (verified by recent commit `1514212`).
- `docs/investigations/2026-04-28-engine-capabilities-survey.md` — quote rather than restate engine state.
- `docs/game-ideas/investigations/2026-04-28-80s-game-conversion-candidates.md` — pre-existing snapshot of the same shortlist; verify the new graph doesn't contradict it. If contradictions surface, the README graph wins (the snapshot is older).
- `wftools/wf_blender/{operators,panels,export_level}.py` — natural extension points for the brief-import operator.
- `docs/investigations/2026-04-19-snowgoons-build-pipeline.md` — canonical end-to-end build pipeline reference.

## Verification (cross-cutting)

1. **Inventory complete.** `ls docs/game-ideas/*.md | wc -l` returns 33 (32 briefs + README). Every brief is in Table A.
2. **No phantom edges.** Every `A → B` Mermaid edge has `A` and `B` as actual files in `docs/game-ideas/`.
3. **Mermaid renders.** `task md -- README.md` opens in browser; every block renders without syntax errors; phone-width viewport remains usable.
4. **Internal-link integrity.** Every `[link](file.md)` in new sections resolves.
5. **README still scans top-to-bottom.** First-time reader gets "Working hub" → high-level overview → tier sections → "my picks" without the dependency tables burying the flow (tables are in `<details>`).
6. **Existing tier-list bullets unchanged.** `git diff` confirms only inserts above, plus a small "tooling pointer" addition.
7. **`task md --` runs after the README and the tooling-doc edits** — per the standing memory rule.
8. **Cross-doc consistency.** Tooling doc's Seam 1 references real brief filenames; README's tooling-pointer paragraph references the new investigation doc by relative path.

## Open question for the user

**Tooling-brainstorm placement.** Recommended: separate investigation doc (`docs/investigations/2026-04-28-level-construction-tooling.md`) with a one-paragraph pointer from the new README "Tooling that would accelerate this" section. Alternative: inline at the bottom of the README. Recommendation rationale: audience separation (README is "browse and pick a level"; tooling doc is "decide what engineering investments accelerate authoring"); existing investigations follow this pattern.
