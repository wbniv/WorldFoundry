# Plan — Q*bert apex respawn on round clear

## Context

Round-clear reset ships (2026-05-04): all 28 cubes flipping to state 2 triggers a
90-tick countdown, after which cube states reset to 0 and `mb[425]` (ROUND_NUMBER)
increments. Q*bert is left wherever they were when the last cube flipped. The arcade
always respawns Q*bert at the pyramid apex at the start of each round. This plan wires
that into the existing round-clear expiry block.

## Scope

Single file: `wflevels/qbert_practice/blender_create_qbert.py` — `DIRECTOR_SCRIPT`
only. No engine/runtime changes.

Out of scope:
- Drop-in animation on respawn (the intro animation plays only on level load;
  for now Q*bert simply teleports to the apex position — same behaviour as the
  game-over restart block)
- Per-round palette swap (separate plan)
- Suppressing fall-death during the 90-tick window (noted as future work in the
  round-clear plan; not addressed here)

## Implementation

### Apex coordinates (verified from hop formula + game-over restart block)

| Mailbox | Value | Meaning |
|---------|-------|---------|
| `mb[400]` | 0 | grid col |
| `mb[401]` | 0 | grid row |
| `mb[402]` | 0 | hop cooldown (clear so first hop is immediate) |
| `INDEXOF_X_POS` | 0 | world x |
| `INDEXOF_Y_POS` | 6 | world y |
| `INDEXOF_Z_POS` | 15 | world z (top of apex cube) |

Also clear residual fall state that may be live if Q*bert fell during the countdown:

| Mailbox | Name | Value |
|---------|------|-------|
| `mb[414]` | FALL_DEATH | 0 |
| `mb[415]` | death-hold timer | 0 |
| `mb[419]` | fall-animation timer | 0 |

### Change — as implemented (diverged from original plan)

`INDEXOF_X/Y/Z` (3009–3011) are LOCAL_SYSTEM mailboxes. Writing them from the director
only moves the director actor, not Q*bert. The director can write global user mailboxes
(2–999) but cannot teleport another actor. A signal mailbox is required.

**Director expiry block** — append after `425 read-mailbox 1 + 425 write-mailbox`:

```forth
0 400 write-mailbox 0 401 write-mailbox 0 402 write-mailbox
0 414 write-mailbox 0 415 write-mailbox 0 419 write-mailbox
1 426 write-mailbox
```

**Player script** — new block 1.5 (after game-over check, before fall animation):

```forth
426 read-mailbox 1 = if
  0 INDEXOF_X_POS write-mailbox 6 INDEXOF_Y_POS write-mailbox 15 INDEXOF_Z_POS write-mailbox
  0 426 write-mailbox
then
```

`mb[426]` = RESPAWN_REQUESTED. Previously unused.

### Why each mailbox

- **mb[400/401]**: grid position used by the hop-address formula
  (`col*(col+1)/2 + row + 200`). Must match world position or the next hop calculates
  from the wrong cell.
- **mb[402]**: hop cooldown. May be nonzero if Q*bert hopped just before the last cube
  flipped. Clearing it lets the player move immediately in the new round.
- **mb[414/415/419]**: fall-death, camera death-hold, fall-animation timer. If Q*bert
  fell during the 90-tick celebration these may be live; clearing prevents a stale death
  sequence running after the reset.
- **mb[426]**: RESPAWN_REQUESTED signal. Set by director, cleared by player after
  teleporting. Necessary because INDEXOF_X/Y/Z writes only affect the calling actor.

## Rebuild steps

```bash
# 1. Blender headless export
blender --background --python wflevels/qbert_practice/blender_create_qbert.py

# 2. Level binary pipeline
bash wftools/wf_blender/build_level_binary.sh qbert_practice

# 3. Standalone wrapper
cd wflevels/qbert_practice
../../wftools/iffcomp-rs/target/release/iffcomp \
  -binary -o=qbert_practice-standalone.iff qbert_practice-standalone.iff.txt
cp qbert_practice-standalone.iff ../
```

## Verification

Use the same automated injection approach as round-clear verification:

1. Temporarily add `28 0 do 2 200 i + write-mailbox loop` to the first-tick init block
   (sets all cubes to state 2 on tick 1 → triggers countdown immediately).
2. Run with debug bridge + video:
   ```
   engine/wf_game -Lwflevels/qbert_practice-standalone.iff \
     -record_video --debug-port 7777 --debug-bind 127.0.0.1
   ```
3. Python monitor watches `mb[400]`, `mb[401]`, `mb[402]`, `mb[424]`, `mb[425]`.
4. Expected on timer expiry: `mb[400]=0`, `mb[401]=0`, `mb[402]=0`, `mb[424]=0`,
   `mb[425]=1`.
5. Remove test injection and rebuild clean.

Manual check: play to the last cube, wait ~1.5 s — Q*bert should snap to the apex
(top of the pyramid) at the moment the cubes turn purple.

## Risks

- **Mid-fall at reset**: if Q*bert is falling when the expiry fires, clearing mb[419]
  mid-animation may produce a visual jump. Acceptable for MVP; fix later by only
  teleporting when `mb[414] == 0` (not in a fall).
- **mb[420] GAME_OVER conflict**: if the player ran out of lives during the countdown,
  mb[420]=1 is set and the game-over restart path takes over. Round-clear expiry still
  fires, resetting position — but the game-over overlay is visible and waiting for
  button input, so the player won't see the respawn until they press a direction. This
  interaction is acceptable for MVP.
