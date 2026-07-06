# Project review — plans & code issues (2026-07-05)

**Scope:** docs/plans (312 plans + index), TODO.md, wf-status.md, CLAUDE.md claims,
`wfsource/source/physics/` + `movement/` (full read), `game/` + `gfx/` + `hal/` + `iff/` +
zForth/WASM syscall handlers (§1b, follow-up pass), Taskfile/CMake/codemagic/CI,
oas2oad-rs `name_KIND` pipeline, repo hygiene.
**Method:** parallel review agents + direct verification of every claim marked *confirmed*.
**Not covered** (review interrupted, see §8): Rust tool parsers (iffcomp/levcomp/textile
internals), Blender addon Python. (The `wf_edit`/CRDT/relay collab stack was subsequently
covered — see §5.)

Severity: **H**igh / **M**edium / **L**ow. Confidence noted where a finding was not
re-verified line-by-line (`plausible` = mechanism read from code, trigger not proven).

---

## 1. Engine code — physics & collision (highest-risk defects)

### Buffer overruns (release builds have no bounds checks)

1. **H — `collision.cc:522-525`: out-of-bounds write *before* the assert.**
   The event is written to `collisionEventList[collisionEventListLength]` first, and
   `AssertMsg(collisionEventListLength < MAX_COLLISION_EVENTS, …)` runs *after* the write.
   `MAX_COLLISION_EVENTS` is 100 (`collision.hp:22`). The 101st simultaneous overlap stomps
   the adjacent globals (`collisionEventListLength`, `recollisionList` at `collision.cc:20-23`)
   — even a debug build writes one slot past the end before aborting. *Confirmed.*

2. **H — `collision.cc:245`: `recollisionList[recollisionListLength++]` has no bounds check
   at all** (not even an assert). `ResolveCollisionEvent` can push up to 2 entries per event
   (`collision.cc:406,440`) and the list drains only after the whole event list is resolved
   (`actrooms.cc:410-424`), so ~50 physics-vs-physics collisions in one frame overflow a
   100-entry array in **all** build types. *Confirmed (unchecked write); trigger plausible.*

### Level-data-controlled reads with assert-only guards

3. **H — `activate.cc:97-98,172`: authored `ActivatedByActor` indexes `masterObjectList`
   raw.** `Array::operator[]` bounds checks are pure `assert`s (`cpplib/array.hpi:180-198`),
   so in release an authored −1 ("none" sentinel) or out-of-range index is an unchecked OOB
   read followed by a dereference. *Confirmed.*

4. **M — `activate.cc:184-197`: `IsActivated` case 3 dereferences `_objList`, which is NULL
   when the level supplies no list** (constructor nulls it at :62-65 under a `DO_ASSERTIONS`
   guard only), and the list's indices are also unchecked per finding 3. *Confirmed.*

5. **M — `movepath.cc:100-101`: `ObjectToFollow` index — same assert-only pattern.** *Confirmed.*

6. **M — `jolt_backend.cc:305-308`: mesh face indices from `cd.iff` index the vertex array
   unchecked** — neither the backend nor the `actor.cc` BindAssets caller validates
   `faces[i].v0..v2` against `vertCount`; a corrupt/mismatched asset is an OOB heap read.
   *Confirmed.*

> These are one class of bug: *authored data trusted at engine boundaries, guarded only by
> asserts that compile out.* The camera stale-track fix and the ActBox mailbox-0 TODO entry
> are the same class. Worth a single sweep: every `masterObjectList[...]`/`WriteMailbox`
> callsite fed by OAD/level data gets a real (non-assert) range check.

### Stale-state reuse in the Jolt bridge

7. **H — `jolt_backend.cc:240-247,272-278,344-351`: a reused `BodyEntry` slot keeps the
   previous occupant's `actor` pointer** — neither create nor destroy clears `e.actor`.
   `FindActorForBodyID` (:508-513) hands that pointer to `JoltContactDispatch`, which calls
   `otherA->Collision(...)` on it (`actor.cc:1827`). Today every creation site happens to call
   `JoltBodySetActor` immediately after, which masks it; any future body created without the
   follow-up call delivers contacts to a freed actor. Fix is one line in create/destroy.
   *Confirmed latent defect; currently masked.*

8. **M — `jolt_backend.cc:646-657,700,710-715`: reused `CharEntry` never clears
   `excludeBodies` (or `actor`).** A character in a reused slot inherits the previous
   character's ignore list; Jolt BodyIDs recycle with an 8-bit sequence, so after enough churn
   a stale excluded ID can alias a live static body → character ignores real floor/wall
   geometry. *Confirmed retention; aliasing plausible.*

9. **M — `JoltVehicleDestroy` is never called anywhere** (`jolt_backend.cc:939-948`,
   `movevehicle.cc:69`): a despawned vehicle leaves a live dynamic chassis colliding in the
   world and a leaked `VehicleEntry`, unlike boxes/characters which `~PhysicalAttributes`
   cleans up (`physical.hpi:253-267`). *Confirmed.*

### Numeric / logic issues

10. **M — `collision.cc:364-366`: divide-by-zero guarded only by assert** — mass authored as
    exactly 32767 leaves `oneOverMass` zero (:337-341); physics-vs-non-physics collision then
    divides by zero in release (fixed-point divide = crash). *Plausible.*
11. **M — `collision.cc:394-404`: object1's response branch modifies *attr2*'s velocity with
    signs opposite to the object2 branch** — looks like a copy-paste target error (should
    mirror with attr1/`collisionVelocity1`). Benign against anchored objects (velocity zero),
    wrong for two moving physics objects. *Plausible — worth a deliberate look.*
