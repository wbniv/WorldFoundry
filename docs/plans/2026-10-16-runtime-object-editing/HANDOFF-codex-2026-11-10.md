# Handoff to Codex: runtime object editing, then Sea Stars, 2026‑11‑10

The Claude session ran out of tokens. This is everything you need to carry on. **Will paused everything just before this was written** ("pause everything"). Don't start work until he says to resume.

## Read these first

1. [`docs/plans/2026-10-16-runtime-object-editing.md`](../2026-10-16-runtime-object-editing.md). Its section **"Phase 0 outcomes, 2026‑11‑10"** overrides the Design section wherever they conflict. That section's last paragraph, "Phase 1 is now:", is the current scope.
2. [`phase0-trace.md`](phase0-trace.md), the Phase 0 code trace, with `path:line` evidence and risks R1–R15.
3. [`docs/plans/2026-11-10-starfish-tank.md`](../2026-11-10-starfish-tank.md), the Sea Stars tank. It comes after runtime object editing Phases 0–2.
4. `CLAUDE.md` (repo root) and `~/CLAUDE.md`: house rules. The ones that bite are listed [below](#house-rules-that-bite).

## What Will decided today (all recorded in the plans)

| Topic | Decision |
|---|---|
| New tank | **Sea Stars**: Indo-Pacific display, the player steers a sea star (blue *Linckia*), several species. It also needs a screensaver variant and level settings (Will: "make sure there's a screensaver version, too", "there should be level settings (number of sea stars, etc.)") |
| Sea Stars D11 | Settings are a **standard OAS object** (`SeaStarsSettings`, which inherits `Settings` through `@include settings.inc`), placed once in the level. **No RPRP catalog and no `settings-bindings.json`** (Will: "option 1"; he'd thought "all this RPRP chunks were gone … it's just duplicated work with OAS/OAD and the Settings class") |
| Runtime object editing | **Unparked**, and it goes before Sea Stars' settings. **O4 engine scope approved** ("yes, engine scope approved") |
| R1 | The Editor Label override is a plain `.lev` custom property, read by levcomp at export. **Never add it to `actor.inc`**: that would move every field of every type by 4 bytes in every compiled level. Follow-up TODO filed |
| R7 | Keep M4's INT32 Seed cap. Clamp saved planted seeds above 2 147 483 647 |
| R11b | Drop bounded text fields. The planted Seed becomes an `INT32`, and the baseline Field types sheet loses its text and path rows. Follow-up TODO filed |

**Still waiting on Will:** Sea Stars D1–D10 (name, player species, roster, glass climbing, speed, style, frame gate, A button, the settings fields, maximum counts). Don't build Sea Stars art or behaviour until he answers.

## Where Phase 1 stopped

Phase 1 was running in a subagent (T4), and it was stopped mid-task when Will paused.

**Committed locally, not pushed:**
- `8cdd071d` "SHOW_AS_LIVE modifier bit, masked off before every showAs comparison". R4: `SHOW_AS_LIVE` = 0x40 in `oad.h`, with a masking helper in `wf_oad`, `wf_attr_schema`, `wf_attr_edit`, `wf_attr_validate`, levcomp-rs, `oas2oad-rs`, `wf_py` and the editor's `oad_reader`. It's meant to build and pass on its own, but **re-run the tests before pushing**, because it was never reported as verified.

**Staged in the index but not committed** (the subagent staged these):
- `wfsource/source/oas/objects.{c,col,e,h,inc,lc,mac}`: `PlantedTankSettings` appended to `objects.mac` and the headers regenerated
- `wfsource/source/oas/plantedtanksettings.{oas,ht,oad}` and `settings.inc` (new)

**Modified, unstaged, and part of Phase 1:**
- `wfsource/source/oas/levelobj.{oas,ht,oad}`: the `LevelObj` appends (Editable Objects, Editable Object Labels, descriptor offsets)
- `wftools/levcomp-rs/src/{common_block,decompile,lvl_writer,main,oad_loader,test_support}.rs`, and the new `editable.rs`
- `wftools/wf_oad/src/lib.rs` and `wftools/wf_oad/tests/fixtures/{camera,gold,levelobj}.oad` (R10 re-sync)
- `tests/levelobj_fields_test.cc`, `tests/test_levelobj_fields.py` and the new `tests/test_editable_objects_export.py`. **It stopped while updating a Python test**, so this is unfinished.

**Untracked, probably regeneration side effects:** `wfsource/source/oas/{font,init,meter,movie,pole,test}.ht`. Check whether `regen-headers.sh` always writes these and whether they were ever tracked. Don't commit them unless they belong.

**Not yours. Never stage or commit these** (other sessions' uncommitted work):
- `TODO.md`. Edit only your own lines; see [Committing](#committing-on-this-shared-tree).
- `scripts/build-object-properties.py`, `scripts/build-aquarium-screensaver-levels.py`, `tests/test_aquarium_screensaver_catalog.py`, `tests/test_backface_cull_invariant.py`
- many `wflevels/*.iff`, `wflevels/*/…`, `docs/diagnostics/…`, `docs/plans/.deferrals-seen`, and others. Run `git status` and treat anything outside the Phase 1 list above as foreign.

## What's left of Phase 1

From the plan's "Phase 1 is now" paragraph, checked against the tree:

1. Finish and pass the tests: `tests/test_editable_objects_export.py`, `tests/test_levelobj_fields.py`, `tests/levelobj_fields_test.cc`, the levcomp `cargo test`, and the R4 radio-plus-live round trip.
2. levcomp writes a **non-empty** Editable Objects list: every object whose type's `.oad` has at least one `SHOW_AS_LIVE` field. Labels are the type display name plus an ordinal, the `.lev` `Editor Label` property overrides them, and a duplicate fails the build. Strings go through an exact-match add, with a `"Cat"`/`"Cats"` test (R8). The descriptors are trimmed to the type's own entries plus the first index shipped (R2), and stored in the LVL common area (R9). Check `editable.rs` for how far this got.
3. **Prove that older levels still load.** A level compiled without the `LevelObj` appends must read as "nothing editable" and load unchanged, through a bounded helper like `levelobj_fields.hp:31-47`. Will was told this is the trace's reading of the code, **not yet tested**. If it fails, tell him: then every level needs recompiling.
4. Run levcomp's oracle and parity tests (iff2lvl). Every committed level rebuilds **byte-identical** unless it gains the new `LevelObj` fields. Report which levels change and why.
5. Split the work into one-concern commits, each building and passing with its test (type registration; `LevelObj` appends plus the old-level proof; levcomp list, labels and descriptors; fixture sync). Then push to `2026-new-level`.

After that come **Phase 2** (the engine side: the writable overlay copied before construction at `level.cc:830-836`, the `extern "C"` offset walker exported from `wf_attr_edit` (R15), `property@` reading the overlay, `property-int-bytes@` accepting `INT32` (R6), and the host fed from the list) and **Phase 3** (migrate all ten catalog levels: `aquarium_plants`, `planted_tank_screensaver`, `aquarium_jellyfish`, `aquarium_thai_reef`, `aquarium_thai_reef_anime`, `baseline`, plus four generated Dream variants; Android `PlantedSettingsProvider`; `check_tank_catalog`). Both are in the plan.

## House rules that bite

- **Builds, tests and engine runs happen in containers, never on the host:** `scripts/in-linux-container.sh` (`WF_CONTAINER_IMAGE=linux-test` by default, `blender` for level generation). Use `task <name>` where a Taskfile entry exists.
- **The branch is `2026-new-level`.** Pushing there is the finish line. **Never open a PR to master.**
- **Never change the engine beyond what Will approved.** O4 covers the plan's "Engine changes" list plus migrating every catalog user. Anything else needs his OK.
- **Resolve at export, not at runtime:** no runtime scans by type (M3).
- **Plan-first:** a non-trivial change gets a plan in `docs/plans/` with mockups and Mermaid diagrams. Render it with `task md -- <file>` and check that every diagram draws (watch for `Warning: mermaid.ink render failed`).
- **Ask before deciding anything that's Will's.** He prefers multiple-choice questions with a recommendation.
- **Writing:** 24-hour times; non-breaking hyphens (U+2011) in ISO dates in prose; every URL as a `[label](url)` link; a non-breaking space between a number and its unit.
- **Crash-prone batch runs:** `ulimit -c 0; ulimit -v 2000000`.
- **At most three hypotheses on one failure**, then stop and report.

## Committing on this shared tree

- Stage only your files, and check `git diff --cached` before every commit. **The index currently holds staged Phase 1 files** (listed above), so a bare `git commit` takes them too. That's fine when you mean to commit them, and not otherwise.
- **`TODO.md` has other people's unstaged edits.** To commit only your own line, build the index blob from `HEAD` with your change applied (`git show HEAD:TODO.md`, edit, `git hash-object -w --stdin`, `git update-index --cacheinfo 100644,<sha>,TODO.md`), then run a plain `git commit`. Don't use `git commit --only TODO.md`, which takes the whole working-tree file, foreign hunks included.
- **TODO grammar** (linted by `~/python-tui-lib/scripts/todo-lint.py`): `- [T4]` open, `- [wip T4]` in progress, `- [verify T4]` built but not yet verified. Done items move to the top of `## Done` as `- ✅ YYYY-MM-DD — [slug] … See [plan](…).`
- End commit messages with a co-author trailer for whichever agent you are.

## TODO items involved

- `[wip T4]` **Runtime object editing on OAS/OAD (replaces RP02)**. Its `<!-- agent:… -->` stamp names the stopped Claude subagent, which you can't message. Replace the stamp with your own note.
- `[T4]` **Editor Label as a real OAD field**, and `[T4]` **Fixed-size string fields in the OAD overlay**: Will's follow-ups to R1 and R11b. Don't start these yet.
- `[T4]` **Sea Stars**: waiting on D1–D10.
- `[verify T4]` **Baseline settings cleanup**: re-verify after Phase 3. `baseline-runtime-options` needs editable runtime rows.
