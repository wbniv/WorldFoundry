# Moon Site 01 — Ground Clamping + Extra Cruisers + Vehicle Physics

**Status:** Not started

**Context:** Three related tasks:
1. All placed assets sit at Z=0, floating above/below uneven lunar terrain.
2. Add two more Lunar Cruisers near camp (3 total fleet).
3. GTA-style enter/drive/exit with real Jolt VehicleConstraint + WheelSettings.

Camera fix is being handled separately. No camera code here.

---

## Fix A — Ground clamping

**Problem:** Every `_place_prop(obj, (x, y, 0.0))` hard-codes Z=0. LOLA terrain ranges −124.7 to +13.7 m.

**Fix:** Add `terrain_z(wx, wy)` to `blender_create_moon.py`, sampling the already-loaded `heights` array:

```python
def terrain_z(wx, wy):
    col = max(0.0, min(float(N - 1), (wx + HALF_M) / CELL_M))
    row = max(0.0, min(float(N - 1), (wy + HALF_M) / CELL_M))
    return float(heights[int(round(row)), int(round(col))])
```

Update all six `_place_prop` calls to `(x, y, terrain_z(x, y))`. All builder functions already place their lowest geometry at mesh-local Z=0.

---

## Feature B — Two more Lunar Cruisers

**Mesh sharing:** Call `_build_lunar_cruiser()` once, then create the other two as `bpy.data.objects.new(name, first.data)` — shared mesh datablock, avoids duplicate .iff entries.

Rename existing Cruiser to `lunar_cruiser_0`.

**New placements:**
- `lunar_cruiser_1` at `(-50.0, 0.0, terrain_z(-50, 0))`
- `lunar_cruiser_2` at `(10.0, -40.0, terrain_z(10, -40))`

---

## Feature C — GTA entry/drive/exit with Jolt vehicle physics

### C1. New C++ mobility type

Add `MOBILITY_VEHICLE = 5` to `wfsource/source/oas/movement.h` enum (after `MOBILITY_FOLLOW = 4`).

This is an enum extension appended at the end — no existing OAD field offsets shift, so binary compatibility with all existing levels is preserved. Safe per the OAD compat policy ("enum extensions OK").

### C2. New file: `wfsource/source/physics/jolt/jolt_vehicle.cc`

Implements Jolt `WheeledVehicleController` for the Lunar Cruiser. Key sections:

**Wheel layout** (from `_build_lunar_cruiser()` geometry, WF axes: X=forward, Y=left, Z=up):

```cpp
// 6 wheels: fore/mid/aft × port/starboard
// Radius 0.7 m, half-width 0.175 m, suspension travel 0.3 m
static const struct { float x, y, z; bool steer; } kCruiserWheels[6] = {
    { 1.9f,  2.6f, 0.35f, true  },   // front-port   (steerable)
    { 1.9f, -2.6f, 0.35f, true  },   // front-stbd
    { 0.0f,  2.6f, 0.35f, false },   // mid-port
    { 0.0f, -2.6f, 0.35f, false },   // mid-stbd
    {-1.9f,  2.6f, 0.35f, false },   // rear-port
    {-1.9f, -2.6f, 0.35f, false },   // rear-stbd
};
```

Note: wheel Z is suspension rest-length (0.35m ≈ half wheel radius), not wheel centre height. The chassis box sits above this.

**`JoltVehicleCreate(Actor*, PhysicsSystem&)`:**
- Box shape for chassis: 5.5 × 4.5 × 2.2 m (matches mesh)
- Body created as `EMotionType::Dynamic`, layer `Layers::MOVING`
- Per-wheel: `WheelSettingsWV` with position, radius, max steer angle (±25° for steerable wheels, 0 for others)
- `WheeledVehicleControllerSettings`: engine `mMaxTorque` = 1500 N·m, `mMaxRPM` = 1000
- `VehicleConstraint` added to `PhysicsSystem`
- Returns `JoltVehicleHandle` stored on the actor alongside existing Jolt body data