12. **M — `jolt_backend.cc:425-432`: the fixed-step accumulator is never clamped after
    `kMaxSubsteps`** — sustained sub-15 fps accumulates debt; on recovery physics
    fast-forwards at 4 substeps/frame until drained. The header comment (`jolt_backend.hp:66-68`)
    claims spiral-of-death protection; the residual is never discarded. *Confirmed.*
13. **M — `jolt_backend.cc:973-984` vs `:865`: vehicle `posCache` seeds as actor-feet position
    but refreshes as chassis center-of-mass** → actor origin teleports up by
    `chassis_hz + wheel_radius/2` on the first step; inconsistent with the base-at-origin
    convention. *Plausible.*
14. **M — `movementmanager.cc:92-102,156-165`: handler data freed into a class-wide static
    `_memory` captured from the *first* manager**, regardless of which pool allocated it, and
    allocated as `char[]` but destroyed via `MEMORY_DELETE(…, MovementHandlerData)` — wrong
    pool + wrong destructor shape for derived handler data. The commented-out assert at :163
    acknowledges it. *Confirmed pattern.*
15. **L/M — unguarded divides:** `movepath.cc:113` (`time / path->EndTime()`, zero-duration
    authored path), `movepath.cc:166` (`/ clock.Delta()`), `colspace.cc:233-235`
    (exact-touch edge in `TimeToHitSlope`). *Plausible.*

---

## 1b. Engine code — game/, gfx/, scripting syscalls (follow-up pass)

Numbered 46+ because this section landed after the original 45 findings. Context that
amplifies most of these: `Array<T>::operator[]` bounds are pure asserts, and the non-const
overload even **mutates** the array on out-of-range access (`if(index >= _num) _num = index+1;`,
`cpplib/array.hpi:180-198`). On web builds every assert is warn-and-continue
(`pigsys/assert.cc` emscripten branch), converting all assert-guarded findings into silent
corruption on WASM.

### Regressions & aborts

46. **H — zForth syscall ID 152 is claimed twice: `read-actor-mailbox` hijacks `node-kind`,
    breaking the filesys views.** `engine/stubs/scripting_zforth.cc:1386` defines
    `: read-actor-mailbox 152 sys ;` (custom 24, comment says "3-23 taken") but `node-kind`
    was already `"152 sys"` (:1503). The dispatcher checks `custom == 24` (:970, pops **two**
    cells, pushes 1) before the FSN accessor branch `custom >= 24 && custom <= 29` (:1167),
    which is now dead for 24. The filesys Director (`wflevels/filesys/blender_filesys.py:184`,
    `fsn-place … node-kind`) now does a cross-actor mailbox read per row — wrong data plus a
    net stack imbalance of −1 per call → garbage kinds, then `dstack_underrun` abort.
    Introduced by the most recent feature commit `484b035f`. *Confirmed (re-verified).*

47. **H — `Actor::die()` writes the OAD "Write To Mailbox On Death" unconditionally; its
    default (0) is a reserved mailbox → abort.** `game/actor.cc:1034` writes
    `GetCommonBlockPtr()->WriteToMailboxOnDeath` with no guard; `oas/common.inc:19` declares
    the field `min 0, default 0`, and `game/mailbox.cc:63-68` asserts `mailbox >= 2`. Any
    destructible actor dying with the default field aborts a DO_ASSERTIONS build (silent drop
    in release). Exact sibling of the known ActBox `ActivatedActorMailbox` TODO item, which
    doesn't list this one. *Confirmed (re-verified incl. OAS default).*

48. **M — `Level::WriteSystemMailbox` falls through from `END_OF_LEVEL` into `CAMSHOT` when
    the value is false** (`game/level.cc:1477-1488`): the `break` is inside
    `if (value.AsBool())`, so writing 0 to END_OF_LEVEL silently zeroes `_camShotMailBox`;
    the next camera tick aborts on `AssertMsg(idxShot != 0, …)` (`movecam.cc:500`).
    *Confirmed (re-verified).*

49. **M — `_scratchMailboxes` has the exact off-by-one the 2026-05-30 fix removed from its
    two siblings** (`game/level.cc:362`): allocated as `SCRATCH_MAX - SCRATCH_START` (no +1)
    while `mailbox.inc:293` documents `SCRATCH_USER_MAX = 4099` as inclusive and
    `mailbox.cc:30-35` fixed the global/persistent allocators to `MAX-START+1`. A write to
    4099 walks off the parent chain to a NULL-parent AssertMsg → debug abort, release drop.
    *Confirmed (re-verified).*

### Script-supplied and authored indices crossing into engine memory

50. **H — script-supplied actor indices reach `LookupMailboxes` with no validation.**
    `write-actor-mailbox` (custom 2, `scripting_zforth.cc:963-969`) and `read-actor-mailbox`
    (custom 24, :977-984) pass the popped index straight to
    `WorldFoundryMailboxesManager::LookupMailboxes` (`game/level.cc:319-329`), where a freed
    slot is NULL (assert-only) and an out-of-range index hits the mutating
    `Array::operator[]`. Same class: `set-rotation` (custom 19, :1118, RangeCheck only) and
    `spawn-template` (custom 7, :1036-1043 — `Level::HasTemplate` exists for the probe but is
    unused). The WASM twins (`scripting_wamr.cc:116-128`) have the identical hole. Trigger
    needs no hostile script — qbert/FSN write to cached indices that can despawn a tick
    earlier. *Confirmed.*

