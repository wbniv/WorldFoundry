# Investigation: Level-construction tooling — skills, Blender plugins, pluggable LLM, licensed-asset sourcing

**Date:** 2026-04-28
**Status:** Survey + scoped plan. Not committed; intended as the reference doc for "what tooling investments accelerate brief → playable level for World Foundry?" The companion to the dependency overview at the top of `docs/game-ideas/README.md`.
**Depends on:** `docs/investigations/2026-04-19-snowgoons-build-pipeline.md` (canonical end-to-end build pipeline reference), `docs/investigations/2026-04-28-engine-capabilities-survey.md` (engine profile).
**Related:** `docs/game-ideas/README.md` (32-brief catalog with dependency graph), `wftools/wf_blender/` (existing Blender plugin).

## Context

The dependency overview in `docs/game-ideas/README.md` enumerates 32 conversion briefs and identifies six foundational projects whose engine subsystems unlock everything else. That answers *what to build*. This doc answers the orthogonal question: *how do we build it faster than 10–20 hours of hand-graft per Blender stage, per brief?*

The current pipeline (validated 2026-04-19, reproducible — see `2026-04-19-snowgoons-build-pipeline.md`) is:

```
Blender scene (manual layout)
  → wf_blender export (.lev + per-mesh .iff)
  → build_level_binary.sh (iffcomp-rs / levcomp-rs / textile-rs / iffcomp-rs)
  → snowgoons.iff (LVAS-rooted)
  → wf_game -L → playable
```

What's already automated: mesh export, IFF compilation (`iffcomp-rs`), texture packing (`textile-rs`), asset bundling (`levcomp-rs`), engine boot.

What's manual: level layout (Blender geometry), actor placement + camera framing, zForth script writing, tuning constant tweaking, **and asset sourcing — currently nothing systematic, just whatever is to hand**.

This investigation enumerates five seams where tooling could land, ranks them by leverage, and proposes phased deliverables.

---

## The five authoring seams

### Seam 1 — Brief → Blender-scene whitebox