**`JoltVehicleUpdate(JoltVehicleHandle*, float dt, uint32_t input_bits)`:**
```cpp
float forward   = (input_bits & EJ_BUTTONF_UP)   ? 1.0f : (input_bits & EJ_BUTTONF_DOWN)  ? -1.0f : 0.0f;
float rightward = (input_bits & EJ_BUTTONF_RIGHT) ? 1.0f : (input_bits & EJ_BUTTONF_LEFT)  ? -1.0f : 0.0f;
float brake     = (input_bits & EJ_BUTTONF_DOWN) && forward < 0 ? 1.0f : 0.0f;
controller->GetWheeledVehicleController()->SetDriverInput(forward, rightward, brake, 0.0f);
```

After `PhysicsSystem::Update`: read `VehicleConstraint::GetVehicleBody()→GetPosition()` → push to actor's `_physicalAttributes`.

**`JoltVehicleDestroy(JoltVehicleHandle*)`:** removes constraint + body from physics system.

**Variable dt:** Jolt `PhysicsSystem::Update(dt, ...)` already handles variable dt for the constraint. No fixed-step wrapper needed — the existing WF variable-tick architecture is compatible.

### C3. Movement handler: `wfsource/source/movement/movevehicle.cc`

New `MovementHandlerVehicle` registered for `MOBILITY_VEHICLE`:
- `Init()`: calls `JoltVehicleCreate`
- `Update(float dt)`: reads actor's local `INPUT` mailbox bits → calls `JoltVehicleUpdate(dt, input_bits)`
- `Destroy()`: calls `JoltVehicleDestroy`

Hook into the `MovementHandlerArray` in `actor.cc` at the `MOBILITY_VEHICLE` slot.

### C4. New mailboxes — `wfsource/source/mailbox/mailbox.inc`

Last moon mailbox is `MOON_LANDER_Z = 1885`. Add after it:

```
MAILBOXENTRY( MOON_CRUISER_0_IDX,   1886 )  Comment("Actor index of lunar_cruiser_0")
MAILBOXENTRY( MOON_CRUISER_1_IDX,   1887 )  Comment("Actor index of lunar_cruiser_1")
MAILBOXENTRY( MOON_CRUISER_2_IDX,   1888 )  Comment("Actor index of lunar_cruiser_2")
MAILBOXENTRY( MOON_NEARBY_VEHICLE,  1889 )  Comment("0=none, 1/2/3=which cruiser player is adjacent to")
MAILBOXENTRY( MOON_ACTIVE_VEHICLE,  1890 )  Comment("0=on foot, 1/2/3=currently in cruiser N")
MAILBOXENTRY( MOON_PLAYER_VIS,      1891 )  Comment("Player visibility: 1=visible, 0=hidden (in vehicle)")
MAILBOXENTRY( MOON_ACTIVE_VEH_IDX, 1892 )  Comment("Actor index of vehicle player is in (for write-actor-mailbox)")
MAILBOXENTRY( MOON_VEHICLE_X,       1893 )  Comment("Active vehicle X; published by vehicle script each tick")
MAILBOXENTRY( MOON_VEHICLE_Y,       1894 )  Comment("Active vehicle Y")
MAILBOXENTRY( MOON_VEHICLE_Z,       1895 )  Comment("Active vehicle Z")
```

All within `GLOBAL_USER_MAX = 1900`. ✓

### C5. Entry ActBox per Cruiser — `blender_create_moon.py`

One ActBox beside the driver's door (+X airlock face) at each Cruiser's **initial parking position**. ActBoxes are world-space Anchored — they do not follow a moving vehicle. This is fine for first-board; re-boarding after driving is deferred (see limitations below).

