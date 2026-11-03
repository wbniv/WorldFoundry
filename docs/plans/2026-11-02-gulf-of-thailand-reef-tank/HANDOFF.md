# Handoff: Gulf of Thailand Reef — 2026‑11‑02 10:37 (Bangkok)

The previous orchestrator session ran out of usage: the 5-hour limit and the **monthly spend limit**. Every reef agent was cut off mid-task. This note is everything a new orchestrator needs. **Read the plan first:** [`2026-11-02-gulf-of-thailand-reef-tank.md`](../2026-11-02-gulf-of-thailand-reef-tank.md). It is the contract, and all ten decisions are made.

## What Will decided (all recorded in the plan)

- **D1–D10 accepted** (Will, 2026‑11‑02: "i accept your recommendations"). That grants engine permission for exactly **E1–E7** (multi-curve `DFRM`) and **S1–S3** (style shading) as the plan specifies, and nothing beyond them.
- **Two visual styles**, each its own level and selector row: `aquarium_thai_reef` (ultra-realistic, row 9) and `aquarium_thai_reef_anime` (cel, row 10).
- **The content rule is species only:** no species already in another tank. Reusing meshes, rigs, textures, controllers and shells is fine.
- Will asked to keep the two-Gulf-habitats idea as a separate TODO item. It's in the main tree's `TODO.md`, uncommitted (see below).

## Commits on `2026-new-level` (main tree)

`a0c95dda` plan · `ecc095dd` two styles · `dc27d780` shell not covered by the rule · `2e8f756b` decisions accepted · `9dab404c` content rule is species only.

## Live work: three worktrees, nothing committed yet

All three are **sparse checkouts** (720 MB each instead of 4.2 GB; see "Disk" below). The agent ids can be resumed with `SendMessage` once usage allows. Each keeps its context and continues where it stopped.

| Phase | Agent id | Worktree / branch | State at cutoff |
|---|---|---|---|
| **E** `DFRM` v2 (T4) | `adccf2d23b5e963c8` | `.claude/worktrees/agent-adccf2d23b5e963c8` / `reef-dfrm-v2` | Uncommitted edits to `dfrm_deform.{h,cc}`, `mesh_deformer.cc`, `scripting_zforth.cc`, `dfrm_chunk.py` and `dfrm_ref.py`. Its last words: "Writer is byte-identical for v1 through both entry points. Now the Python reference." The tests (E6) and evidence are not yet written |
| **S** style shading (T4) | `af0b24dd5f0c6116f` | `.claude/worktrees/agent-af0b24dd5f0c6116f` / `reef-style-shading` | Uncommitted edits to `gfx/camera.{cc,hp,hpi}`, `backend_factory.cc`, `backend_modern.cc` and `renderer_backend.hp`. Last words: "Now uniforms, members, program builders." Still to do: Metal, `camera.oas`, the Risk 3 route, the invariant test, captures |
| **0** research + poster (T3) | `aa89aff91a43dd0f3` | `.claude/worktrees/agent-aa89aff91a43dd0f3` / `reef-phase0` | Untracked `docs/reference/gulf-of-thailand-reef-poster/` and `tests/test_poster_gulf_of_thailand_reef.py`. **No `docs/reference/thai-reef-research.md` yet.** It had spawned two research sub-agents ("fish and crab biology", "mobile invertebrates"); both died at the limit and their findings are not on disk |
| **1** shell + static reef (T4) | — | not started | Queued until E or S finishes (disk). Brief: see "Starting Phase 1" |

**Resume message for each agent:** "Usage limits reset; continue Phase X from where you stopped. Same brief, same disk rules (stop below 5 GB free)." If a resume fails (for example, the worktree is gone), start a fresh agent with the same brief. The briefs are reconstructible from the plan: each phase's section, plus the rules below.

Rules every agent was given:
- build and test in containers only;
- commit on its own branch, no push or merge;
- don't edit the plan `.md` or `TODO.md`;
- write evidence to `evidence/<phase>.md`;
- report `ESCALATE:` past its remit;
- cap debugging at 3 hypotheses;
- no Codemagic builds (Phase S records Metal parity as pending);
- cast1 work only if a cast is unreserved, restoring it afterwards.

## Integration (the orchestrator's job, T5)

When a branch reports done:
1. Read its `evidence/<phase>.md`.
2. Check it against the plan's verification steps (3 for E, 14 for S, 1–2 and 13 for Phase 0).
3. Merge into `2026-new-level`.
4. Remove its worktree and branch.
5. Update the plan's status and strike completed steps.