51. **H — `BungeeCameraHandler::update` dereferences unresolved actor indices — the
    2026-06-13 stale-track fix covered only half the paths.** `game/movecam.cc:1015-1026`
    chains `theLevel->getActor(shotData->Target/Follow/TrackObject)->GetPredictedPosition()`;
    `getActor` returns NULL for a freed slot even in debug (`level.hpi:119-128`), so a
    despawned target crashes in all build modes — the exact scenario `ResolveTrackObject`
    (:232) was added for. It also ignores the `TrackObjectMailbox` override that
    `SetCameraParametersFromShot` honors (:288-290); that function has its own unguarded
    `bol[shotData->Follow]` (:259) and `getActor(shotData->Target)->…` (:312). *Confirmed
    mechanism; trigger plausible.*

52. **M — `Level` caches raw pointers to special actors that removal never clears.**
    `SetPendingRemove` (`level.cc:1357-1361`) refuses removal only for the camera;
    `_mainCharacter`/`_idealMainCharacter`/`_director` are never nulled by
    `removePendingObjects` (:1046-1084). A script writing `EMAILBOX_ALIVE = 0` on the player
    (`actor.cc:1436-1437`) or a Destroyer covering the player leaves
    `updateMainCharacter()` operating on freed memory next frame. Same class as the fixed
    camera bug. *Plausible, high impact.*

53. **L — cross-actor system-mailbox reads hit kind-specific fields with no kind guard**,
    newly reachable via `read-actor-mailbox`: `actor.cc:1227-1231` (`_nonStatPlat->_hitPoints`
    — NULL for StatPlats) and `actor.cc:1336-1340` (unchecked `(Missile*)this` cast in
    release). Before commit `484b035f` these were only reachable from an actor's own script.

### Write-before/without-bounds-check on fixed arrays

54. **M — pending-removal queue can overflow in release**: `Level::SetPendingRemove`
    (`level.cc:1374`) guards `int32 _toBeRemovedObjects[512]` (`level.hp:248`) with an assert
    only, while temp-actor pools were raised to 2000-4000 (`room/room.cc:109`) and
    `fsn_despawn()` (`scripting_zforth.cc:285-294`) marks an entire view for removal in one
    frame — >512 marks writes past the member array. Sibling:
    `AssetManager::LoadRoomSlot` (`asset/assets.cc:181`) protects the room-slot heap block
    with AssertMsg only. *Plausible, release-only.*

### Rendering & camera math

55. **M — WF_CULL backface test (and one-sided lighting) transform the face normal by the
    modelview instead of its inverse-transpose** (`gfx/glpipeline/backend_modern.cc:379-389`),
    while the per-actor scale mailboxes (3040-3042) bake non-uniform scale into the model
    matrix rows (`renderassets/rendacto.cc:481-483`). Under non-uniform scale (FSN towers
    Z×6, treemap cells) the sign of `dot(M·n, M·c)` can disagree with true facing → wrong
    culling near silhouettes; the same normal-matrix error skews one-sided lighting today.
    The dome (current WF_CULL consumer) dodges it by baking scale at export, but the TODO
    plan to flip WF_CULL default ON collides with every scale-mailbox user. *Confirmed math
    defect; visible impact plausible.*

56. **M — `ActiveRooms::ChangeActiveRoom` unbinds the *new* room (possibly NULL) instead of
    the one being freed** (`room/actrooms.cc:185-187`): `_activeRooms[idxActiveRoom]` was
    already overwritten with the destination at :144, so the code nulls the correct pointer
    then calls `UnBindAssets()` on the wrong (or NULL) room. *Plausible — needs an
    asymmetric room-adjacency transition; the code contradicts its own intent.*

57. **L — `BungeeCameraHandler::predictPosition` divides by authored elasticity**
    (`movecam.cc:972`): camshot `Elasticity = 0` (or zero `deltaT` after a clock reset) →
    division by zero → NaN camera velocity or fixed-point fault. *Plausible.*

### Minor

58. **L — web builds turn every assert into warn-and-continue** (`pigsys/assert.cc`
    emscripten branch): deliberate bring-up tradeoff, but it converts findings 47/49/50/54
    (and the §1 assert-only guards) into silent memory corruption on WASM.
59. **L — unconditional per-spawn stderr spam in the hot path**: `game/generator.cc:128-138`
    prints three `fprintf(stderr, "Generato::FIRING …")` lines per generated object (every
    coin).
60. **L — `gfx/rendmatt.cc:82` `CalcUV(unsigned char uin, …)` still truncates the VRAM
    coordinate to 8 bits** — the 2026-05-31 uint8→uint16 widening covered the glpipeline
    `CalcUV`s but not the matte's copy; wrong background-tile UVs when `u/v + w > 255`.

> Sweep answers for the §1 note: besides ActBox, one more unguarded OAD-mailbox write
> exists (finding 47); `actboxor.cc:87` is safe (OAS min=2). All four
> `MailboxesWithStorage` construction sites were audited — one off-by-one remains
> (finding 49). Stale actor-index caches beyond the fixed camera: findings 50-52.

---

## 2. OAD toolchain — `name_KIND` residual gaps

The 2026-04-17 fix (`1c82130f`) is data-driven off `objects.lc` and covers all 29 kinds, but:

16. **M — missing-kind fallback is silent-wrong-output, not an error**
    (`wftools/oas2oad-rs/src/main.rs:290-299`): unknown stem → stderr warning, exit 0,
    `MovementClass=0`; with `--objects-lc` omitted it's `unwrap_or(0)` with **no warning**
    — exactly the pre-fix bug shape. Should be a hard error for stems that have a
    MovementClass field.
17. **M — two stale, order-divergent copies of `objects.lc` exist**
    (`wflevels/oad/objects.lc`, `wfsource/levels.src/oad/objects.lc`): they put `Gold` at
    index 6 (shifting 21 of 29 kinds) and lack `file`/`dir`. Passing either to `--objects-lc`
    re-fires the engine's 22 `MovementClass` construction asserts. The live pipeline uses the
    correct one (`build_level_binary.sh:33`), but the traps should be deleted.
