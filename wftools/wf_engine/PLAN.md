# WF Engine — Start Snowgoons Level Directly

## Context

The `wf_game` binary builds and runs. The engine loads `cd.iff`, which is a multi-level
archive. Currently it tries to run the "cubemenu shell" level (L0) first, which relies on
Tcl scripts to write `EMAILBOX_LEVEL_TO_RUN` so the real level loads. Scripting is
disabled (NullInterpreter). Goal: boot directly into snowgoons (L4 in cd.iff), which has
the most complete assets.

Two bugs block a clean run:

1. **`_desiredLevelNum` uninitialized** — the `assert(_desiredLevelNum >= 0)` at
   `game.cc:189` fires (or succeeds by luck with garbage value = 0). The
   `_overrideLevelNum` check that would let the `-l 4` flag work sits *after* the
   assert (line 194), so it never helps.

2. **EMAILBOX_CAMSHOT never set** — `DelayCameraHandler` (`movecam.cc:885`) asserts
   after 5 frames because no script writes a CamShot object index to mailbox 1021.
   The current workaround in `level.cc:227` writes the *player* object index, which
   is wrong — `NormalCameraHandler::init()` then casts it to `CamShot*` and asserts
   at `movecam.cc:479`.

---

## Fix 1 — `game.cc`: default `_desiredLevelNum = 4`, move override check before assert

**File:** `wfsource/source/game/game.cc`

In `WFGame::WFGame()` constructor initializer list (line ~68), initialize
`_desiredLevelNum` to 4:

```cpp
WFGame::WFGame( const int nStartingLevel )
    :
    _msgPortMemPool( MemPoolConstruct( sizeof( SMsg ), MSGPORTPOOLSIZE, HALLmalloc ) ),
    _overrideLevelNum( nStartingLevel ),
    _desiredLevelNum( 4 )          // ← add: snowgoons by default
{
```

In `RunGameScript()` (line ~189), move the `_overrideLevelNum` check to *before* the
asserts:

```cpp
// Move these 2 lines UP, before the asserts:
if(_overrideLevelNum != -1)
    _desiredLevelNum = _overrideLevelNum;

assert(_desiredLevelNum >= 0);
assert(_desiredLevelNum < 9999);
```

This lets `-l N` (the existing command-line override) select any level.

---

## Fix 2 — `level.cc`: track first CamShot, write its index to EMAILBOX_CAMSHOT

**File:** `wfsource/source/game/level.cc`

Replace the current incorrect bootstrap (which writes the *player* index) with one that
tracks the first CamShot object and writes *its* index.

In `constructObject()` (~line 218), change the `Player_KIND` branch to only do player
setup, and add a `CamShot_KIND` branch alongside it:

```cpp
if ( pCreatedActor->kind() == Actor::Player_KIND )
{
    setMainCharacter( pCreatedActor );
    updateMainCharacter();
    // REMOVED: wrong EMAILBOX_CAMSHOT write was here
}
else if ( pCreatedActor->kind() == Actor::CamShot_KIND )
{
    // Bootstrap camera when scripting is disabled:
    // write first CamShot's index to EMAILBOX_CAMSHOT so
    // DelayCameraHandler transitions instead of asserting.
    if ( GetMailboxes().ReadMailbox( EMAILBOX_CAMSHOT ) == Scalar(0,0) )
        GetMailboxes().WriteMailbox( EMAILBOX_CAMSHOT, Scalar( index, 0 ) );
}
else if ( pCreatedActor->kind() == Actor::Camera_KIND )
{
    ...
```

The guard `ReadMailbox == 0` ensures only the first CamShot sets the mailbox (matching
what the original ActBoxOR script would have done).

---

## Critical files

| File | Change |
|------|--------|
| `wfsource/source/game/game.cc` | Init `_desiredLevelNum(4)`; move override check before asserts |
| `wfsource/source/game/level.cc` | Replace player-index write with CamShot_KIND branch |

---

## Verification

```bash
cd wfsource/source/game
LD_LIBRARY_PATH=../../../wftools/wf_engine/libs DISPLAY=:0 ../../../wftools/wf_engine/wf_game
```

Expected: engine loads L4 (snowgoons), no assertion in `movecam.cc`, X11 window
displays level geometry. If `-l N` flag works, test with `-l 1` (primitives) to
confirm the override path.
