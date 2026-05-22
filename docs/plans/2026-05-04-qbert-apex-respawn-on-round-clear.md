# Plan — Q*bert apex respawn on round clear

See full plan at `docs/plans/2026-05-04-qbert-apex-respawn.md`.

## Status: COMPLETE (2026-05-04)

Implementation shipped and built. The original plan's `INDEXOF_X/Y/Z` writes from the director were incorrect — those are LOCAL_SYSTEM mailboxes (3009–3011) that only move the calling actor. Writing them from the director moved the invisible director, not Q*bert.

## What was actually implemented

**Director round-clear expiry block** (`blender_create_qbert.py` ~line 625):
- Keeps: cube reset (mb[200..227]=0), mb[411/413]=0, mb[425]++
- Keeps: mb[400/401/402/414/415/419]=0 (global user mailboxes — director can write these)
- Replaces INDEXOF_X/Y/Z writes with: `1 426 write-mailbox` (RESPAWN_REQUESTED signal)

**Player script** (new block 1.5, after game-over check, before fall animation):
```forth
426 read-mailbox 1 = if
  0 INDEXOF_X_POS write-mailbox 6 INDEXOF_Y_POS write-mailbox 15 INDEXOF_Z_POS write-mailbox
  0 426 write-mailbox
then
```

## Key finding documented

`INDEXOF_X/Y/Z` are local-system mailboxes. The director cannot teleport the player
by writing them — use a signal mailbox that the player script reads in its own context.
Documented in `feedback_wf_mailbox_scope_and_indexof.md` and the new "Mailbox scope
rules" section in `docs/level-building.md`.

## Verification needed

Run with debug bridge + all-state-2 injection, confirm:
- mb[400]=0, mb[401]=0, mb[425]=1 on timer expiry (same as before)
- Q*bert visually snaps to apex at round reset (was broken before fix)
- Apex cube flips to state 2 when Q*bert lands (hop detection works in round 2)