18. **L — latent case bug** (`main.rs:163` vs `:294`): map keys are lowercased, lookups use
    the raw file stem — `Player.oas` would silently get kind 0. Plan doc claims the lookup is
    case-insensitive; it's half-lowercased.
19. **L — stale `wfsource/source/oas/objects.p`** defines only kinds 0–25 (no
    `Gold/File/Dir_KIND`) — dead today, a trap if the `OASNAME` expansion is ever "fixed".
20. **L — 8 `.oas` files with a MovementClass field aren't in `objects.lc`**
    (`actor,font,init,meter,movie,pole,template,test`) and always take the warn+0 path;
    `test.oad` ships as a wf_oad fixture with `MovementClass=0`.

---

## 3. Build / CI plumbing (broken today)

21. **H — six Taskfile tasks point at `wftools/wf_asset_browser/`, renamed to
    `blender_asset_finder/`** (`Taskfile.yml:877,892,899,906,926,937-938,945,950`):
    `asset-browser-install/-zip/-validate/-package`, `bump-asset-browser`,
    `publish-asset-browser` all fail; `package-all` (:954) dies transitively. *Confirmed.*
22. **H — `engine/vendor/emsdk-6.0.0/` was never committed** although `.gitignore:74-79`
    only excludes its subpaths and the web-canvas plan says it's vendored: `task setup-emsdk`,
    `build-web`, `build-web-edit`, `serve-web-edit`, `dev-setup-web-edit` all fail on a fresh
    clone (`git log --all -- 'engine/vendor/emsdk*'` is empty). This machine evidently has a
    local copy; no one else can build the web editor. *Confirmed.*
23. **H — duplicate YAML key `android-apk-debug` in `codemagic.yaml` (:20 and :254).**
    Parsers keep the last definition (manual, mac_mini_m2), so the push-triggered Linux APK
    workflow — including its `triggering:` block — silently never runs, defeating the
    stated "APK per push to 2026-ios" intent (:18). *Confirmed.*
