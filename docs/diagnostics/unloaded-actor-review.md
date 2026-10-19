# Confirmed: moving an actor from an inactive source room leaves stale membership

**Update:** Will authorized a repair after this reproduction. See the
[fix and correctness regression](unloaded-actor-fix.md). The historical
observations below remain the pre-fix evidence.

Reproduced 2026-10-09 on `teleport-audit`, engine commit `c92ca353`, documentation
HEAD `ffe4f94b`. No engine code changed for this investigation.

The active Player's Forth script writes actor 20's X/Y/Z position from
(295, 0, 7), inside inactive room D, to (-5, 0, 7), inside active room A.
Actor 20 is an anchored redball marked **Moves Between Rooms**. Actor 21 is
an otherwise equivalent control authored in A. The camera watches the Player.
Each actor has a distinct global heartbeat mailbox (480/481/482); mailbox
indices below 1901 are global, so actor identity alone does not isolate them.

| Native release observation | Never loaded D | D loaded once, then unloaded |
|---|---:|---:|
| Target X after script | -5 | -5 |
| Target heartbeat before / after 120 Player updates | 0 / 0 | 7 / 7 |
| Control heartbeat immediately after move / after wait | 27 / 147 | 33 / 153 |
| Target heartbeat after visiting D and returning to A | 37 | 42 |

Both variants also reproduced with assertions enabled. Its logs directly show:

`Room::UpdateRoomContents: object 20 kind=6 pos=(-5,0,7) fell out of room 3 ...; re-adding`

That line appears when the Player activates D, despite the target already being
physically inside A. This confirms stale source-room membership, rather than
merely failure to bind a never-loaded actor. In each variant the target remains
invisible in A during the stall and appears after the source-room visit.
See [stalled screenshot](unloaded-actor/release/never-loaded/stalled-in-A.png)
and [recovered screenshot](unloaded-actor/release/never-loaded/recovered-in-A.png).
The screenshots are dark because the existing fixture's lighting is minimal;
the additional redball is visible left of the Player after recovery.

## Code path

- [actor.cc:1458](../../wfsource/source/game/actor.cc#L1458): position mailbox
  setters change the physical pose and call `NotifyPositionWrite`.
- [level.cc:1289](../../wfsource/source/game/level.cc#L1289): notification only
  records the camera's watched object. Actor 20 is not watched.
- [level.cc:1061](../../wfsource/source/game/level.cc#L1061): membership repair
  iterates only active rooms. Inactive D therefore retains actor 20.
- [room.cc:270](../../wfsource/source/room/room.cc#L270): the source room removes
  and re-adds objects whose poses lie outside it, once that room is visited.
- [level.cc:990](../../wfsource/source/game/level.cc#L990): prediction and physics
  updates use active-room lists, explaining the frozen script heartbeat.
- [level.cc:1259](../../wfsource/source/game/level.cc#L1259): rendering uses each
  active room's render list, explaining the missing actor in A.
- [actrooms.cc:231](../../wfsource/source/room/actrooms.cc#L231): an arriving
  room binds previously unbound Moves Between Rooms actors permanently.
  Previously bound actors still reproduce the defect, so binding alone is
  insufficient to fix it.

## Reproduce

From the engine worktree, with a GL display and the existing native compiler tools:

```sh
python3 tests/generate_teleport_level.py --tools /home/will/WorldFoundry-wbniv/wftools --out /tmp/t4-unloaded-fixture --camera follow --unloaded-actor
python3 tests/reproduce_unloaded_actor.py --binary engine/wf_game --level /tmp/t4-unloaded-fixture/teleport_regression-standalone.iff --out /tmp/t4-unloaded-evidence
```

The bridge only requests Player command 7 and reads observations; the Player
script performs all target position writes. The harness checks both variants,
requires at least 120 completed Player updates, compares the active control,
and requires recovery after source activation. A successful harness exit means
**the defect reproduced**, not that the engine passed a correctness regression.
The historical defect mode is not registered in CTest. The subsequently added
`--expect-fixed` mode is registered as `unloaded_actor_teleports` and requires
prompt updates without a source-room visit.

## Evidence and limits

- [x] Native release: both variants reproduced, screenshots and receipts retained.
- [x] Assertions-enabled native engine: both variants reproduced, direct stale-room diagnostics retained.
- [x] No assertion, UBSan, nil-pointer or script errors in the final runs.
- [x] Default following-camera fixture regenerated unchanged: SHA-256
  `9f452ca4c2102c572104c100aa1d6c95e52ffbee4cd3cf25a506202aac4a4f57`.
- [x] Reproduction fixture SHA-256:
  `00f10e9b88c3189ad6735720929eb2e79d25814cd74e1605beea5e6689d443c4`.
- [x] Subsequent engine repair and correctness regression asserting next-frame
  target updates: [fix review](unloaded-actor-fix.md).
- [ ] Android/Chromecast verification of this specific case.

Raw evidence is under [unloaded-actor/](unloaded-actor/): release and assertions
logs, per-run receipts with executable/fixture hashes, and screenshots. Fixture
source, compiler transcript, input/tool hashes and the compiled standalone level
are retained under `unloaded-actor/fixture/`. The assertions executable predates
the final transform-API notification line; its script mailbox path matches the
release engine tested here. No mocked room implementation or engine diagnostic
patch was used.

Next implementation needs to reconcile non-watched position writes with room
membership, including deferred binding for actors never loaded before. This
reproduction does not choose when to migrate between separate X/Y/Z writes or
change which inactive actors normally run scripts.