Then dispatch the next phases in the plan's order: 1 → 1b → 2 → 3 → 4 → 5.

## Uncommitted in the main tree (careful)

- **`TODO.md`:**
    - My `[wip T4]` stamps on three reef items (`<!-- agent:… -->`) are uncommitted.
    - **The rest of `TODO.md`'s diff belongs to another session** (the Planted Tank `[verify T3]` item). Stage only reef hunks: `HEAD` plus reef lines → `git hash-object -w` → `git update-index --cacheinfo`. Never `git add TODO.md`.
- **Not ours; never stage:**
    - `scripts/build-aquarium-screensaver-levels.py`, `scripts/build-object-properties.py` and `tests/test_aquarium_screensaver_catalog.py` (Planted Tank work; Phase 4 waits for them);
    - `tests/test_backface_cull_invariant.py`, the `.iff` changes and `wflevels/qbert_practice/…`.
- This file is committed with the reef stamps.

## Disk (this caused two outages on 2026‑11‑02)

- `/` has **7.4 GB free** (10:37). A full checkout of `2026-new-level` is **4.2 GB**, of which 3.8 GB is `docs/` media and logs.
- **Make every agent worktree sparse before work starts:**
  `git -C <wt> sparse-checkout set --no-cone '/*' '!/docs/diagnostics/' '!/docs/plans/**/*.log' '!/docs/plans/**/*.png' '!/docs/plans/**/*.mp4' '!/docs/plans/**/*.webm' '!/docs/plans/**/*.gz' '!/docs/plans/**/*.bin' '/docs/plans/2026-11-02-gulf-of-thailand-reef-tank/'`
  This setting is per worktree; the main tree is unaffected.
- `isolation: worktree` checks out `master` first. Agents then `git switch -c <branch> 2026-new-level`, which temporarily writes the full 4.2 GB before you can make it sparse. With less than ~8 GB free, create the worktree yourself instead: `git worktree add --no-checkout`, then `sparse-checkout set`, then `checkout`. Then run the agent without isolation, pointed at that path.
- Docker (`wf-rootless` context): build cache was pruned, and the Blender image `wf-blender:local` is **not present**. Phase 1's first level build rebuilds it (a few GB).
- Core dumps are now capped (Will ran `disk-hygiene-system-setup.sh`).

## Starting Phase 1 (when E or S frees its slot)

Brief, T4, no engine edits:
- **Build:** `wflevels/aquarium_thai_reef/` with `config.py`, `reef/scene.py` (one seeded scene with anchors), `reef/rockscape.py`, `corals.py`, `sponges.py`, `atlas.py` (1024² realistic), `generate.py`, `build.sh` (container, through `scripts/level-build.sh`), `run.sh` and `report_budget.py`.
- **The shell:** new, 120 × 60 × 55 cm at ×10 scale, with a placeholder player.
- **Budget:** ≤ 48,000 static triangles in ≤ 8 groups.
- **Test:** `tests/test_aquarium_thai_reef.py` checks the budget, the content rule (species only) and the anchors.
- **Registration:** a `task aquarium-thai-reef-level`, plus entries in `aquarium-levels.sh` and `compare-level-build-routes.sh`. **No** menu or Dream registration (that's Phase 4).
- **Evidence:** desktop captures. A cast1 static gate of ≤ 38 ms, or pending.
- **Layout reference:** `build_mockups.py` (scene units 1600 × 900).
- Full detail is in the plan's Phase 1, "The tank" and "Two visual styles".

## Useful facts found along the way

- `DFRM` v1 refuses more than one curve at `dfrm_deform.cc:81` and `:177`.
- The zForth `deform-block` reads at most 40 cells (`scripting_zforth.cc:1412`).
- `dfrm-pose` is defined at `:1636`.
- Fog lives on the Camera OAD (`oas/camera.oas`, read at `game/camera.cc:67`).
- The `dfrm_strand` ctest is at `CMakeLists.txt:1280`.
- The seahorse cost basis (+30 render actors → +21.54 ms CPU on cast1) is in `docs/plans/2026-10-16-saltwater-seahorses/comparison.md`.
- *Trapezia cymodoce* at Mu Ko Tao: search results point to a 2024 coral-crab survey ([candidate abstract](https://scijournal.buu.ac.th/index.php/sci/article/view/4852)). Phase 0 must confirm it.