24. **M — `task build-web-edit` lacks the `vendor-unpack` dep** (`Taskfile.yml:391` deps only
    `dev-setup-web-edit`): fresh checkout fails at `include(…/Jolt/Jolt.cmake)` / empty
    Corrosion. (`build-web` has the dep; `build-web-edit` doesn't.) Currently masked by #22.
25. **M — `task md` (documented in CLAUDE.md Key Commands) does not exist**: it lives in the
    optional shared include `../python-tui-lib/Taskfile.shared.yml` (`Taskfile.yml:3-7`),
    which is absent on this machine; `optional: true` hides the breakage. Fix CLAUDE.md or
    make the include's absence loud.
26. **M — `install-apk` hardcodes `/usr/lib/android-sdk/platform-tools/adb`**
    (`Taskfile.yml:542-545`) — never installed by any setup task (`android-sdk-install`
    installs no `platform-tools`; `dev-setup` installs distro adb at `/usr/bin/adb`). Broken
    on this host. *Confirmed.*
27. **M — first (currently shadowed) codemagic android workflow: `yes | sdkmanager` under
    `pipefail` → SIGPIPE 141 step failure** (:44,57). The second copy patched exactly this
    (:307-308); if #23 is fixed by renaming, the first copy re-breaks unless patched too.
28. **L — `-Pandroid.ndkVersion` / `-Psdk.dir` in codemagic (:73-74) are no-ops** — AGP reads
    `build.gradle.kts:12` and `local.properties`, not `-P` properties; bumping
    `WF_NDK_VERSION` in codemagic alone would silently do nothing.

---

## 4. Plans & TODO hygiene

29. **H — the `check-plan-index.sh` drift hook advertised in `docs/plans/README.md:5-6` does
    not exist** anywhere in the repo (or in `scripts/git-hooks/`), so the index-drift guarantee
    is fictional. (The index itself is currently clean: all 312 plans indexed, no dangling
    rows — verified both directions.) *Confirmed.*
30. **H — no git hooks are active in this clone at all**: `.git/hooks` has zero non-sample
    hooks and `git config core.hooksPath` is unset, so even the printf-filename guard
    (`scripts/git-hooks/pre-commit`, which itself documents the required
    `git config core.hooksPath scripts/git-hooks`) is inert. *Confirmed.*
31. **M — 5 duplicate plan pairs, each two divergent near-copies, both indexed as separate
    rows with different summaries, some with contradictory statuses:**
    - `2026-04-23-chromecast-google-tv-port.md` ("Status: Not started") vs
      `2026-04-23-chromecast-googletv-port.md` ("Phase 0 ✅ Phase 1 ✅ done") — TODO.md links
      the latter; the former is stale and contradicts it.
    - `2026-04-29-blender-run-operator.md` ("OPEN — not wired") vs
      `2026-04-29-run-in-engine-blender-operator.md` (no Status) — wf-status.md says the
      operator **shipped 2026-04-29**, so the "OPEN" status is wrong.
    - `2026-04-28-wf-asset-provider-pure-python.md` ("OPEN — not started") vs
      `2026-04-29-pure-python-asset-provider.md` (no Status) — wf-status.md records the
      pure-Python rewrite as done 2026-04-28.
    - `2026-04-28-game-ideas-dependency-graph.md` vs `…-and-tooling.md`.
    - `2026-06-04-viewport-doesn-t-resize-on-window-maximize.md` ("Done") vs
      `2026-06-04-viewport-resize-on-maximize.md` (no Status).
    Each pair needs one canonical file; mark the other superseded (the repo already has this
    convention) or move it to `cancelled/`. *Confirmed.*
32. **M — 50 of 312 plans carry no Status marker** (grep for any `status:`-like line),
    contradicting the 2026-05-25 sweep's "every plan now carries a Status". Most are
    post-sweep (2026-05-26 → 2026-06-13) — i.e. the sweep's invariant wasn't maintained and
    nothing enforces it — plus ~12 pre-sweep stragglers
    (e.g. `2026-04-28-joust-clone-plan.md`, `2026-05-12-zforth-js-port-recommendation.md`,
    `2026-05-23-guard-flto-thin-behind-clang.md`). *Confirmed by grep; a few may use
    nonstandard markers.*
33. **M — TODO.md has 5 broken plan links:** `per-level-max-active-rooms.md` (actual file has
    a date prefix), `deferred/2026-04-29-eliminate-rtti.md` (not in deferred/),
    `2026-05-30-baseobject-2003-extraction.md` (moved to docs/investigations/),
    `2026-05-14-qbert-multi-step-cube-cycles.md` (moved to docs/qbert/plans/),
    `2026-05-17-per-metapackage-install-scripts.md` (deleted entirely).
34. **L — orphan at plans root:** `project_followup_replace_physics.md` has no date prefix
    (naming-convention outlier). It *is* correctly indexed (`README.md:310`) and its
    "In progress — several open items remain" status maps 1:1 to the still-open TODO Physics
    section — not a stale-DONE, just the odd filename. *Confirmed.*
34a. **M — `wflevels/cd_full.iff.txt` is broken/unbuildable** (matches TODO.md:62 exactly):
    it `[ "…" ]`-includes five nonexistent build-time paths (`/tmp/L0_cube.iff`, `L1_basic`,
    `L2_cyber`, `L3_primitives`, `/tmp/L6_whitestar.iff` — verified absent), so `iffcomp`
    can't build it; and line 41's bare `[ "snowgoons.iff" ]` at the L4 slot has no `{ 'L4' … }`
    wrapper, but snowgoons roots at `LVAS` not `L4`, so the TOC entry (`:20`) resolves to
    nothing. The correct sibling `cd_snowgoons.iff.txt:28-38` wraps it. Regenerate or delete.
    *Confirmed.*
34b. **M/L — wf-status.md carries stale entries the plan-status sweep didn't reach:**
    - `wf-status.md:143` still lists "Level pipeline proof … in progress (Phases A+B+C done,
      D–E gate the common.inc rearrangement)", but TODO records both D (`:230`, 2026-04-19)
      and E (`:157`, 2026-06-04 multi-level cd.iff) as done — stale in-progress. *Confirmed.*
    - `wf-status.md:49`'s sweep entry asserts "Reconciled all 225 plan docs … every plan now
      carries a Status"; the dir now holds 312 plans and ~50 lack a Status (finding 32), so
      both the count and the standing "every plan" claim are stale (see also #32). *Confirmed.*
    - `wf-status.md:112` "pure-Python rewrite (unverified)" is superseded by TODO `:177`
      (done 2026-05-28) but never updated — soft tension (History is append-only by design).

---

## 5. Docs-vs-code drift

35. **M — CLAUDE.md Stack table lists `chargrab-rs`, which does not exist**
    (`wftools/chargrab-rs/` absent; `docs/rust-ports.md:13` says "In progress"; the C++
    `wftools/chargrab/` was deleted). *Confirmed.*
36. **M — 4 docs reference `wftools/engine/stubs/scripting_stub.cc`** (level-building.md,
    coding-conventions.md, scripting-languages.md, linux-engine-port.md); the file moved to
    `engine/stubs/` in the directory reorganization.
37. **M — pre-increment convention (coding-conventions.md §4) is violated in *new* code**,
    not just legacy: 132 `i++` for-loops in non-vendor `wfsource/source`, including
    `audio/linux/music.cc:112,120,189` written 2026-04. Either enforce (the TODO sweep item)
    or soften the convention text.
38. **M — `docs/worldfoundry_milestone1_evaluation_plan.md` links twice to
    `worldfoundry_milestone1_evaluation.md`, which doesn't exist anywhere.**
39. **L — CLAUDE.md stale line number:** the wrong `(sin C, cos C, 0)` comment is now at
    `movement.cc:711`, not 698 (claim content otherwise correct and the formula at
    `physicalobject.hpi:50-52` verified).
40. **L — machine-specific paths committed in docs:** `docs/wf-edit-manual.md` links into
    `-home-will-WorldFoundry` (another user's Claude memory dir); `docs/wf-asset-browser.md`
    links `../../../.claude/plans/…` — both dead in any clean checkout.
41. **L — dead-on-Linux Windows-path asset probe:** `actor.cc:163-178` fopens
    `%s\..\levels.txt` / `objects.id` with backslash separators (debug name lookup silently
    returns "unknown"). Also the only real violations of the "assets via
    `HALGetAssetAccessor()` only" rule are non-asset I/O (saves, screenshots) — rule holds.
42. **L — smaller stale doc links:** `docs/scripting-languages.md` → qbert autopilot
    investigation moved under `docs/qbert/`; `docs/uv-seam-fix.md` → png moved under
    `wftools/wf_blender/docs/`; `docs/level-design-troubleshooting.md` → missing
    `memory/reference_zforth_bootstrap_words.md`; `docs/rust-ports.md` → deleted
    `recolib/hdump.cc`.

---

## 5. Collaborative editor stack — relay, CRDT, teardown, security

The load-bearing theme: the relay was built LAN-first but "Host a call" now forwards it
through a public `*.trycloudflare.com` tunnel, and the transport gained **no authentication**
in the move. `wfmut::resolve_actor` does real runtime bounds-checks (not asserts), so
peer/debug-supplied actor indices are safe at that layer — the exposure below is auth and
resource-exhaustion, not memory safety. The y-crdt pin was confirmed **v0.26.0**
(`Cargo.lock:1096`, `Cargo.toml:15`), so TODO.md's submodule claim is accurate.

### Relay (`wftools/wf_collab/src/bin/relay.rs`)

61. **H — no room authentication: any tunnel client can read and corrupt any room.**
    The join loop (`relay.rs:220-248`) accepts any `CH_CONTROL` frame, joins the
    client-named room, and immediately sends `full_state_sync()` (the entire level); any
    subsequent `CH_SYNC` frame is applied to the authoritative doc and fanned out
    (`relay.rs:279-285`) with no shared secret anywhere in the path. Once a host shares the
    tunnel link, anyone who learns or guesses the URL + room id downloads the full level,
    injects arbitrary CRDT edits every peer applies, and reads/forges chat and presence.
    *Confirmed (re-verified).*
62. **H — client-supplied `peer_id` is the map key with overwrite semantics → trivial
    per-peer eviction/DoS.** `room.peers.insert(peer_id.clone(), send_tx)` (`relay.rs:248`):
    a second client joining with a victim's id replaces the victim's `send_tx`, silently
    killing its update delivery; the attacker's later disconnect removes the shared entry
    (`relay.rs:317`). Two honest peers that both send an empty id both become `"anon"` and
    collide identically. *Confirmed (re-verified).*
63. **M — unbounded per-peer queue + uncapped room/peer maps → memory-exhaustion DoS.**
    Each peer gets an `mpsc::unbounded_channel` (`relay.rs:236`) and `fanout` pushes a full
    copy per peer with no backpressure (`relay.rs:127-133`); a peer that completes the WS
    handshake and never drains buffers the entire edit stream in RAM. Rooms are created on
    demand with no cap (`relay.rs:241`). Both reachable by any tunnel client (compounds #61).
    *Confirmed.*
64. **checked-clean — malformed-frame handling in the relay.** `load_snapshot`/`apply_sync`
    use `Update::decode_v1(...)?`-style guards and early-return on decode error
    (`relay.rs:70-73,117-125`); unknown channels are logged and ignored (`:307-309`). No
    panic-on-malformed-frame hole. *Confirmed clean.*

### Security posture of debug/REST/tunnel surfaces

65. **M — the debug bridge is an unauthenticated RCE-equivalent channel if bound
    non-locally.** Default bind is `127.0.0.1` and the cloudflared tunnel only forwards the
    relay port 9900 (`main.cc:1159`), so it is *not* exposed through "share a link" — but
    `--debug-bind 0.0.0.0` → `INADDR_ANY` (`debug_server.cc:512-513`) opens
    `reload_script` (runs attacker Forth in-engine, `:437-445`), `set_shader` (compiles
    attacker GLSL, `:447-455`), `inject_input` (`:409-435`), and `screenshot` (writes an
    attacker-named path, `:457-464`) with no credential. *Confirmed (re-verified bind +
    command surface).*
66. **checked-clean — cloudflared fetch SHA256 pinning.** `fetch-cloudflared`
    (`Taskfile.yml:238-257`) pins a per-arch SHA256, downloads to `$DEST.tmp`, verifies with
    `sha256sum -c`, and deletes-and-exits on mismatch before `chmod +x`/`mv`. Correct.

### Transaction discipline & teardown

67. **M — detached debug-bridge / REST threads can touch destroyed globals at exit.**
    `debug_server.cc:540` detaches each `handle_client`; a detached handler blocked in
    `::read` wakes on fd-close during `DebugServer_Stop`, then re-locks `gQueueMutex` and
    pushes to `gQueue` in cleanup (`:484-492`) — if that runs during static destruction the
    mutex/queue may already be gone (UAF). Same shape in `rest_api.cc:309` (listener thread
    never joined; `gServer` is deliberately leaked to dodge the UAF). Engine stubs
    (`WF_DEBUG_BRIDGE`/`WF_REST_API`), not linked into the editor, so scope is limited.
    *Plausible.*
68. **L — every Doc *read* opens a `kOriginLocal` write transaction** (`wfcrdt.cpp:47-51`
    via `Doc::begin()`, used by `ReadActorNames/Eids/Fields` at `level_doc.cc:629,643,702`).
    Harmless today (`CollabDrain` drops sub-2-byte frames, `main.cc:794`; the known
    `ReadActorNames` nested-txn crash is fixed by scoping the outer txn to commit first,
    `main.cc:3841-3846`) but fragile — defeats any future concurrent-reader assumption.
    *Plausible.*
69. **L — reconnect thread can stall shutdown for seconds.** Teardown sets `relay_shutdown`
    then joins `relay_reconnect_thread` (`main.cc:3945-3947`), but the abort seam is checked
    only between attempts (`connect_retry.h:91-98`) while `try_once` blocks in
    `WsClient::connect` up to 5 s per address (`ws_client.cc:179-195`). Unresponsive exit,
    not a crash. *Confirmed.*
70. **L (informational) — `fill_map`/`fill_array` is stale-but-harmless dead code**, not a
    bug: pin is v0.26.0 and the comment concedes the empty-then-populate pattern is now "a
    pure optimization with no functional payoff" (`wfcrdt.cpp:249-253`). TODO cleanup item is
    valid; no correctness defect.
71. **L (informational, forward-looking) — web identity persistence is a latent self-drop
    trap.** Current handling is correct: `LoadIdentity` rejects an empty `peer_id`
    (`main.cc:209`), web never persists identity (no `IDBFS`/`syncfs` for the config dir), so
    each tab mints a fresh `web-…` id exactly as TODO.md prescribes. If IDBFS identity
    persistence is ever wired, every tab would share one `peer_id` and the receiver's
    self-filter (`main.cc:813`) would reintroduce the presence/chat self-drop — guard the
    persistence seam when it lands. *Confirmed clean today.*

---

## 6. Repo hygiene

43. **H — runtime/build outputs are tracked in git:** `qbert_hiscores.txt` (rewritten by
    `hscore.cc:17` on every desktop play session — dirties the tree by playing the game) and
    `engine/pilot_bridge_runner` (3.4 MB unstripped ELF, committed 2026-05-30).
44. **M — 25 tracked `.mp4` demo recordings (~7.6 MB), 9 at repo root**; `.gitignore:83`
    covers only one specific output path. Combined with ~66 MB of regenerable `wflevels/`
    artifacts (81 `.iff.txt`/`.lvl`; two 13.8 MB `.iff.txt` files) and 30 MB of
    `docs/papers/` PDFs, the pack is 266 MiB and grows with every demo video. Decide: delete,
    git-lfs, or a release-artifacts location.
45. **L — README situation:** root has an empty tracked `README` plus `README.md` as a
    symlink → `wf-status.md`; GitHub renders neither usefully (symlinked READMEs aren't
    followed). Also root-level orphans `ht-codegen-repair-prompt.md` and
    `2026-05-10-fixed-point-platform-survey.pdf` belong under docs/ if kept.

---

## 6b. Tooling — Rust parsers, Blender addon, level scripts, shell

### Rust tools (levcomp-rs / textile-rs / oad_loader)

72. **M — the editor's decompile path panics on a malformed level.**
    `levcomp-rs/src/decompile.rs:113-123` (`build_object_names`) slices `lv_data` by header
    fields read straight from the file: `objects_offset = ri32(lv_data, 8)` then
    `&lv_data[objects_offset..]`, and per-object `obj_offset = ri32(obj_arr, index*4)` then
    `&lv_data[obj_offset..]` — none validated. The only header guard is `len >= 52` (:717);
    `obj_count` (offset 4) and `objects_offset` (offset 8) are unchecked. A compiled `.iff`
    with `objectCount = 0x40000000` or an out-of-range `objectsOffset` panics ("range end
    index out of range") instead of erroring cleanly. The **editor calls this on user files**.
    Second instance in the main emit loop (`:760,768`). *Confirmed (re-verified).*
73. **M — `textile-rs/src/texture.rs:68` (`parse_modl`) aborts the process via `assert_eq!`
    on a malformed `.iff`**: `assert_eq!(size % ENTRY, 0, "MATL size not a multiple…")` where
    `size` is file-supplied — a `MATL` sub-chunk whose in-range size isn't a multiple of 264
    panics. Should return an error. *Confirmed.*
74. **L/M — `levcomp-rs/src/oad_loader.rs:310-315`: a negative OAD `len` triggers a
    capacity-overflow panic.** `let len = entry.len as usize` (from an unvalidated `i16`) then
    `out.extend(repeat(0).take(len - copy))` — `len = -1` becomes ~1.8e19, `len - copy`
    underflows. A crafted `.oad` `BUTTON_STRING` entry with `len = -1` panics. *Confirmed.*
75. **L — `textile-rs/src/locfile.rs:14,21` byte-slice a `&str` assuming ASCII** — an asset
    filename ending in a multi-byte codepoint panics on a char boundary. *Plausible.*
76. **checked-clean:** the two-phase common-block emission (`lvl_writer.rs:146-162,254`) is
    correct — the builder is fully populated before the header reads its length; phase-1
    offsets match phase-2 bytes. `wf_iff::read_chunks`, `wf_oad`, `iffcomp-rs/writer.rs`,
    TGA loader, and byte-order handling are well-guarded. No `chargrab-rs` crate exists
    (matches §35).

### Blender addon (silent data loss)

77. **H — actor `Scale` round-trips lossily: exported but never imported.**
    `export_level.py:1068-1070` writes a `VEC3 "Scale"` chunk, but the importer only ever
    reads the first `VEC3` as Position (`:681`, matched by tag not name) and has no Scale
    handling. Export a scaled actor → re-import → scale silently resets to 1.0; the same loss
    exists in the levcomp decompile→recompile path (`decompile.rs:24` skips the Scale field).
    Defeats the mailbox-3040-3042 scale convention. *Confirmed.*
78. **H — field-emission failure is swallowed and export still reports success.**
    `export_level.py:1118-1123`: if `load_schema`/`_emit_lev_fields` throws (bad `.oad`, schema
    regression), the exception is logged to `/tmp/wf_export_errors.log` and export continues
    — the actor is written with **no OAD fields** (no Mobility, scripts, or mailboxes) yet the
    operator reports "Exported N objects." The level compiles and the actor silently
    misbehaves; on Windows the `open("/tmp/…")` in the handler itself throws. *Confirmed
    (re-verified).*
79. **M — LIGHT fields emitted twice** (`export_level.py:1124-1139`): `lightRed/Green/Blue/
    Type` come from both `_emit_lev_fields` (schema) and a hardcoded `is_light` block
    (`obj.data.color`); the two can disagree and break byte-identical round-trip. *Confirmed.*
80. **M — live-bridge schema failure silently swallowed** (`wf_blender/__init__.py:178-181`,
    `except Exception: enum_map = {}`): enum-label edits then coerce to `None`, are never
    pushed to the running engine, and the snapshot updates so it never retries. *Confirmed.*
81. **M — license-policy waivers are documented but unimplemented.**
    `wflevels/licence_policy.toml:78-88` defines `[[waiver]]` per-asset overrides, but
    `blender_asset_finder/providers.py` `load_policy` (`:191-241`) never reads a `waiver` table
    and `Policy` has no field for it — the override mechanism silently does nothing. (The
    TODO's "OpenGameArt CC0 gate wrongly rejects CC-BY" is *not* a bug: rejecting CC-BY-4.0 is
    policy-correct per the toml. But OGA 3.0 licences map to `UNKNOWN`→rejected, and provider
    errors are swallowed to `[]` at `:534-537,668-671`, making a dead endpoint
    indistinguishable from "no matches.") *Confirmed.*
82. **L/M — hardcoded foreign paths:** `smb_model_gallery.py:6`
    `REPO = "/home/will/WorldFoundry.2026-new-level"` breaks the render script for any other
    checkout; dead `/home/will/…` OAD fallbacks at `export_level.py:592-595` (mitigated by a
    `__file__` walk-up). Same `-home-will-` foreign-path family as §40. *Confirmed.*

### Level-authoring scripts

83. **M — production levels load schemas from the oas2oad *test-fixtures* directory —
    11 scripts, not the 2 the TODO lists.** All of `smb_w1_1/2/3/4`, `moon_site01`, and six
    `marble-madness/blender_mm_*.py` set
    `OAD_DIR = REPO/wftools/wf_oad/tests/fixtures` (verified by grep). The same schemas exist
    in the intended `wflevels/oad/`; the fixtures dir is maintained as test data (last touched
    by the `1c82130f` oas2oad fix), so a fixture regeneration can silently change or drop the
    schemas these levels depend on. `qbert_practice` and `mm_practice` point at a *third*
    location (`wfsource/source/oas`), so there are **three competing OAD dirs**;
    filesys/filelight/dome/treemap correctly use `wflevels/oad`. *Confirmed (re-verified — the
    TODO undercounts this).*
84. **L — W1-3/W1-4 are NOT stale forks** (checked as requested): both `import smb_common` and
    delegate to shared helpers; locally-defined functions are genuinely level-specific
    wrappers. The single-sourcing consolidation holds. *Confirmed clean.*
85. **M — `scripts/blender_create_level.py:20-23,33` walks up two levels from `scripts/`**
    (`REPO = normpath(join(SCRIPT_DIR, '..', '..'))`), landing outside the repo, so
    `SNOWGOONS_LEV`/`OAD_DIR` resolve to nonexistent paths — the script fails at import.
    (Its docstring names it `blender_create_mm_practice.py`, so it was relocated and never
    fixed.) *Confirmed.*

### Shell scripts

86. **`set -euo pipefail` audit: no violations** — all 11 `.sh` files plus `git-hooks/pre-commit`
    set it before any statement. *Confirmed clean.*
87. **H — `scripts/apt-worldfoundry-bootstrap.sh` is inoperable.** It requires `foundry-apt/`
    (`:39,127`), deleted 2026-05-20 (commit `411f1ef8`), so it always dies at preflight; its
    `usage()` also names the wrong file. *Confirmed.*
88. **M — same script leaks the GPG *private* signing key in `/tmp`.** The armored secret key
    is written to a fixed `/tmp/foundry-packages.sec.gpg` with default umask before `chmod
    600` (`:48-49,319-321`), and the `cleanup()` trap (`:84-89`) doesn't remove it — a
    mid-script `set -e` failure leaves the signing key on a shared machine. (Currently
    unreachable because of #87, but a landmine when that's fixed.) *Confirmed.*
89. **L — screenshot smoke scripts' EXIT trap references PIDs set later**
    (`tests/screenshot_two_peer_b2.sh:34`, `screenshot_three_peer_b2.sh:31`): under `set -u`
    an early exit makes the trap itself error, so the background `wf-relay` on 9991 leaks;
    `smoke_relay_reconnect.sh:26` shows the correct pre-init pattern. Also `DISPLAY=:0` is
    hardcoded across the peer/relay smoke scripts (fails off `:0`/Wayland/headless). *Plausible/
    Confirmed.*

---

## 7. Verified-clean areas

- Plans index ↔ files: **no drift either direction** (312/312).
- CLAUDE.md: build tasks, zForth default, `currentDir` formula, `bl_to_wf` identity,
  scale mailboxes 3040-3042, pipeline description — all verified accurate (modulo #39).
- CMakeLists: every listed source/include path exists; Taskfile deps parse; CI workflow file
  references all exist.
- Jolt bridge threading (single-threaded job system, synchronous contact callbacks),
  `PhysicalAttributes` member init, guarded `1/dt` divides in `JoltCharacterUpdate` — clean.
- `iffcomp-rs` (3) and `levcomp-rs` (7) cargo tests pass.
- Mailbox scope rules and mesh-origin rule in level-building.md match code/scripts.

## 8. Review coverage gaps (recommended follow-up)

All originally-planned review streams have now reported and been reconciled (the plans-audit
stream's residual items — physics TODO-knob accuracy, `cd_full.iff.txt`, wf-status staleness —
are folded into §4). Remaining coverage is thin only here:

- **`.github/workflows/*` and a full line-by-line `codemagic.yaml` pass** beyond the duplicate
  key (#23) and the shadowed-workflow SIGPIPE (#27) — the config review confirmed the file
  parses and all referenced paths exist, but did not read every step for logic errors.
- **Deeper Rust-crate logic** beyond parser panic-safety (e.g. semantic correctness of
  textile's PERM/atlas packing, iffcomp offset arithmetic) — spot-checked, not exhaustively
  read.

*(`game/`+`gfx/`+syscalls: §1b · collab stack: §5 · Rust/Blender/scripts tooling: §6b.)*