**Today:** A designer reads a brief (e.g. `donkey-kong.md`'s "Level structure (room graph)" + "Bestiary" sections), opens Blender, manually creates cube placeholders for each room, names them, attaches OAD schemas, places cameras, sets actor positions. ~10–20 hours per stage; longer for content-heavy briefs (Marble Madness, Lode Runner).

**Required-objects floor.** Before any brief-specific content, every WF level needs a fixed set of mandatory objects without which the engine won't boot. From the canonical snowgoons-blender reference (`wflevels/snowgoons-blender/snowgoons.lev`) and `wfsource/source/oas/` schemas, the mandatory set is:

| Class (OAS) | Role | Snowgoons example name(s) | Cardinality |
|---|---|---|---|
| `levelobj` | Level root container; holds globals (palette, asset table, level metadata) | `Level` | exactly 1 |
| `director` | Per-tick driver — runs the level's master script | `Director` | exactly 1 |
| `room` | Room-graph node; every actor is parented to a room | `Room01`, `Room02` | ≥ 1 (one per logical area) |
| `camera` | Active rendering camera; reads its target/CamShot from a mailbox | `Camera` | ≥ 1 |
| `camshot` | Camera-anchor object; the engine asserts a valid `CamShot` index is written to mailbox 1021 within 5 frames or `movecam.cc:885` fires (per `docs/level-building.md:63`) | `CamShot01`, `GMACamShot` | ≥ 1 |
| `target` | Camera look-at anchor (paired with camshot for follow-cameras) | `GMACamTar`, `Target01` | ≥ 1 (typically one per camshot that needs aim) |
| `light` | Scene illumination; multiple supported | `Omni01`, `Omni02` | ≥ 1 |
| `matte` | Skybox / background billboard | `Matte` | ≥ 1 (a level without a matte renders bare clear-color) |

Plus the conditional-but-near-universal set:

| Class (OAS) | Role | When |
|---|---|---|
| `actboxor` | Activate-Box (OR semantics) — trigger volume that writes a mailbox on entry; canonical use is camera-switch on-room-cross | Whenever the level switches CamShots (almost always) |
| `player` | Player actor (one per player slot) | Every interactive level |
| `tool` | Pickup item with mailbox-driven activation | Most action levels |
| `statplat` / `platform` / `enemy` / `missile` / `shadow` / `target` / `generator` / `warp` | Gameplay primitives | Per-brief |

The user mentioned a "cambox" earlier; I do not see a `cambox` class in `wfsource/source/oas/objects.h` (the canonical KIND enum) — best guess is the user is referring to the **camera scaffolding cluster** that *together* forms a camera setup: one `camera` + one `camshot` + one `target` + the `actboxor` that activates them. If there is a specific "cambox" object I'm missing, treat my listing as a draft and correct before any code lands.

**Opportunity.** A skill / Blender operator that consumes a brief Markdown file and emits a `.blend` scaffold:

- **Step 1 — required-objects floor.** Lay down `Level`, `Director`, `Matte`, plus one default `Camera` + `CamShot01` + `Target01` + `Omni01` light. This step is brief-independent — it's the same 7-object floor every WF level needs. The Blender operator can do this in one fixed pass before reading the brief.
- **Step 2 — room-graph from the brief's "Level structure" table.** Each row → one `room` object + one Blender collection at the row's coordinates (or default-grid if coordinates aren't given). Each `room` gets a placeholder cube boundary mesh.
- **Step 3 — per-room camera scaffolding.** For each room with a stated camera (e.g. fixed overhead, side-scroll), emit one additional `camshot` + `target` + `actboxor` cluster, the `actboxor` sized to the room AABB and configured to write the matching `CamShot` index on entry.
- **Step 4 — bestiary actors.** One `enemy` / `tool` / `missile` / etc. per bestiary entry, named to match the brief, with OAD schema attached based on the entry's archetype tag (player / enemy / projectile / pickup / scenery). Position from the brief's `Mailbox protocol` or `Bestiary` table when given; default to room-center grid otherwise.
- **Step 5 — defer geometry to the designer.** The mesh data for each `statplat` is a placeholder cube; the designer refines per-brief.

Steps 1–4 are mechanical (the brief literally specifies them); Step 5 is where the designer's expertise lands. Even a 50%-correct scaffold collapses 10–20 hours of file-creation drudgery into 1–2 hours of geometry refinement.

This is the **highest-leverage seam**.

### Seam 2 — Bestiary prose → zForth scripts

**Today:** The brief's `bestiary.md` (or inline bestiary table) describes actor behaviour in prose. Many briefs already include illustrative zForth (Asteroids has a complete `do-player-tick`; Joust has the canonical EXT-2 dispatch pattern; Donkey Kong's `bestiary.md` shows the Mario state machine). Hand-porting from prose to working zForth is bounded but tedious.

**Opportunity:** A skill that takes a bestiary entry + the project's `INDEXOF_*` mailbox name table (sourced from `wfsource/source/mailbox/`) and emits zForth that compiles cleanly. The output is reviewed by the designer, not committed blindly — but the first draft is mechanical.

zForth (and Forth in general) is already homoiconic and dispatch-table-extensible by language design — there is *no impedance mismatch* between "describe this actor's behaviour" and "emit a Forth word that does it." This seam is well-bounded precisely because the target language fits the task.

### Seam 3 — Tuning iteration

**Today:** A brief's `tuning.md` lists balance constants (gravity, jump velocity, barrel roll speed). Designer tweaks values, re-exports level, plays it, repeats. Each loop is 5–10 minutes of dead time; difficulty tuning takes 20–50 loops per stage.

**Opportunity (engine side):** A play-telemetry harness — the engine logs `(player position, death cause, time-to-death, score)` at session granularity. A tuning-loop skill consumes the logs + the brief's `tuning.md` and proposes constant updates ("`JUMP_VELOCITY` is too low — 73% of attempts to clear the third platform fail"), with the designer confirming each delta before commit. ~1 week of engine work to add a `MB_TELEMETRY_*` mailbox region and a session-end serialiser.

**Opportunity (Blender side) — leverage what's already there.** Blender's actual *Game Engine* (BGE) was removed in 2.8 (2019); the unofficial UPBGE fork uses Bullet not Jolt and is the wrong tool for "make WF run inside Blender." But several Blender-native subsystems *do* fit this seam without re-implementing the engine:

1. **Custom property panels for tuning constants** (highest leverage; lowest cost). `wftools/wf_blender/panels.py` already drives an OAD-schema-aware property UI. Extend it: surface every `tuning.md` constant as a Blender custom property on the `Director` or `LevelObj`, edit via Blender's N-panel, and the export operator round-trips changes back to `tuning.md` on commit. No text-editor jump-out. ~1 day on top of the existing plugin.
2. **Drivers for cross-constant relationships.** Blender's driver system lets one property be a Python expression over others. `JUMP_GRAVITY = -2 * ENEMY_FALL_GRAVITY` becomes a driver, not two free-floating numbers — captures design intent in the file. Drivers serialise into `.blend` natively; the exporter expands them out as Forth `: <const-name> ... ;` words at build time. ~2 days plus a test pass.
3. **Animation timeline + viewport playback as the telemetry-replay UI.** Once the engine emits a session log (`(player_pos, t)` per frame plus death events), import it as a Blender Action on a ghost-mesh player actor. Scrubbing the timeline shows where the player went; vertex-paint death density onto the room mesh (red where five players died at the same coordinate). All Blender-native — animation editor + vertex paint — no new UI surface to build. ~3 days once the engine-side log format is stable.
4. **Geometry Nodes for parameterised hazards.** "30% barrel chance per girder, density decreasing toward the top" becomes a Geometry Node graph rather than hand-placed objects. Designer adjusts the density slider, hits export, plays. Pairs naturally with Seam 1's whitebox flow — the brief-import operator lays down a geometry-node template per hazard archetype; designer tunes parameters. ~1 week per archetype family (barrel, ladder gap, enemy spawn).
5. **Modal-operator "live cost" overlay during layout.** While the designer drags a platform, an overlay shows "this jump is 1.4× the brief's stated par" computed from `tuning.md` constants. Pre-playtest tuning hint with no telemetry required. ~1 week, separable.

**Recommendation for Seam 3:** start with (1) and (3) — they reuse existing Blender machinery (property panels you already have; animation editor that's free), don't require any new engine work beyond the telemetry log itself, and close the loop in both directions (tweak constants in Blender → re-export; replay sessions in Blender → see what broke). (2) and (4) are quality-of-life additions; (5) is its own small project worth scoping separately.

The engine-side telemetry harness is the load-bearing dependency for (3); (1) and (2) can ship before it. So a sensible order is: Blender property panels for tuning constants → engine telemetry harness → Blender session-replay viewer → drivers + geometry-node hazards as polish.

### Seam 4 — Asset generation (deferred)

**Today:** Source `.tga` textures and `.blend` meshes are hand-authored or borrowed from existing levels (snowgoons reuses `house.iff`, `tree02.iff`, etc.).

**Opportunity:** Once the Zork / Adventure brief's runtime image-generator client + runtime PNG/JPEG decode subsystem ships (~6 weeks of fresh engine work; see `docs/game-ideas/zork-adventure.md`), the same plumbing can run *at bake time* to fill texture slots a designer hasn't supplied. Out of scope for v1 of this tooling plan; explicitly waits on the Zork engine work.

### Seam 5 — Licensed-asset sourcing (the seam this section was originally missing)

**Today:** Nothing systematic. When the snowgoons level needed a tree mesh, somebody made one. When a future Marble Madness conversion needs a checker-pattern marble, somebody will model one. There is no catalog, no provenance tracking, no licence audit trail.

**Why this matters more than the other seams.** A WF level shipping with a borrowed asset whose licence terms are unclear is a *latent legal liability*. Every other seam in this doc is about saving the designer's time; this seam is about not shipping a product that quietly carries someone else's intellectual property under terms incompatible with the project's commercial intent. **Licence is not metadata; it is gate.**

**Opportunity (the deep cut).** Build asset-sourcing into the Blender plugin as a first-class operation, with licence as a load-bearing filter. Architecturally:

1. **Provider abstraction.** A pluggable `wf_asset_provider` interface — a registered list of model + texture sources, each implementing `search(query, license_filter) → list_of_candidates` and `download(candidate_id) → blob + manifest.json`. Today's roster of providers (verify and refresh before any committed list):
   - **Sketchfab** (CC + commercial; per-model licence varies; mature search API)
   - **Poly Haven** (CC0 — public domain — free for any use including commercial without attribution)
   - **Quaternius** (CC0 + paid game-asset packs)
   - **Kenney.nl** (CC0 game assets; the canonical "ship-it-tomorrow" source)
   - **OpenGameArt** (mixed; CC0 / CC-BY / CC-BY-SA / GPL — licence per-asset)
   - **AmbientCG** (CC0 textures + materials)
   - **TextureHaven / HDRIHaven** (CC0; same Poly Haven family)
   - **Blender Cloud** (CC-BY; subscription unlocks downloads)
   - **TurboSquid** (commercial; per-model royalty-free or "Editorial Use" — *must* read each one)
   - **CGTrader** (commercial; mixed royalty-free + extended)
   - **Unity Asset Store / Unreal Marketplace** (commercial; game-engine-bound EULAs — generally *not* portable to a third engine without per-store rules check)

   This is a moving target. The provider list is a config file (`wftools/wf_blender/providers.toml`), not hard-coded — providers come and go (Adobe Substance Source died; new ones launch annually).

2. **Licence taxonomy.** Each downloaded asset carries a `manifest.json` with these fields:
   - `licence_id` — canonical short string (e.g. `CC0-1.0`, `CC-BY-4.0`, `CC-BY-SA-4.0`, `royalty-free-commercial`, `royalty-free-non-commercial`, `editorial-only`, `gpl-3.0`, `proprietary-purchased`).
   - `commercial_use` — `yes-no-attribution` / `yes-with-attribution` / `no` / `paid` / `royalty`.
   - `attribution_required` — boolean; if true, also `attribution_string`.
   - `share_alike_required` — boolean; if true, derived works inherit the same licence (the CC-BY-SA / GPL trap).
   - `royalty_terms` — `null` for flat-fee or free; populated for royalty schemes (`{ rate: 0.05, on: "gross_revenue" }`).
   - `licence_fee_paid_usd` — `0` for free; otherwise the actual fee paid for this asset.
   - `licence_url` — link to the canonical licence text.
   - `provider`, `provider_id`, `download_date`, `original_url`.
   - `derived_from` — chain of parent assets if this is a remix; lets the audit recurse.

3. **Project-level licence policy.** The WF project (or a downstream commercial project consuming WF) declares its policy as `wflevels/<level>/licence_policy.toml`. Every entry is a structured record — `id`, `status`, `reason`, plus optional fields — *not* a comment-annotated string list. The audit tool, the failure diagnostic, the credits screen, and the waiver flow all surface `reason` to the developer; if it lived in a `#` comment, none of them could read it. **Comments-as-data is forbidden in this schema.**

   ```toml
   require_attribution_credits = true   # build pipeline emits credits screen when any attribution-required asset is shipped

   [[licence]]
   id = "CC0-1.0"
   status = "accept"
   reason = "public domain — always fine"

   [[licence]]
   id = "CC-BY-4.0"
   status = "accept"
   reason = "acceptable; attribution must be present in credits screen"
   requires_attribution = true

   [[licence]]
   id = "royalty-free-commercial"
   status = "accept"
   reason = "acceptable when flat-fee paid and recorded in manifest"

   [[licence]]
   id = "CC-BY-SA-4.0"
   status = "reject"
   reason = "share-alike would force WF derivative under CC-BY-SA"

   [[licence]]
   id = "GPL-3.0"
   status = "reject"
   reason = "share-alike, code-flavoured-asset variant of CC-BY-SA"

   [[licence]]
   id = "editorial-only"
   status = "reject"
   reason = "cannot ship in a game"

   [[licence]]
   id = "royalty-on-revenue"
   status = "reject-default"
   reason = "by-default-reject; opt-in per asset only via per-asset waiver"

   # Per-asset waivers (rare; populated by the Blender plugin's elevation flow, not free-form-edited).
   [[waiver]]
   asset_id = "kenney/medieval-tree-04"   # placeholder example
   licence_id = "CC-BY-SA-4.0"
   approved_by = "wbnorris"
   approved_at = "2026-05-12"
   reason = "stylistic match; legal sign-off recorded in <ticket-link>"
   ```

   The `levcomp-rs` step (or a sibling step) refuses to bundle an asset whose `manifest.json.licence_id` lacks an entry with `status = "accept"` (or a matching `[[waiver]]`). **Hard gate** — not a warning. Schema is validated in CI; entries missing `id`, `status`, or `reason` fail the build.

   The file is **tool-managed**, not free-form-edited. `wf-licence add CC-BY-4.0 --status=accept --reason="..."` and the Blender plugin's "request licence approval" UX (which opens a PR with the new `[[licence]]` block) are the canonical paths. Hand-editing is the fallback for legal-review one-offs only.

4. **Filter UI in the Blender plugin.** When the designer hits "Find a tree mesh" in the asset browser, the search query carries the project's accept-list (computed by reading the policy and selecting entries with `status = "accept"`); results from incompatible licences are filtered out at the source — not shown, not reachable by accident. Override is possible (some level may legitimately need a CC-BY-SA asset for a stylistic reason) but requires explicit elevation: a "request licence approval" flow that adds a `[[waiver]]` block to `licence_policy.toml` via PR, with `approved_by` + `approved_at` + `reason` fields populated.

5. **Audit trail.** `wftools/wf_audit/audit_assets.sh` walks a level, dumps every asset with its `manifest.json`, generates a credits page (one-line per attribution-required asset), and asserts every asset's licence has a `[[licence]]` entry with `status = "accept"` (or a matching `[[waiver]]`) in the project policy. Fails CI otherwise. The audit + policy queries use **`tomlq`** (jq syntax over TOML — same query language as JSON's `jq`) for the assertion pipeline; **`taplo`** validates the policy file's schema on every commit (entries missing `id` / `status` / `reason` fail the build before the audit step ever runs).

6. **Royalty-fee accounting.** For royalty-bearing assets (rare but real — e.g. a music track licensed at 5% of gross), the manifest records the rate and the audit tool produces a per-shipped-unit royalty obligation summary. Out of scope for v1 of this seam — capture as Phase F.

7. **The hard cases** (acknowledged, not solved):
   - **Asset remix**. If an artist takes a CC0 mesh, remixes it in Blender, and ships the remix, the remix is *theirs* (CC0 doesn't prevent re-licensing the derivative). The `derived_from` chain in the manifest lets a future audit reconstruct the chain — but enforcing "re-licensed-after-remix" is honour-system at the artist's authoring step.
   - **AI-generated assets**. The legal status is unsettled (US vs. EU law differ; per-jurisdiction pending). Treat AI-generated assets as a *separate licence category* (`ai-generated-uncertain`) and let the project's `licence_policy.toml` decide whether to accept. Do not make a default ruling.
   - **Audio**. The whole framework above applies to sound effects and music, with the additional twist that mechanical-rights vs. sync-rights vs. master-rights are distinct categories. Out of scope of v1; a future "audio asset sourcing" sibling investigation needs to extend this taxonomy.

---

## Concrete deliverables ranked by leverage

In rough rank order:

1. **`/wf-build-level` Claude Code skill** (Seam 1). Consumes a brief, lands a `.blend` scaffold + `.lev` skeleton, runs `build_level_binary.sh`, reports pass/fail. Glue, not new infrastructure. ~3 days.
2. **Asset-provider abstraction + licence-policy gate** (Seam 5, the load-bearing piece). New `wftools/wf_asset_provider/` Rust crate with provider plugins for Poly Haven, Kenney, AmbientCG, Sketchfab. `licence_policy.toml` schema + enforcement in `levcomp-rs`. Audit tool. ~1.5 weeks.
3. **`/wf-author-script` Claude Code skill** (Seam 2). Bestiary prose → zForth using the project's mailbox name table. ~3 days.
4. **Blender plugin "Brief import" operator** (Seam 1, deeper). Extends `wftools/wf_blender/operators.py` with a "File → Import → WF Brief" action. Reads `<game>.md`, populates the scene with named actors, schemas attached, room collections. ~1 week.
5. **Pluggable LLM backend.** `WF_LLM_PROVIDER=anthropic|openai|local` env var; prompt templates in `wftools/wf_blender/llm_prompts/`. The `/wf-build-level` and `/wf-author-script` skills read provider config from the env. Adding a provider is a new template + the crate's HTTP shim. ~2 days.
6. **Tuning-loop telemetry harness** (Seam 3). Engine-side `MB_TELEMETRY_*` mailbox region; session-end log serialiser; analysis skill. Engine work + tooling work. ~2 weeks total.
7. **Asset-gen integration** (Seam 4). Deferred until Zork / Adventure's runtime image-gen subsystem ships. ~6+ weeks behind.

---

## Pluggable-LLM design notes

The `WF_LLM_PROVIDER` env var selects the backend. Providers each implement a tiny shim:

```rust
trait LlmProvider {
    fn complete(&self, system: &str, user: &str, model: &str) -> Result<String>;
}
```

Concrete providers:
- `anthropic` — Claude Sonnet 4.6 / Opus 4.7 via Anthropic API.
- `openai` — GPT-4o / o3 via OpenAI API.
- `local` — llama.cpp / LM Studio / Ollama HTTP endpoint; configurable host:port.
- `none` — disable LLM features; the skill returns an error message asking the designer to set the env var. Default for CI.

Prompt templates live in `wftools/wf_blender/llm_prompts/*.md`, one per skill (`build_level.md`, `author_script.md`). Versioned in git. The skill reads the template, substitutes `{{brief_path}}`, `{{mailbox_table}}`, etc., and submits.

**Key rule:** prompt drift across providers is *not* acceptable. If a prompt only works on Claude, it's a bug, not a feature. The skill must produce the same level of quality on the slowest local llama as on the fastest API call — accepting that local llama may take longer. If a provider can't reach baseline quality, drop it from the supported list and document why.

---

## Format note — Forth + parking-space patterns

zForth is the project's scripting choice (see `docs/scripting-languages.md` and the "WF World Foundry engine project" memory). A separate parking-space project recently designed a TUI-scripting DSL and ended up at multi-bracket LISP after rejecting iffcomp's FOURCC-named verbs. The relevant *patterns* — homoiconic source as artifact, dispatch-table extensibility, record-edit-replay — are not LISP-specific; Forth has them natively. So the parking-space design notes are useful as *evidence* that the patterns work in real systems, but the implementation in WF is straight Forth-on-zForth, no LISP detour. Mentioned here only because the user asked us to consider parking-space's chat as an input.

---

## Phased plan

- **Phase A — Skill scaffolds.** `/wf-build-level` and `/wf-author-script` as Claude Code skills (no Blender plugin work yet). ~1 week. Acceptance: a designer can run `/wf-build-level qbert` and get a `.blend` + `.lev` skeleton in their working directory; running `build_level_binary.sh` against that skeleton produces an `.iff` that the engine can boot (even if visually empty).
- **Phase B — Asset provider + licence gate.** `wf_asset_provider` crate with 4 initial backends (Poly Haven, Kenney, AmbientCG, Sketchfab). `licence_policy.toml` schema + enforcement in `levcomp-rs` (structured `[[licence]]` records with `id` / `status` / `reason`; comments-as-data forbidden — see Seam 5 for the schema). Audit tool wired through `tomlq` queries; CI gate via `taplo` schema validation. Tool-managed (not free-form-edited) via `wf-licence add` CLI + Blender "request licence approval" PR flow. ~1.5 weeks. Acceptance: an asset whose `manifest.json.licence_id` lacks a `[[licence]]` entry with `status = "accept"` (or a matching `[[waiver]]`) fails the build with a clear diagnostic; the audit tool dumps every shipped asset with its licence, reason, and attribution.
- **Phase C — Blender brief-import operator.** "File → Import → WF Brief" UI in `wftools/wf_blender/operators.py`. Adds named actors, attaches OAD schemas, creates room collections from the brief's room-graph table. ~1 week. Acceptance: opening Blender on an empty scene and running the brief-import on `donkey-kong.md` produces a scene with 4 stages × N actors × room collections, ready for the designer to refine geometry.
- **Phase D — Pluggable LLM backend.** Env-var-driven provider selection; prompt templates in git. ~2 days incremental on top of Phase A skills. Acceptance: the same `/wf-build-level qbert` invocation works against Anthropic, OpenAI, or a local llama with no other change.
- **Phase E — Telemetry-driven tuning loop.** Engine-side `MB_TELEMETRY_*` region + session-end log serialiser + `/wf-tune` analysis skill. ~2 weeks. Acceptance: after 10 playthroughs of `donkey-kong.md` Stage 1, the skill proposes (and the designer accepts or rejects) at least one `tuning.md` constant change with a rationale citing the telemetry.
- **Phase F — Royalty accounting + audio assets.** Out-of-scope-of-v1. Sibling investigation when the project has a real shipping product with revenue.
- **Phase G — Asset-gen via runtime LLM/image client.** Strictly downstream of Zork / Adventure's engine work (~6 weeks behind). Out of scope for this plan.

Total Phase A → E: roughly 5–6 weeks of focused tooling work.

---

## Risks

- **Licence misfilings.** A provider may misclassify an asset's licence — or an artist may upload a borrowed asset under a CC0 declaration that isn't theirs to give. The audit tool can catch obvious failures (licence not in accept-list); it cannot validate that the upstream declaration is *truthful*. Mitigation: prefer the trusted-curation providers (Poly Haven, Kenney, AmbientCG) over open-upload bazaars (Sketchfab, OpenGameArt) when the licence question matters.
- **LLM-generated content prompt drift.** Provider switching is free in theory; in practice each model has its own quirks. Mitigation: a regression-test suite — given the same brief, the same skill on each provider must produce a buildable result. Quality bar checked manually; build-bar checked by CI.
- **Blender plugin breaks the working snowgoons workflow.** The current plugin is the canonical reference and the only thing keeping the build pipeline reproducible. New operators must be additive only; never modify the existing export path or schema-attach behaviour. Verification: snowgoons-blender export must continue to produce byte-identical output (modulo Blender's mesh-size variance) before and after every plugin change.
- **Royalty obligations under-counted.** A royalty-bearing asset whose `manifest.json.royalty_terms` is set to `null` (mistakenly) is invisible to the audit tool. Mitigation: the audit tool warns on every asset whose `licence_id` is `royalty-*` and the `royalty_terms` field is null — refuses to ship. Designer must explicitly set or zero the rate.
- **Pluggable provider becomes an excuse for mediocre prompts.** Don't ship a provider that can't reach baseline quality. The "supported providers" list is curated, not aspirational.
- **Scope creep of the asset taxonomy.** Music has master + sync + mechanical rights; AI generation has unsettled provenance; remix chains can be legally murky. v1 of this plan handles meshes + textures only — flag the rest as future work explicitly.

---

## Out of scope

- **Audio asset sourcing.** Mentioned several times; intentionally deferred.
- **Modeling tools beyond Blender.** No 3ds Max / Maya / Cinema 4D / Houdini integration.
- **Real-time collaborative editing.** Out of scope; designers each work in their own Blender session.
- **Procedural generation that's not provider-backed or LLM-backed.** Houdini-style procedural workflows are their own large investment.
- **Asset *creation* (AI texturing, AI mesh generation).** Phase G material; depends on Zork / Adventure infrastructure.
- **Marketplace integration for end-users.** This plan is for designers building WF levels, not for shipping a user-facing asset store.

## Follow-ups

1. **Per-provider integration spike.** A 2-day spike per provider to validate the API surface and licence-metadata extraction. Especially for Sketchfab (search API quirks) and TurboSquid (no public API; web-scrape only).
2. **Licence-taxonomy review.** Have a real lawyer (not a doc) review the `licence_id` taxonomy + reject-list defaults before any commercial product depends on it.
3. **`licence_policy.toml` defaults per WF use case.** Different downstream products will want different policies — the WF source repo itself should ship "permissive" defaults; commercial-product forks should tighten.
4. **CI integration.** Asset-licence audit should run on every PR that adds or modifies a level's asset list. Caught-at-PR-time is much cheaper than caught-at-ship-time.
5. **Designer training.** A short "how to think about asset licences" doc — accompanies this plan, lives in `docs/`. Not every designer has a copyright lawyer's instincts, and the right *defaults* matter more than the right *checkboxes*.