```python
def _add_entry_trigger(cx, cy, cz, vehicle_id):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(cx + 5.5, cy, cz + 2.0))
    trig = bpy.context.object
    trig.scale = (3.0, 4.0, 2.0)           # ~6×8×4 m trigger volume
    bpy.ops.object.transform_apply(scale=True)
    attach_schema(trig, 'actbox')
    trig['wf_MailBox']                 = 1889   # MOON_NEARBY_VEHICLE
    trig['wf_MailBoxValue']            = vehicle_id
    trig['wf_ClearOnExit']             = 'True'
    trig['wf_Mailbox Exit Value']      = 0.0
    trig['wf_Activated Actor Mailbox'] = 4005   # crash workaround — default 0 aborts
    trig['wf_Mobility']                = 'Anchored'
    trig.name = f'entry_trigger_{vehicle_id}'
```

### C6. Cruiser actor setup — `blender_create_moon.py`

Change all three Cruisers to `Mobility='Vehicle'` (maps to `MOBILITY_VEHICLE = 5`). Existing OAD movement fields (mass, falling acceleration) still apply to the Jolt rigid body; the vehicle-specific params (engine torque, wheel config) are hardcoded in `jolt_vehicle.cc` for now.

```python
cruiser['wf_Mobility']             = 'Vehicle'
cruiser['wf_Mass']                 = 6000.0   # kg — Toyota Lunar Cruiser target mass
cruiser['wf_Falling Acceleration'] = 1.62     # lunar g applied to chassis rigid body
```

### C7. Cruiser Forth scripts

Each Cruiser publishes its actor index and, when active, its position:

```forth
\\ wf
INDEXOF_ACTOR_INDEX read-mailbox INDEXOF_MOON_CRUISER_0_IDX write-mailbox

INDEXOF_MOON_ACTIVE_VEH_IDX read-mailbox INDEXOF_ACTOR_INDEX read-mailbox = if
    INDEXOF_X_POS read-mailbox INDEXOF_MOON_VEHICLE_X write-mailbox
    INDEXOF_Y_POS read-mailbox INDEXOF_MOON_VEHICLE_Y write-mailbox
    INDEXOF_Z_POS read-mailbox INDEXOF_MOON_VEHICLE_Z write-mailbox
then
```

(cruiser_1 and cruiser_2 use `MOON_CRUISER_1_IDX` / `MOON_CRUISER_2_IDX` respectively.)

### C8. Player Visibility Mailbox

Change `player['wf_Visibility Mailbox']` from hardcoded `1` (constant TRUE) to `1891` (`MOON_PLAYER_VIS`). Player script seeds `1` each tick on foot, writes `0` on entry.

### C9. Player Forth script — entry/exit + driving state machine

Enter/exit button: verify exact bit at implementation (`kBtnInteract` placeholder — check `movement.h`/`joy.h`; must be non-jump).

```forth
\\ wf
\ ── on-foot mode ─────────────────────────────────────────────────────────────
INDEXOF_MOON_ACTIVE_VEHICLE read-mailbox 0 = if
    1 INDEXOF_MOON_PLAYER_VIS write-mailbox
    INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox INDEXOF_INPUT write-mailbox
    \ ... existing HUD + launch-phase code (unchanged) ...

    INDEXOF_MOON_NEARBY_VEHICLE read-mailbox 0 > if
        INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox kBtnInteract & 0 > if
            INDEXOF_MOON_NEARBY_VEHICLE read-mailbox INDEXOF_MOON_ACTIVE_VEHICLE write-mailbox
            0 INDEXOF_MOON_PLAYER_VIS write-mailbox
            0 INDEXOF_INPUT write-mailbox
            \ Resolve vehicle ID → actor index
            INDEXOF_MOON_NEARBY_VEHICLE read-mailbox 1 = if
                INDEXOF_MOON_CRUISER_0_IDX read-mailbox INDEXOF_MOON_ACTIVE_VEH_IDX write-mailbox then
            INDEXOF_MOON_NEARBY_VEHICLE read-mailbox 2 = if
                INDEXOF_MOON_CRUISER_1_IDX read-mailbox INDEXOF_MOON_ACTIVE_VEH_IDX write-mailbox then
            INDEXOF_MOON_NEARBY_VEHICLE read-mailbox 3 = if
                INDEXOF_MOON_CRUISER_2_IDX read-mailbox INDEXOF_MOON_ACTIVE_VEH_IDX write-mailbox then
        then
    then
then

\ ── in-vehicle mode ──────────────────────────────────────────────────────────
INDEXOF_MOON_ACTIVE_VEHICLE read-mailbox 0 > if
    0 INDEXOF_INPUT write-mailbox

    \ Snap player to vehicle so chase cam follows
    INDEXOF_MOON_VEHICLE_X read-mailbox INDEXOF_X_POS write-mailbox
    INDEXOF_MOON_VEHICLE_Y read-mailbox INDEXOF_Y_POS write-mailbox
    INDEXOF_MOON_VEHICLE_Z read-mailbox INDEXOF_Z_POS write-mailbox

    \ Route joystick → vehicle INPUT via write-actor-mailbox ( val idx actor -- )
    INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox
    INDEXOF_INPUT
    INDEXOF_MOON_ACTIVE_VEH_IDX read-mailbox
    write-actor-mailbox

    INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox kBtnInteract & 0 > if
        0 INDEXOF_MOON_ACTIVE_VEHICLE write-mailbox
        0 INDEXOF_MOON_ACTIVE_VEH_IDX write-mailbox
        1 INDEXOF_MOON_PLAYER_VIS write-mailbox
    then
then
```

### Known limitations (deferred)

- **Re-boarding after driving:** ActBox stays at initial parking spot. After driving away and returning, the player can't re-enter until proximity-based detection replaces the ActBox (needs all vehicles publishing position globals, or `read-actor-mailbox` primitive).
- **"Press B to enter" HUD prompt:** HUD polish pass.
- **Exit offset:** player exits at vehicle origin, not at a door. Add door-offset once basic exit works.
- **Steering feel:** front-only steering (`max_steer_angle` on front pair) gives a natural turn radius; tune engine torque and suspension stiffness against the real lunar-g feel.

---

## Files changed

| File | Changes |
|---|---|
| `wfsource/source/oas/movement.h` | Add `MOBILITY_VEHICLE = 5` |
| `wfsource/source/physics/jolt/jolt_vehicle.cc` | **New** — `JoltVehicleCreate/Update/Destroy`, Lunar Cruiser wheel config |
| `wfsource/source/movement/movevehicle.cc` | **New** — `MovementHandlerVehicle` for `MOBILITY_VEHICLE` |
| `wfsource/source/game/actor.cc` | Register `MovementHandlerVehicle` in `MovementHandlerArray` |
| `wfsource/source/mailbox/mailbox.inc` | 10 new `MOON_` entries (1886–1895) |
| `wflevels/moon_site01/blender_create_moon.py` | `terrain_z()`; all asset Z values; 2 more Cruisers (shared mesh); Cruiser `Mobility='Vehicle'`; 3 entry ActBoxes; Cruiser scripts; player `Visibility Mailbox = 1891`; player Forth state machine |

---

## Verification

```bash
task build          # C++ changes
python3 -m py_compile wflevels/moon_site01/blender_create_moon.py
blender --background --python wflevels/moon_site01/blender_create_moon.py
task build-level -- moon_site01
task run-moon
```

Checks:
- All assets rest on terrain (no floating)
- 3 Cruisers at distinct positions, wheels visibly on the ground
- Walk into entry trigger → `MOON_NEARBY_VEHICLE` nonzero (debug bridge)
- Press interact → player hides, `MOON_ACTIVE_VEHICLE` nonzero
- Joystick → Cruiser moves with wheel-physics response (weight transfer, suspension visible)
- Press interact → player reappears at vehicle position
