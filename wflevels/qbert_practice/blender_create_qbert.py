"""
blender_create_qbert.py — drive Blender to produce qbert_practice.lev.

Run headlessly:
  blender --background --python blender_create_qbert.py

Strategy: import snowgoons-blender.lev (gets all infrastructure objects with
correct OAD schemas attached), strip everything except the reusable
infrastructure, reposition objects for the Q*bert pyramid layout, then
generate 28 cube actors at pyramid positions plus the player at the apex,
plus a second camshot (cs_death) for the fall cutscene. Export to
qbert_practice.lev.

Phase-1 cube consolidation (2026-05-10, docs/plans/2026-05-10-qbert-cube-consolidation.md):
  - 28 cube actors (one per pyramid position), all referencing the same
    cube.iff (3-material mesh: top / lit-side / shadow-side).
  - Per-face material color is mutated at runtime via the new
    EMAILBOX_FACE_COLOR_TOP/LIT/SHADOW slots (mailbox.inc:3037..3039),
    written from the director script via `write-actor-mailbox`.
  - Director maintains the per-cube state (200..227) and a 16-round x
    3-state top-color LUT, plus the per-level lit/shadow side colors;
    on cube-state changes it writes the new top color to that cube; on
    level transitions it writes new side colors to all 28 cubes.
  - Replaces the prior 1344-actor visibility-fan-out (28 positions x 16
    rounds x 3 states) which baked colors into prebaked .iff variants.

MVP scope (per docs/plans/2026-05-03-qbert-mvp.md):
  - 28-cube pyramid in a 7-row triangular layout.
  - Player as an Anchored actor with the hop state machine in its Script.
  - Director script for cube-state advance and win check (colour rule 0).
  - Two CamShots (cs_pyramid and cs_death) wired through INDEXOF_CAMSHOT.
  - No enemies, no discs, no HUD, no audio.
"""

import bpy
import os
import sys
import math

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(SCRIPT_DIR, '..', '..'))
SNOWGOONS_LEV = os.path.join(REPO, 'wflevels', 'snowgoons-blender', 'snowgoons-blender.lev')
OUT_LEV = os.path.join(SCRIPT_DIR, 'qbert_practice.lev')
OAD_DIR = os.path.join(REPO, 'wfsource', 'source', 'oas')
STATPLAT_OAD = os.path.join(REPO, 'wftools', 'wf_oad', 'tests', 'fixtures', 'statplat.oad')
ENEMY_OAD    = os.path.join(REPO, 'wftools', 'wf_oad', 'tests', 'fixtures', 'enemy.oad')

# ── Pyramid geometry ──────────────────────────────────────────────────────────
NUM_ROWS = 7  # rows 0 (apex) through 6 (bottom)
TOTAL_CUBES = NUM_ROWS * (NUM_ROWS + 1) // 2  # 28
CUBE_SIZE = 2.0  # matches gen_cube.py — 2×2×2 cube
CUBE_BASE_Z = 1.0  # bottom row centre Z (cubes extend ±1 around their centre)
# Cubes are rotated 45° about Z (diamond presentation); their footprint
# extends √2 along the new X/Y axes. Multiply XY centre offsets by √2 so
# adjacent diamonds touch corner-to-corner with no overlap.
SQRT2 = math.sqrt(2.0)

# Mailbox layout (qbert_practice).
#   2          END_TIME (engine sentinel — mm convention)
#   13         DEATH (engine signal — mm convention)
#   70..72     HUD score/timer/lives (mm convention; mb 72 LIVES rendered by DrawHud)
#   100..101   camshot zone signals from ActBoxOR (mm convention)
#   200..227   CUBE_STATE_BASE (28 slots, cube N's per-frame state at 200+N — values 0/1/2)
#   228..255   CUBE_PREV_STATE_BASE (28 slots, last-frame value of CUBE_STATE — director
#              compares to detect state changes and re-write that cube's TOP color)
#   256..303   ROUND_TOP_LUT (48 slots, round R state S top RGB at 256 + R*3 + S — populated
#              once at level init from gen_cube.ROUND_TOP_COLORS)
#   400        QBERT_ROW
#   401        QBERT_COL
#   402        HOP_COOLDOWN
#   411        QBERT_LANDED (player→director one-shot)
#   412        CUBES_TO_TARGET (director→HUD count)
#   413        ROUND_CLEAR (director→engine win flag)
#   414        FALL_DEATH (player→director one-shot at end of fall animation)
#   415        cs_death countdown (frames remaining holding cs_death)
#   416        INTRO_PHASE (0..5 active sweep, 6 done)
#   417        INTRO_TIMER (frames into current intro leg)
#   418        INTRO_DONE (1 latch when intro complete; gates joystick + camshot routing)
#   419        FALL_PHASE (0=not falling, 1..30=ramping Z down each tick)
#   420        GAME_OVER (1 latch when lives→0; cleared on player restart)
#   421        LEVEL_INITIALIZED (director one-shot init flag — sets lives=3 once)
#   422        LAST_STICK (player edge-detect snapshot for restart-button trigger)
#   424        ROUND_CLEAR_TIMER (director internal — counts down 90→0 on win, then resets)
#   425        ROUND_NUMBER (0-based; increments on each clear, 0..15)
#   426        ROUND_CHANGED (director-internal one-shot — set when round counter
#              advances; next-tick handler broadcasts the new round's TOP colors
#              to all 28 cubes; cleared after broadcast)
#   427        LAST_LEVEL (director-internal — last level index whose side colors
#              were broadcast; compared to ROUND_NUMBER//4 to detect level changes)
#   430        (reserved; was AUTOPILOT_ON — autopilot now host-driven via inject_input)
#   431        (reserved; was AUTOPILOT_STEP)
#   432        CAPTURE_TRIGGER (Phase E walker — 1=state-0 snap, 2=state-1 snap,
#              3=round-clear, 0 otherwise. Host watches transitions and issues
#              `screenshot` ops over the debug bridge.)
#
# Per-cube color overrides live on each cube actor's local mailboxes:
#   3037 / 3038 / 3039 = EMAILBOX_FACE_COLOR_TOP / LIT / SHADOW (mailbox.inc)
# The director writes them via the `write-actor-mailbox` zForth primitive,
# addressing each cube by its actor index. CUBE_ACTOR_BASE is computed at
# export time and embedded into the director Forth as a constant.
INDEXOF_CUBE_STATE_BASE      = 200
INDEXOF_CUBE_PREV_STATE_BASE = 228   # 228..255
INDEXOF_ROUND_TOP_LUT_BASE   = 256   # 256..303 (16 rounds × 3 states)
INDEXOF_ROUND_NUMBER         = 425
INDEXOF_ROUND_CHANGED        = 426
INDEXOF_LAST_LEVEL           = 427

NUM_MAILBOXES = 500  # well above the highest mailbox we use (~432)


def cube_index(row, col):
    """Triangular packing index — matches the GDD's INDEXOF_CUBE_STATE_BASE + row*(row+1)/2 + col."""
    return row * (row + 1) // 2 + col


def cube_world_position(row, col):
    """Centre of cube (row, col) in world coords. Z-up.

    Iconic Q*bert pyramid stacking: each row sits on the back half of the
    row below, so successive rows offset by (CUBE_SIZE/2) in +Y and
    CUBE_SIZE in +Z. This gives the staircase look where the cube tops
    are all visible from a 3/4 camera angle.
    """
    world_x = SQRT2 * (col - row / 2.0) * CUBE_SIZE
    # Apex row (r=0) is furthest back in +Y; bottom row (r=NUM_ROWS-1) is at Y=0.
    world_y = SQRT2 * (NUM_ROWS - 1 - row) * (CUBE_SIZE / 2.0)
    # Apex highest Z; bottom row at CUBE_BASE_Z.
    world_z = CUBE_BASE_Z + (NUM_ROWS - 1 - row) * CUBE_SIZE
    return (world_x, world_y, world_z)


# ── Player + camera positions ─────────────────────────────────────────────────
# Apex cube is at world (0, 6, 13). Player sits on top of it.
APEX_X, APEX_Y, APEX_Z = 0.0, SQRT2 * (NUM_ROWS - 1) * (CUBE_SIZE / 2.0), CUBE_BASE_Z + (NUM_ROWS - 1) * CUBE_SIZE
PLAYER_SPAWN_XYZ = (APEX_X, APEX_Y, APEX_Z + 1.5)
# Arcade-Q*bert framing: symmetric in X (x=0), 30° iso down-tilt. Look-at is
# the pyramid centroid; camera is south (-Y) and elevated (+Z) so the down-
# vector from camera to look-at is ~30° below horizontal. Matches the
# Gottlieb cabinet's 30° dimetric iso projection — cube tops are clearly
# visible (the diamond-on-top view), front faces show as parallelograms.
# (Earlier (12, -15, 14) was 3-quarters offset + only 17° down — too
# horizontal; pyramid rendered as a thin triangle.)
CAMSHOT_POS = (0.0, -22.0, 23.0)   # ~28 units from look-at — pulled back from
                                   # (0,-15,19) so Q*bert's head isn't clipped
                                   # at the top of the framebuffer.
CAMSHOT_LOOKAT = (0.0, 3.0, 8.5)   # apex+player in frame; offset above pyramid centre
# Iso-angle check: down-angle = atan((23-8.5)/(3-(-22))) = atan(14.5/25) = 30.1°.

# Room bbox is **relative to the room's position** in the exported BOX3.
# Must strictly enclose every actor (no equality on edges, or levcomp drops
# the actor into PERM — see level-design-troubleshooting.md).
#
# Actor extremes that drive the bbox:
#   Pyramid cubes:   X=[-6..+6], Y=[0..6], Z=[0..14]
#   Player at apex:  (0, 6, 14.5)
#   cs_pyramid:      (12, -15, 14)   ← gameplay camera
#   cs_death:        (12, -15, 14)
#   cs_intro_0:      (48, -90, 41)   ← far-back intro start (drives X+/Y-/Z+ extremes)
#   cs_intro_1..4:   between cs_intro_0 and cs_pyramid
#   light:           (0, -5, 16)
#   director/levelobj: (0, -10, 7)
#   matte:           (0, 0, 6)
ROOM_CENTRE = (0.0, 0.0, 7.0)
ROOM_BBOX_REL = (-15.0, -100.0, -45.0, 75.0, 15.0, 45.0)
# Resulting absolute bbox: (-15, -100, -38) to (75, 15, 52).
# Z floor extended to -38 so the 30-tick fall animation completes before the
# actor exits the room. Worst-case fall starts at z=3 (bottom-row cube top)
# and reaches z=-27 at tick 30; floor at -38 gives 11 units of margin.
# Asymmetric in Y because the intro sweep starts deep in -Y; centre stays
# at world origin for editor sanity.

# ── 1. Start with a clean scene ─────────────────────────────────────────────────
bpy.ops.wm.read_factory_settings(use_empty=True)
import addon_utils
addon_utils.enable("wf_blender", default_set=False, persistent=False)
scene = bpy.context.scene

# ── 2. Import the snowgoons reference level ─────────────────────────────────────
print(f"[qbert] Importing {SNOWGOONS_LEV}")
bpy.ops.wf.import_level(filepath=SNOWGOONS_LEV)

# ── 3. Identify what to keep vs delete ─────────────────────────────────────────
KEEP_CLASSES = {'director', 'camera', 'levelobj', 'matte', 'light',
                'room', 'camshot', 'target', 'actboxor', 'player'}
DELETE_CLASSES = {'statplat', 'enemy', 'snowman01', 'missile',
                  'tool', 'tool01', 'ground01', 'hp'}


def get_class(obj):
    schema = obj.get('wf_schema_path', '')
    if schema:
        return os.path.splitext(os.path.basename(schema))[0]
    return ''


# Delete gameplay objects from snowgoons
for obj in list(bpy.data.objects):
    if get_class(obj) in DELETE_CLASSES:
        bpy.data.objects.remove(obj, do_unlink=True)

# Drop duplicates: keep only the first of each infrastructure class
seen = set()
for obj in list(bpy.data.objects):
    cn = get_class(obj)
    if cn in KEEP_CLASSES:
        if cn in seen:
            bpy.data.objects.remove(obj, do_unlink=True)
        else:
            seen.add(cn)

print("[qbert] Classes after strip:", sorted({get_class(o) for o in bpy.data.objects}))


def find_by_class(cn):
    for obj in bpy.data.objects:
        if get_class(obj) == cn:
            return obj
    return None


# ── 4. Reposition infrastructure ───────────────────────────────────────────────
# Director, levelobj, matte, light: doesn't matter much (no rendered geometry,
# but matte renders the background). Place them around the camera.
director = find_by_class('director')
if director:
    director.location = (0, -10, 7)

levelobj = find_by_class('levelobj')
if levelobj:
    levelobj.location = (0, -10, 7)
    levelobj['wf_Number Of Mailboxes'] = NUM_MAILBOXES
    levelobj['wf_Model Type'] = 'None'  # suppress debug-box render

matte = find_by_class('matte')
if matte:
    matte.location = (0, 0, 6)
    matte['wf_Matte Type'] = 'Color'
    matte['wf_Background Color'] = 0x101830  # subtle dark blue — gives shadow-side cubes a contrast against BG (arcade L1R1 is pure black, but our shadow side renders slightly darker than authored due to engine lighting)
    matte['wf_Visibility Mailbox'] = 1  # always visible
    # The matte renders the background via its own backdrop logic. Without this
    # override, Model Type defaults to "Box" and RenderActor3DBox draws the
    # matte as a small random-coloured cube *in front of* the pyramid (the
    # pyramid's apex was getting masked by a pink hex).
    matte['wf_Model Type'] = 'None'

camera = find_by_class('camera')
if camera:
    camera.location = CAMSHOT_POS
    # Fog defaults from the snowgoons template (start=20, end=30, color=0x888888)
    # would fully fog out anything past 30 units. Camera at (20,-25,22) puts the
    # pyramid at distance ~35 → fully replaced by fog colour (gray) and the
    # cubes lose their material colour entirely. Push fog back so the pyramid
    # fits inside the unfogged near range, and dial the colour to the matte
    # background so the transition (if reached) is invisible.
    camera['wf_FoggingStartDistance'] = 100.0
    camera['wf_FoggingCompleteDistance'] = 200.0
    camera['wf_FoggingColor'] = 0x000020  # match matte background
    camera['wf_Model Type'] = 'None'  # suppress debug-box render

light = find_by_class('light')
if light:
    light.location = (0, -5, 16)
    # mm_practice uses (π/2, 0, 0) but that one-direction tilt only lights
    # one of our 45°-rotated cube's two visible side faces; the other renders
    # near-black. Add a 45° Z-rotation so the source vector points midway
    # between the two visible-face normals, giving both sides equal
    # (~0.707) directional contribution → both lit + shadow side colours
    # render at consistent half-brightness instead of one being fully dark.
    light.rotation_euler = (math.pi / 2, 0, math.pi / 4)
    light.name = 'Light01'
    light['wf_lightType'] = 'Directional'
    light['wf_lightRed']   = 1.0
    light['wf_lightGreen'] = 1.0
    light['wf_lightBlue']  = 1.0

def _make_principled_material(name, rgb):
    """Create a Principled-BSDF material with Base Color set to rgb (0..1 tuple)."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
    mat.diffuse_color = (rgb[0], rgb[1], rgb[2], 1.0)  # viewport solid-shade colour
    return mat


def _build_qbert_player_mesh():
    """Build a 3D Q*bert from primitives, return the joined mesh object.

    Silhouette: orange UV-sphere body, smaller orange head, peach conical
    snout pointing **+X** (engine forward), two orange cylinder legs, dark-
    orange flattened feet. All primitives joined into one mesh with per-face
    material assignments. Origin at (0,0,0) = ground level (feet bottom).

    Axis convention: WF actor forward = +X, left = +Y, up = +Z (see
    project_wf_axis_convention memory). The camera at (0,-22,23) looks +Y;
    Q*bert at the apex spawns with rest yaw rotated so engine-+X aligns
    with world-(-Y), i.e. the snout points toward the viewer at rest. We
    do the alignment by setting the actor's authored rotation to +90° yaw
    rather than by rotating the mesh — that way the engine and the script
    both agree that "forward = +X" in actor-local space.
    """
    mat_orange = _make_principled_material('qbert_orange',    (1.00, 0.53, 0.00))
    mat_snout  = _make_principled_material('qbert_snout',     (1.00, 0.67, 0.40))
    mat_feet   = _make_principled_material('qbert_feet',      (0.80, 0.33, 0.00))
    mat_eye    = _make_principled_material('qbert_eye_white', (1.00, 1.00, 1.00))

    parts = []  # (object, material)

    # Low-poly budget: the level memory pool is tight (~28 cubes share the
    # same Level DMalloc), so keep total verts well under ~250.

    # Body — UV sphere (~80 verts)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.55, segments=10, ring_count=6, location=(0, 0, 0.55))
    parts.append((bpy.context.object, mat_orange))

    # Head — smaller UV sphere (~50 verts)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.40, segments=8, ring_count=5, location=(0, 0, 1.25))
    parts.append((bpy.context.object, mat_orange))

    # Mesh-local "forward" = +X (engine convention). Snout, eyes, feet point +X.
    # Left-right is the Y axis. The actor's authored rest rotation handles the
    # +X-forward → toward-camera alignment in world space (see player setup
    # below where we set rotation_euler.z so the snout faces the camera).

    # Snout — cone pointing +X (default cone points +Z; rotate +90° about Y) (~9 verts)
    bpy.ops.mesh.primitive_cone_add(
        vertices=8, radius1=0.18, radius2=0.10, depth=0.45,
        location=(0.40, 0, 1.20), rotation=(0, math.pi / 2, 0)
    )
    parts.append((bpy.context.object, mat_snout))

    # Legs — two cylinders, straddling the Y axis (~12 verts each)
    for y in (-0.22, 0.22):
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=6, radius=0.13, depth=0.30, location=(0, y, 0.15)
        )
        parts.append((bpy.context.object, mat_orange))

    # Feet — flattened spheres in front of legs (+X is "front") (~24 verts each)
    for y in (-0.22, 0.22):
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=0.20, segments=6, ring_count=4, location=(0.05, y, 0.04)
        )
        bpy.context.object.scale = (1.2, 1.0, 0.4)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        parts.append((bpy.context.object, mat_feet))

    # Eyes — two small white spheres on the front (+X) of the head (~12 verts each)
    for y in (-0.14, 0.14):
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=0.07, segments=6, ring_count=4, location=(0.30, y, 1.40)
        )
        parts.append((bpy.context.object, mat_eye))

    # Smooth-shade everything, assign each part's single material to all its faces.
    for obj, mat in parts:
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        for poly in obj.data.polygons:
            poly.material_index = 0
            poly.use_smooth = True

    # Join into one mesh with the body as the active/target object.
    bpy.ops.object.select_all(action='DESELECT')
    for obj, _ in parts:
        obj.select_set(True)
    body = parts[0][0]
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    body.name = 'QbertPlayerMesh'
    body.data.name = 'QbertPlayerMesh'
    return body


# Player — Anchored, Q*bert hop state machine in Script
player = find_by_class('player')
if player:
    player.location = PLAYER_SPAWN_XYZ
    # Authored rest yaw: rotate -90° about Z so engine-local +X (mesh "front",
    # i.e. snout/eyes/feet) aligns with world -Y, which is "toward the camera"
    # at (0, -22, 23). Engine and script both treat +X as forward; this
    # rotation only affects the visual placement at rest.
    player.rotation_euler = (0.0, 0.0, -math.pi / 2)
    player['wf_Mobility'] = 'Anchored'
    player['wf_Mass'] = 0.0
    player['wf_Mesh Name'] = 'player.iff'
    player['wf_Model Type'] = 'Mesh'
    player['wf_Visibility Mailbox'] = 1  # always visible

    # Replace the imported snowgoons placeholder mesh with a real 3D Q*bert
    # built from primitives. The export pipeline (wf_blender/export_level.py
    # _write_mesh_iff) reads materials + per-face material_index off the mesh
    # data and writes a multi-material player.iff — no manual binary IFF
    # writing required.
    qbert_mesh_obj = _build_qbert_player_mesh()
    old_mesh = player.data
    player.data = qbert_mesh_obj.data
    bpy.data.objects.remove(qbert_mesh_obj, do_unlink=True)
    if old_mesh and old_mesh.users == 0:
        bpy.data.meshes.remove(old_mesh)
    # MVP hop state machine: one-tick teleport per stick edge, with cooldown
    # to prevent rapid-fire hops. Mailbox slots (per the original plan):
    #   400 ROW, 401 COL, 402 COOLDOWN, 411 LANDED, 414 FALL_DEATH
    # Cube positions are computed inline from (row, col):
    #   X = 2*col - row,  Y = 6 - row,  Z = 1 + (6-row)*2 + 2 (player offset)
    # Cardinal joystick → diagonal hop mapping (cabinet was rotated 45°):
    #   UP    (0x0800) → up-right  (dr=-1, dc= 0)
    #   RIGHT (0x2000) → down-right (dr= 1, dc= 1)
    #   DOWN  (0x1000) → down-left  (dr= 1, dc= 0)
    #   LEFT  (0x4000) → up-left    (dr=-1, dc=-1)
    # See DIRECTOR_SCRIPT below for the Forth gotchas (real \n only, no \
    # comments after the first sigil line, ASCII-only inside script body).
    # Per-tick body order (top→bottom) — each layer EXITs to gate the rest:
    #   1. game-over restart trigger (mb 420 == 1): edge-detect joystick press
    #      against last-tick snapshot in mb 422; on transition reset all level
    #      state and re-arm the intro state machine. Always EXIT — no other
    #      input is processed during game-over.
    #   2. fall-animation state machine (mb 419 > 0): ramps INDEXOF_Z_POS
    #      down 1 unit per tick for 30 ticks, then snaps player back to apex
    #      and latches mb 414 (FALL_DEATH) for the director to pick up.
    #      EXIT during fall so joystick is frozen.
    #   3. cooldown + INTRO_DONE-gated joystick processing (cardinal → diagonal
    #      hop mapping per cabinet 45° rotation):
    #        UP    (0x0800) → up-right  (dr=-1, dc= 0)
    #        RIGHT (0x2000) → down-right (dr= 1, dc= 1)
    #        DOWN  (0x1000) → down-left  (dr= 1, dc= 0)
    #        LEFT  (0x4000) → up-left    (dr=-1, dc=-1)
    #   4. cooldown decrement (always).
    #   5. Z<-2 safety net (gated on FALL_PHASE==0 so it doesn't fire mid-fall).
    #
    # do-hop: replaces the original "set Z=-10 on off-edge" instant-teleport
    # with a predictive fall trigger — when the destination is off-pyramid,
    # clamp the row used for the X/Y/Z computation to [0..6] (so Q*bert appears
    # at a sensible Z, the level of the cube he hopped from), then set
    # FALL_PHASE=1 to let the per-tick state machine ramp Z down each tick.
    #
    # See feedback_zforth_script_gotchas.md: real \n only, no `\` comments
    # after sigil line, ASCII-only, `( ... )` for inline comments.
    player['wf_Script'] = (
        "\\ wf qbert player\n"
        ": stick INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox ;\n"
        ": cd 402 read-mailbox ;\n"
        ": tick-cd cd dup 0 > if 1 - 402 write-mailbox else drop then ;\n"
        # do-hop: on stack ( dr dc ). Before consuming dr/dc to update position,
        # compute the target yaw in revolutions (CCW from engine-+X-forward)
        # for the hop direction and store it in mb 433. The new tick block
        # below reads mb 433 + the actor's current ROTATION_C (mb 3014) each
        # cooldown frame and writes the shortest-path remaining-delta /
        # frames-left into DELTA_YAW (mb 3034) — so the lerp self-corrects
        # and lands exactly on the target as the cooldown hits zero.
        # Direction → target yaw (engine convention +X=forward, +Y=left):
        #   UP    (-1, 0) NE = +X+Y → +0.125 rev
        #   DOWN  ( 1, 0) SW = -X-Y → +0.625 rev
        #   RIGHT ( 1, 1) SE = +X-Y → +0.875 rev
        #   LEFT  (-1,-1) NW = -X+Y → +0.375 rev
        # Hop-arc motion (Phase 1.5): instead of teleporting INDEXOF_X/Y/Z_POS
        # to the destination on frame 0, save the current position to mb 435/
        # 436/437 (HOP_START_*), save target Z to mb 438 (HOP_END_Z; X and Y
        # are recomputed each frame from mb 400/401), and bump HOP_COOLDOWN to
        # 13 so the per-frame lerp block (added below) gets exactly 12 ticks
        # at t = (13-cd)/12 ∈ [1/12, 12/12], landing exactly on target.
        # Note: mb 440+ is the global cube vis-slot range (see clear-all-vis
        # loop in the restart block), so we can't use mb 440 here; HOP_END_X/Y
        # are recomputed from row/col rather than stored.
        ": do-hop "
        "over over "
        "dup 0 = if drop 0 < if 0.125 else 0.625 then else swap drop 0 > if 0.875 else 0.375 then then "
        "433 write-mailbox "
        "INDEXOF_X_POS read-mailbox 435 write-mailbox "
        "INDEXOF_Y_POS read-mailbox 436 write-mailbox "
        "INDEXOF_Z_POS read-mailbox 437 write-mailbox "
        "401 read-mailbox + swap 400 read-mailbox + "
        "dup 400 write-mailbox over 401 write-mailbox "
        "6 swap - 2 * 1 + 2 + 438 write-mailbox "        # HOP_END_Z (lerped to)
        "drop 13 402 write-mailbox "
        "400 read-mailbox dup 0 < swap 6 > | "
        "401 read-mailbox 0 < | "
        "401 read-mailbox 400 read-mailbox > | "
        "if "
        # Off-edge: re-clamp row for safe-Z computation, then trigger fall.
        # Crucially do NOT set QBERT_LANDED (mb 411): the director's landing
        # handler indexes CUBE_STATE by (row,col); off-pyramid coords would
        # compute into prev-state / wrong-cube slots and flip an unrelated cube.
        "400 read-mailbox dup 0 < if drop 0 then dup 6 > if drop 6 then "
        "6 swap - 2 * 1 + 2 + 438 write-mailbox "        # clamped safe-Z → HOP_END_Z (lerp animates toward it before FALL_PHASE takes over)
        "1 419 write-mailbox "
        "else 1 434 write-mailbox then ;\n"      # PENDING_LAND set on-pyramid only; lerp promotes to mb 411 (LANDED) on landing
        # 1. Game-over restart trigger. Snapshot prev-stick before updating
        # mb 422 so edge-detect can compare; then update mb 422 = current.
        "422 read-mailbox stick 422 write-mailbox\n"
        "420 read-mailbox 1 = if "
        "0 = if "  # consumes prev_stick: prev was zero?
        "stick 0 <> if "
        # Restart: reset every per-game mailbox + snap player to apex.
        # CRITICAL: also reset ROUND_NUMBER=0 so play resumes at L1R1, not
        # at whatever round the previous game-over happened on. Re-init the
        # visibility fan-out by zeroing all 336 vis slots and showing the
        # L1R1 (palette 0) state-0 row.
        "3 72 write-mailbox "
        "0 411 write-mailbox 0 412 write-mailbox 0 413 write-mailbox "
        "0 414 write-mailbox 0 415 write-mailbox "
        "0 416 write-mailbox 0 417 write-mailbox 0 418 write-mailbox "
        "0 419 write-mailbox 0 420 write-mailbox "
        "0 400 write-mailbox 0 401 write-mailbox 0 402 write-mailbox "
        "-0.25 3014 write-mailbox -0.25 433 write-mailbox "  # snap yaw back to rest pose (-90°)
        "0 425 write-mailbox "                    # ROUND_NUMBER → 0 (restart at L1R1)
        "0 426 write-mailbox "                    # round-clear-pending flag
        "0 424 write-mailbox "                    # round-clear timer
        "0 431 write-mailbox "
        "28 0 do 0 200 i + write-mailbox loop "
        # Re-arm CUBE_PREV_STATE_BASE to sentinel 99 so the director's
        # state-change detector fires a re-color for every cube on the next
        # tick — mirrors the LEVEL_INIT path. Without this, cubes visited in
        # the previous game retain their state-2 (cleared / blue) TOP colour
        # because cur=0 vs prev=0 wouldn't differ either, and we can't trust
        # the lingering prev=2 from cleared cubes to always trigger.
        "28 0 do 99 228 i + write-mailbox loop "
        "336 0 do 0 440 i + write-mailbox loop "  # clear all vis slots
        "28 0 do 1 440 i 3 * + write-mailbox loop "  # show L1R1 state-0 row (pal=0)
        "0 INDEXOF_X_POS write-mailbox "
        "6 1.4142136 * INDEXOF_Y_POS write-mailbox "
        "15 INDEXOF_Z_POS write-mailbox "
        "then "
        "then "
        "exit "
        "else drop "
        "then\n"
        # 1.5. Round-clear apex respawn. Director sets mb[426]=1 when round
        # timer expires; we handle it here (player context) so INDEXOF_X/Y/Z
        # writes go to the player actor's position, not the director's.
        # exit prevents joystick processing on the same tick as the teleport.
        "426 read-mailbox 1 = if "
        "0 INDEXOF_X_POS write-mailbox 6 1.4142136 * INDEXOF_Y_POS write-mailbox 15 INDEXOF_Z_POS write-mailbox "
        "0 402 write-mailbox -0.25 3014 write-mailbox -0.25 433 write-mailbox "
        "0 431 write-mailbox 0 426 write-mailbox exit "
        "then\n"
        # 2. Fall-animation state machine. While mb 419 > 0:
        #    1..29 → ramp Z down 1 per tick, increment FALL_PHASE.
        #    >=30  → snap player to apex, latch FALL_DEATH=1, reset FALL_PHASE.
        "419 read-mailbox dup 0 > if "
        "dup 30 < if "
        "INDEXOF_Z_POS read-mailbox 1 - INDEXOF_Z_POS write-mailbox "
        "1 + 419 write-mailbox "
        "else "
        "drop "
        "0 419 write-mailbox 1 414 write-mailbox "
        "0 INDEXOF_X_POS write-mailbox "
        "6 1.4142136 * INDEXOF_Y_POS write-mailbox "
        "15 INDEXOF_Z_POS write-mailbox "
        "0 400 write-mailbox 0 401 write-mailbox "
        "0 402 write-mailbox -0.25 3014 write-mailbox -0.25 433 write-mailbox "
        "then "
        "exit "
        "else drop "
        "then\n"
        # 3. Joystick → diagonal hop. Cardinal joystick bits map to qbert
        # diagonals because the original arcade cabinet was rotated 45°.
        # Gated on cooldown==0 and INTRO_DONE so the player can't queue hops.
        # Host-side automation (walker / record harness) drives this via
        # the debug bridge inject_input op on HARDWARE_JOYSTICK1_RAW.
        "cd 0 = if "
        "418 read-mailbox 1 = if "
        "stick 0x0800 & if -1 0 do-hop exit then "
        "stick 0x2000 & if 1 1 do-hop exit then "
        "stick 0x1000 & if 1 0 do-hop exit then "
        "stick 0x4000 & if -1 -1 do-hop exit then "
        "then "
        "then\n"
        # 3.5. Smooth yaw across remaining HOP_COOLDOWN frames.
        # Reads current ROTATION_C (mb 3014) and target (mb 433) each frame,
        # computes shortest-path remaining delta in (-0.5, 0.5] revolutions,
        # and writes (delta / frames-left) to DELTA_YAW (mb 3034). Self-
        # corrects each frame so it lands exactly on target as cd hits zero.
        # 180° special case: shortest-path sign is ambiguous (just the lexical
        # sign of target-current). The camera at (0,-22,23) looks +Y, so
        # face-visible = midpoint forward.Y < 0 = midpoint yaw mod 1 in
        # (0.5, 1.0). When |delta|^2 > 0.249 (≈ |delta| > 0.499; squared
        # because `abs` isn't in the zForth bootstrap, see scripting_zforth.cc
        # kCoreBootstrap), pick the sweep whose CCW midpoint (current + 0.25)
        # lands in the face hemisphere, else use CW.
        "402 read-mailbox 0 > if "
        "433 read-mailbox 3014 read-mailbox - "
        "dup 0.5 > if 1.0 - then "
        "dup -0.5 < if 1.0 + then "
        "dup dup * 0.249 > if "
        "drop 3014 read-mailbox 0.25 + "
        "dup 1.0 >= if 1.0 - then "
        "dup 0.0 < if 1.0 + then "
        "0.5 > if 0.5 else -0.5 then "
        "then "
        "402 read-mailbox / 3034 write-mailbox "
        "then\n"
        # 3.7. Hop-arc position interpolation across HOP_COOLDOWN frames.
        # Smoothstepped XY lerp + parabolic Z arc with peak +2 at mid-hop.
        # t_raw = (13 - cd) / 12 ∈ [1/12, 12/12]; smoothed via t*t*(3-2t)
        # for ease-in-out (lifts off slowly, decelerates onto landing).
        # cd=1 ⇒ t_raw=1 ⇒ smoothstep(1)=1 ⇒ exact landing on target.
        # Target X/Y are recomputed each frame from mb 400/401 (row/col were
        # already updated in do-hop); target Z lives in mb 438 (clamped on
        # off-edge hops by the do-hop fall path).
        "402 read-mailbox 0 > if "
        "13 402 read-mailbox - 12.0 / "                        # t_raw
        "dup dup * swap 2.0 * 3.0 swap - * "                    # t = smoothstep(t_raw)
        # X lerp: pos_x = start_x + t * ((2*col - row)*sqrt(2) - start_x)
        "dup 401 read-mailbox 2 * 400 read-mailbox - 1.4142136 * "
        "435 read-mailbox - * 435 read-mailbox + INDEXOF_X_POS write-mailbox "
        # Y lerp: pos_y = start_y + t * ((6 - row)*sqrt(2) - start_y)
        "dup 6 400 read-mailbox - 1.4142136 * "
        "436 read-mailbox - * 436 read-mailbox + INDEXOF_Y_POS write-mailbox "
        # Z lerp + arc bonus = lerp(start_z, end_z, t) + 4*t*(1-t)*2.0
        "dup 438 read-mailbox 437 read-mailbox - * 437 read-mailbox + "  # ( t lerp_z_base )
        "over dup 1.0 swap - * 4.0 * 2.0 * + "                  # ( t final_z ) — keeps t on stack
        "INDEXOF_Z_POS write-mailbox "                           # ( t )
        # Trigger LANDED 1 frame before exact landing (cd=2) for anticipation
        # feel — cube colour flips just before Q*bert visually touches down.
        # Off-edge hops left mb 434 = 0 (default), so this writes 0 to mb 411
        # = no LANDED trigger (director's `0 <>` gate skips); on-pyramid hops
        # set mb 434 = 1 in do-hop's else branch, which lands here as `1`.
        # Stack-neutral: pushes/pops cancel out, leaves ( t ) for the scale
        # block below.
        "402 read-mailbox 2 = if 434 read-mailbox 411 write-mailbox 0 434 write-mailbox then "
        # Phase 2 stretch-and-squash: classic anticipation → air-stretch →
        # impact-squash → recover-to-natural sequence over the 12-frame hop.
        #   bell = 4*t*(1-t)   ∈ [0, 1], peaks at t=0.5 (mid-air)
        #   imp  = (2t-1)²    ∈ [0, 1], peaks at t=0 and t=1 (takeoff + landing)
        # On the final landing frame (cd=1, t=1) we snap to identity so
        # Q*bert is at natural shape post-hop. The remaining 11 frames run:
        #   z_scale  = 1 + 0.20*bell − 0.40*imp  (taller mid-air, shorter at endpoints)
        #   xy_scale = 1 − 0.10*bell + 0.40*imp  (narrower mid-air, wider at endpoints)
        # Visible sequence: wide+short crouch on takeoff → tall+narrow at apex →
        # wide+short impact on near-landing → snap to (1,1,1) on landing.
        # Mailboxes 3040/3041/3042 = X/Y/Z_SCALE (wired through actor → RenderActor3D).
        "402 read-mailbox 1 = if "
        "drop "                                                  # discard t — landing frame
        "1.0 3040 write-mailbox 1.0 3041 write-mailbox 1.0 3042 write-mailbox "
        "else "
        # Compute imp = (2t-1)² and bell = 4*t*(1-t) from t.
        "dup 2.0 * 1.0 - dup * "                                 # ( t imp )
        "swap dup 1.0 swap - 4.0 * * "                           # ( imp bell )
        # Z_SCALE = 1 + 0.20*bell − 0.40*imp.
        "over 0.40 * over 0.20 * swap - 1.0 + 3042 write-mailbox "
        # ( imp bell ) still on stack — compute XY_SCALE = 1 + 0.40*imp − 0.10*bell.
        "0.10 * swap 0.40 * swap - 1.0 + "                       # ( xy_scale )
        "dup 3040 write-mailbox 3041 write-mailbox "
        "then "
        "then\n"
        # 4. Cooldown decrement.
        "tick-cd\n"
        # 5. Safety-net Z<-2 — gated on FALL_PHASE==0 so the fall state
        # machine isn't pre-empted while ramping Z down past -2.
        "INDEXOF_Z_POS read-mailbox -2 < if "
        "419 read-mailbox 0 = if "
        "0 INDEXOF_X_POS write-mailbox 6 1.4142136 * INDEXOF_Y_POS write-mailbox "
        "15 INDEXOF_Z_POS write-mailbox "
        "0 400 write-mailbox 0 401 write-mailbox 1 414 write-mailbox "
        "then "
        "then\n"
    )

# Room — bbox is stored relative to the room's position (verified against
# mm_practice_blender.lev: wf_original_bbox value is exported to BOX3 as-is).
room = find_by_class('room')
if room:
    room.location = ROOM_CENTRE
    bx0, by0, bz0, bx1, by1, bz1 = ROOM_BBOX_REL
    # Visualisation mesh — position-relative since Blender meshes are local-space.
    box_verts = [
        (bx0, by0, bz0), (bx1, by0, bz0), (bx1, by1, bz0), (bx0, by1, bz0),
        (bx0, by0, bz1), (bx1, by0, bz1), (bx1, by1, bz1), (bx0, by1, bz1),
    ]
    box_faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
                 (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    room['wf_original_bbox'] = ROOM_BBOX_REL
    new_mesh = bpy.data.meshes.new("RoomBounds")
    new_mesh.from_pydata(box_verts, [], box_faces)
    new_mesh.update()
    old_mesh = room.data
    room.data = new_mesh
    if old_mesh and old_mesh.users == 0:
        bpy.data.meshes.remove(old_mesh)

# Actboxor — covers the playable volume and writes cs_pyramid index to mailbox 100
actboxor = find_by_class('actboxor')
if actboxor:
    actboxor.location = ROOM_CENTRE
    # The snowgoons template's actboxor.Object referenced "CamShot01" by name.
    # We renamed CamShot01 → cs_pyramid above, so update the reference too.
    actboxor['wf_Object'] = 'cs_pyramid'

# CamShot 1 — cs_pyramid, the gameplay shot, all axes Absolute
camshot = find_by_class('camshot')
if camshot:
    camshot.location = CAMSHOT_POS
    camshot.name = 'cs_pyramid'
    # All three axes Absolute, rotation Fixed (look-at via Target)
    camshot['wf_Position X'] = 'Absolute'
    camshot['wf_Position Y'] = 'Absolute'
    camshot['wf_Position Z'] = 'Absolute'
    camshot['wf_Rotation'] = 'Fixed'
    camshot['wf_FOV'] = 60.0
    # Pan time = 1.2 s so the FINAL leg of the intro sweep (cs_intro_4 → cs_pyramid)
    # decelerates smoothly into the gameplay shot. Also affects the post-cs_death
    # return — death cycle now ends with a 1.2 s pan back to gameplay (was instant).
    camshot['wf_Pan Time In Seconds'] = 1.2
    camshot['wf_Model Type'] = 'None'  # suppress debug-box render
    # BungeeCam folds TrackObject's world position into the look-at vector.
    # The snowgoons template ships with Track Object='Player', which makes the
    # camera follow the player around — undesired for Q*bert's fixed pyramid
    # framing. Point Track Object at Target02 (pyramid centre) so the look-at
    # stays on the pyramid regardless of where the player has hopped.
    camshot['wf_Track Object'] = 'Target02'
    camshot['wf_Follow'] = 'Target02'  # equal Follow → Position math degenerates
                                        # to absolute camshot position

# Targets — use existing Target01/02 from snowgoons
# Target01 = world-origin anchor for the BungeeCam Follow vector.
# Target02 = look-at point for the CamShot's Target field. Place it at
# the pyramid centre so the camera frames the whole pyramid, not above it.
# Also force Model Type = None so the targets don't render as random-coloured
# debug boxes (RenderActor3DBox uses MakeRandMaterialList).
targets = [o for o in bpy.data.objects if get_class(o) == 'target']
if len(targets) >= 1:
    targets[0].location = (0.0, 0.0, 0.0)
    targets[0].name = 'Target01'
    targets[0]['wf_Model Type'] = 'None'
if len(targets) == 1:
    t1 = targets[0]
    t2 = t1.copy()
    t2.data = t1.data.copy() if t1.data else None
    scene.collection.objects.link(t2)
    targets.append(t2)
if len(targets) >= 2:
    targets[1].location = CAMSHOT_LOOKAT
    targets[1].name = 'Target02'
    targets[1]['wf_Model Type'] = 'None'

# ── 5. Add a second CamShot (cs_death) — follows player on fall ───────────────
# Duplicate cs_pyramid and reconfigure
if camshot:
    cs_death = camshot.copy()
    cs_death.data = camshot.data.copy() if camshot.data else None
    scene.collection.objects.link(cs_death)
    cs_death.name = 'cs_death'
    cs_death.location = CAMSHOT_POS  # same world position
    cs_death['wf_FOV'] = 22.0  # tighter framing
    cs_death['wf_Pan Time In Seconds'] = 0.2  # smooth pan when switching to it
    # Track the player so the death cutscene follows the falling body.
    # Equal Track Object and Follow keeps Position math degenerate (camera
    # stays at CAMSHOT_POS); only the look-at vector swings to follow the
    # player. With the fall state machine landing FALL_DEATH=1 AT END of the
    # 30-frame fall, the player is back at apex by the time cs_death takes
    # over — so this configuration also frames the apex post-fall, but is
    # forward-compatible with future flows that want cs_death active during
    # the fall (just trigger FALL_DEATH=1 in do-hop instead of at end).
    cs_death['wf_Track Object'] = 'Player'
    cs_death['wf_Follow'] = 'Player'

# ── 5b. Intro cinematic CamShots — chained sweep-in to cs_pyramid ─────────────
# Five CamShots placed along an arc from "very far back" to the existing
# cs_pyramid view. The director's Forth state machine writes their indices
# to INDEXOF_CAMSHOT in sequence; each pan is linear (PanCameraHandler) but
# the chain approximates a curve and the per-leg Pan times shape an ease-
# in-out speed profile (slow → fast → slow). Total intro length ~3.7 s.
#
# Engine fact (docs/investigations/2026-04-29-camera-system.md): the
# PanCameraHandler does linear lerp between source and dest CamShot
# positions over destShot.PanTimeInSeconds. There is no built-in spline or
# ease curve. See docs/investigations/2026-05-04-camera-path-support-revival.md
# for what would be needed to drive the camera from a Blender curve directly.
INTRO_CAMSHOTS = [
    # (name, world position, Pan time on transition INTO this shot)
    # Positions chosen so the sweep curves toward the new (0, -15, 19) gameplay
    # cam at a 30° iso angle; first leg is "5x distance, more elevated"; final
    # leg lands face-on (centred in X) to match arcade Q*bert framing.
    ('cs_intro_0', (48.0, -90.0, 41.0), 0.0),  # initial cut — far back + high
    ('cs_intro_1', (34.0, -68.0, 35.0), 1.2),  # ease-in: slow start
    ('cs_intro_2', (20.0, -47.0, 29.0), 0.5),  # accelerating
    ('cs_intro_3', (10.0, -32.0, 24.0), 0.3),  # fastest leg
    ('cs_intro_4', ( 3.0, -22.0, 21.0), 0.5),  # decelerating into cs_pyramid
]
intro_camshot_objs = []
if camshot:
    for name, pos, pan_time in INTRO_CAMSHOTS:
        cs_intro = camshot.copy()
        cs_intro.data = camshot.data.copy() if camshot.data else None
        scene.collection.objects.link(cs_intro)
        cs_intro.name = name
        cs_intro.location = pos
        cs_intro['wf_FOV'] = 60.0
        cs_intro['wf_Pan Time In Seconds'] = pan_time
        intro_camshot_objs.append(cs_intro)

# ── 5c. Red Ball enemies (Phase B) ───────────────────────────────────────────
# N = 3 red balls bouncing down the pyramid. The director enables (wakes) one
# idle ball at a time on a per-round spawn cadence; each ball owns its own
# movement script — randomised left/right per hop, parabolic Z arc mid-hop,
# off-pyramid retire. Director-side globals (mb 511..517) carry the LFSR,
# spawn timer, and per-ball "active" mirror so the director can re-decide
# which ball to wake next without needing to read peer mailboxes.
#
# Architecture: each ball is a separate enemy actor (redball_0/1/2) created
# at level build, linked at park-Z (off-screen) so it's invisible until the
# director writes its initial state via write-actor-mailbox.
#
# See docs/plans/2026-05-11-qbert-red-ball-phase-b.md.

REDBALL_COUNT        = 3
REDBALL_HOP_TICKS    = 18      # ~0.3 s/hop at 60 Hz; arcade is ~3 hops/s
REDBALL_HEIGHT_OFFSET = CUBE_SIZE / 2 + 0.5   # ball centre above cube centre

# Park position when idle (in PHASE 0) — stays within the room bbox
# (min Z = -38) so the engine doesn't spam "fell out of room" warnings.
REDBALL_PARK_Z = -30.0

# Forth-side constants matching cube_world_position():
#   X = SQRT2 * CUBE_SIZE * (col - row/2)         = 2.82843 * (col - row*0.5)
#   Y = SQRT2 * (CUBE_SIZE/2) * (NUM_ROWS - 1 - row) = 1.41421 * (6 - row)
#   Z = CUBE_BASE_Z + CUBE_SIZE * (NUM_ROWS - 1 - row) + REDBALL_HEIGHT_OFFSET
#     = 14.5 - 2 * row                                          (NUM_ROWS=7, CUBE_BASE_Z=1, CUBE_SIZE=2)
_RB_X_MUL  = SQRT2 * CUBE_SIZE                       # 2.82843
_RB_Y_MUL  = SQRT2 * (CUBE_SIZE / 2)                 # 1.41421
_RB_Z_BASE = CUBE_BASE_Z + CUBE_SIZE * (NUM_ROWS - 1) + REDBALL_HEIGHT_OFFSET  # 14.5
_RB_Z_MUL  = CUBE_SIZE                               # 2.0
# Z values at the ball's initial spawn row (apex Z=14.5; row-1 Z=12.5).
_RB_Z_AT_ROW_0 = _RB_Z_BASE - 0 * _RB_Z_MUL                # 14.5 (used as initial START_Z)
_RB_Z_AT_ROW_1 = _RB_Z_BASE - 1 * _RB_Z_MUL                # 12.5 (used as initial END_Z)

# Per-ball mailbox layout: base = 462 + 8*K. Each ball owns 8 cells.
_RB_OFF_ROW       = 0
_RB_OFF_COL       = 1
_RB_OFF_COOLDOWN  = 2
_RB_OFF_PHASE     = 3
_RB_OFF_START_Z   = 4
_RB_OFF_END_Z     = 5
_RB_OFF_FROM_ROW  = 6
_RB_OFF_FROM_COL  = 7
_RB_PER_BALL      = 8

def _rb_mb(k, off):
    return 462 + _RB_PER_BALL * k + off

# Director-owned globals (shared across all balls).
RB_MB_LFSR          = 511
RB_MB_SPAWN_TIMER   = 512
RB_MB_ACTIVE_BASE   = 514      # RB_ACTIVE[K] = mb 514+K (K ∈ {0,1,2})
RB_MB_SPAWN_CLAIMED = 517

# LFSR step — Galois LFSR-16, polynomial x^16+x^14+x^13+x^11+1 (tap mask 0xB400).
# Side-effect: advance mb 511; result: lsb (0 or 1) left on stack.
# zForth has `&`, `|`, `^`, `<<`, `>>` (PRIM_AND/OR/XOR/SHL/SHR in zforth.c).
_RB_LFSR_STEP = (
    f"{RB_MB_LFSR} read-mailbox "
    f"dup 1 & 0 <> if "
    f"1 >> 0xB400 ^ "
    f"else "
    f"1 >> "
    f"then "
    f"dup {RB_MB_LFSR} write-mailbox "
    f"1 & "
)

def redball_script(k):
    """Generate the wf_Script for redball K (0..REDBALL_COUNT-1).

    Phase 0: idle (off-screen). Director will wake by writing initial state.
    Phase 1: hopping. Each tick decrements cooldown and writes interpolated XYZ.
             On landing tick (cooldown <= 0): contact-check vs player; if
             off-pyramid, retire to PHASE 0; otherwise pick next direction
             via shared LFSR and re-arm cooldown.
    """
    mb_row      = _rb_mb(k, _RB_OFF_ROW)
    mb_col      = _rb_mb(k, _RB_OFF_COL)
    mb_cd       = _rb_mb(k, _RB_OFF_COOLDOWN)
    mb_phase    = _rb_mb(k, _RB_OFF_PHASE)
    mb_start_z  = _rb_mb(k, _RB_OFF_START_Z)
    mb_end_z    = _rb_mb(k, _RB_OFF_END_Z)
    mb_from_row = _rb_mb(k, _RB_OFF_FROM_ROW)
    mb_from_col = _rb_mb(k, _RB_OFF_FROM_COL)
    mb_active   = RB_MB_ACTIVE_BASE + k

    # t_raw = (HOP_TICKS - cd) / (HOP_TICKS - 1)  — float, in [1/17 .. 1]
    # t'    = smoothstep(t_raw) = t_raw² · (3 − 2·t_raw)
    # (Forth idiom matches player's hop arc at blender_create_qbert.py:596.)
    #
    # Position interpolation: cube-space lerp on (row, col), then convert to
    # world XY via the same X/Y formula used in cube_world_position().
    #   row_now = from_row + t' * (row - from_row)
    #   col_now = from_col + t' * (col - from_col)
    #   x = X_MUL * (col_now - row_now * 0.5)
    #   y = Y_MUL * (6 - row_now)
    #   z_linear = start_z + t' * (end_z - start_z)
    #   z_arc    = z_linear + 4*t_raw*(1-t_raw) * 2.0   (peak +2 at t=0.5)
    hop_denom_f = float(REDBALL_HOP_TICKS - 1)

    # Per-tick algorithm:
    #   1. Phase 0 (idle): early exit; director will wake.
    #   2. Phase 1: decrement COOLDOWN; compute t_raw ∈ [1/17..1] and smoothstep t'.
    #   3. Lerp row_now/col_now in cube-space using t'; convert to world XY; write.
    #   4. Z = lerp(start_z, end_z, t') + 8 * t_raw * (1 - t_raw) parabolic bonus.
    #   5. Contact check vs player (every frame).
    #   6. On landing tick: retire if off-pyramid; else pick next direction via LFSR,
    #      advance row/col, refresh START_Z/END_Z, re-arm COOLDOWN.
    #
    # Stack notation: ( ... -- ... ) tracks values across each line.
    return (
        f"\\\\ wf redball {k}\n"
        # ── Phase 0: idle (off-screen). Director writes our initial state to wake us.
        f"{mb_phase} read-mailbox 0 = if exit then\n"
        # ── Phase 1: hopping. Decrement COOLDOWN.
        f"{mb_cd} read-mailbox 1 - dup {mb_cd} write-mailbox\n"
        # t_raw = (HOP_TICKS - cd_new) / (HOP_TICKS - 1)             ( cd_new -- t_raw )
        f"{REDBALL_HOP_TICKS} swap - {hop_denom_f} /\n"
        # Smoothstep, preserving t_raw under t':                     ( t_raw -- t_raw t' )
        # Top-of-stack smoothstep idiom mirrors player at line ~596.
        f"dup dup dup * swap 2.0 * 3.0 swap - *\n"
        # row_now = from_row + t' * (row - from_row)                 ( t_raw t' -- t_raw t' row_now )
        f"dup {mb_row} read-mailbox {mb_from_row} read-mailbox - * "
        f"{mb_from_row} read-mailbox +\n"
        # col_now = from_col + t' * (col - from_col)                 ( t_raw t' row_now -- t_raw t' row_now col_now )
        f"over {mb_col} read-mailbox {mb_from_col} read-mailbox - * "
        f"{mb_from_col} read-mailbox +\n"
        # y = (6 - row_now) * Y_MUL → write 3010, stack unchanged
        # `over` copies row_now to top; `6.0 swap -` computes (6 - row_now).
        f"over 6.0 swap - {_RB_Y_MUL} * 3010 write-mailbox\n"
        # x = (col_now - row_now*0.5) * X_MUL → write 3009           ( ... row_now col_now -- ... t_raw t' )
        f"swap 0.5 * - {_RB_X_MUL} * 3009 write-mailbox\n"
        # z_linear = start_z + t' * (end_z - start_z)                ( t_raw t' -- t_raw z_linear )
        f"{mb_end_z} read-mailbox {mb_start_z} read-mailbox - * "
        f"{mb_start_z} read-mailbox +\n"
        # arc bonus = 8 * t_raw * (1 - t_raw); z_final = z_linear + bonus   ( t_raw z_linear -- z_final )
        f"swap dup 1.0 swap - * 8.0 * +\n"
        # write Z.                                                   ( z_final -- )
        f"3011 write-mailbox\n"
        # ── Contact check (every frame). Same (row, col) as player → FALL_DEATH.
        f"{mb_row} read-mailbox 400 read-mailbox = if "
        f"{mb_col} read-mailbox 401 read-mailbox = if "
        f"1 414 write-mailbox "
        f"then then\n"
        # ── Landing tick? cd_new <= 0.
        f"{mb_cd} read-mailbox 0 <= if "
        # Off-pyramid: row > 6 → retire to PHASE 0, park, clear director's mirror.
        f"{mb_row} read-mailbox 6 > if "
        f"0 {mb_phase} write-mailbox "
        f"0 {mb_active} write-mailbox "
        f"{REDBALL_PARK_Z} 3011 write-mailbox "
        f"exit "
        f"then "
        # Pick next direction via LFSR.                                 ( -- bit )
        f"{_RB_LFSR_STEP}"
        # Stash FROM_ROW, advance ROW (always +1).                    ( bit -- bit )
        f"{mb_row} read-mailbox dup {mb_from_row} write-mailbox 1 + {mb_row} write-mailbox "
        # Stash FROM_COL, advance COL if bit != 0.                    ( bit -- )
        f"{mb_col} read-mailbox dup {mb_from_col} write-mailbox "
        f"swap if 1 + then {mb_col} write-mailbox "
        # Stash START_Z (current Z at end of hop) and END_Z (Z at new row).
        f"3011 read-mailbox {mb_start_z} write-mailbox "
        f"{_RB_Z_BASE} {mb_row} read-mailbox {_RB_Z_MUL} * - {mb_end_z} write-mailbox "
        # Re-arm cooldown for the next hop.
        f"{REDBALL_HOP_TICKS} {mb_cd} write-mailbox "
        f"then\n"
    )

# Build the shared mesh + material once; clone the Blender object for each
# ball. The engine reads geometry from redball.iff (written by the wf_blender
# exporter from the Blender mesh+material).
#
# Geometry is an icosphere — icosahedron base + REDBALL_SUBDIV recursive
# loop-subdivisions, each new midpoint normalised back onto the sphere.
# Subdiv counts:
#   0 → 12 verts / 20 faces (icosahedron, blocky)
#   1 → 42 verts / 80 faces (default — recognisably round)
#   2 → 162 verts / 320 faces (smoother; heavier)
REDBALL_SUBDIV = 1
_REDBALL_RADIUS = 0.5
_REDBALL_PHI = (1.0 + math.sqrt(5.0)) / 2.0

def _normalise_to_radius(x, y, z, r):
    n = math.sqrt(x*x + y*y + z*z)
    return (x * r / n, y * r / n, z * r / n)

# Base icosahedron (12 verts, 20 faces, golden-rectangle construction).
_REDBALL_VERTS = [
    _normalise_to_radius( 0.0,  1.0,  _REDBALL_PHI, _REDBALL_RADIUS),
    _normalise_to_radius( 0.0,  1.0, -_REDBALL_PHI, _REDBALL_RADIUS),
    _normalise_to_radius( 0.0, -1.0,  _REDBALL_PHI, _REDBALL_RADIUS),
    _normalise_to_radius( 0.0, -1.0, -_REDBALL_PHI, _REDBALL_RADIUS),
    _normalise_to_radius( 1.0,  _REDBALL_PHI,  0.0, _REDBALL_RADIUS),
    _normalise_to_radius( 1.0, -_REDBALL_PHI,  0.0, _REDBALL_RADIUS),
    _normalise_to_radius(-1.0,  _REDBALL_PHI,  0.0, _REDBALL_RADIUS),
    _normalise_to_radius(-1.0, -_REDBALL_PHI,  0.0, _REDBALL_RADIUS),
    _normalise_to_radius( _REDBALL_PHI,  0.0,  1.0, _REDBALL_RADIUS),
    _normalise_to_radius( _REDBALL_PHI,  0.0, -1.0, _REDBALL_RADIUS),
    _normalise_to_radius(-_REDBALL_PHI,  0.0,  1.0, _REDBALL_RADIUS),
    _normalise_to_radius(-_REDBALL_PHI,  0.0, -1.0, _REDBALL_RADIUS),
]
_REDBALL_FACES = [
    (0, 2, 8),  (0, 8, 4),  (0, 4, 6),  (0, 6, 10), (0, 10, 2),
    (3, 1, 9),  (3, 9, 5),  (3, 5, 7),  (3, 7, 11), (3, 11, 1),
    (2, 5, 8),  (8, 5, 9),  (8, 9, 4),  (4, 9, 1),  (4, 1, 6),
    (6, 1, 11), (6, 11, 10),(10, 11, 7),(10, 7, 2), (2, 7, 5),
]

# Loop-subdivide REDBALL_SUBDIV times: each tri (a,b,c) becomes 4 tris
# {(a,ab,ca), (b,bc,ab), (c,ca,bc), (ab,bc,ca)} where ab/bc/ca are
# midpoints of the original edges, each pushed back onto the sphere.
def _redball_subdivide(verts, faces):
    cache = {}      # (i,j) → new vertex index, with i<j
    def midpoint(i, j):
        key = (min(i, j), max(i, j))
        idx = cache.get(key)
        if idx is not None:
            return idx
        ax, ay, az = verts[i]
        bx, by, bz = verts[j]
        mx, my, mz = _normalise_to_radius(
            (ax + bx) * 0.5, (ay + by) * 0.5, (az + bz) * 0.5,
            _REDBALL_RADIUS)
        idx = len(verts)
        verts.append((mx, my, mz))
        cache[key] = idx
        return idx
    new_faces = []
    for a, b, c in faces:
        ab = midpoint(a, b)
        bc = midpoint(b, c)
        ca = midpoint(c, a)
        new_faces += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
    return new_faces

for _ in range(REDBALL_SUBDIV):
    _REDBALL_VERTS = list(_REDBALL_VERTS)  # ensure mutable
    _REDBALL_FACES = _redball_subdivide(_REDBALL_VERTS, _REDBALL_FACES)

_redball_mesh = bpy.data.meshes.new('redball_mesh')
_redball_mesh.from_pydata(_REDBALL_VERTS, [], _REDBALL_FACES)
_redball_mesh.update()
_redball_mat = bpy.data.materials.new('redball_red')
_redball_mat.use_nodes = True
_redball_bsdf = _redball_mat.node_tree.nodes.get('Principled BSDF')
_redball_bsdf.inputs['Base Color'].default_value = (1.0, 0.0, 0.0, 1.0)
_redball_mesh.materials.append(_redball_mat)

# Capture actor index of the first ball so the director can address each via
# write-actor-mailbox (REDBALL_ACTOR_BASE + K). Mirrors the CUBE_ACTOR_BASE
# pattern.  All 3 balls created contiguously in this loop.
SCHEMA_PATH_KEY = 'wf_schema_path'
_pre_redball_actor_count = sum(1 for o in bpy.data.objects if o.get(SCHEMA_PATH_KEY))
REDBALL_ACTOR_BASE = _pre_redball_actor_count + 1   # 1-based

for _k in range(REDBALL_COUNT):
    _ball = bpy.data.objects.new(f'redball_{_k}', _redball_mesh)
    # Park off-screen — director will write initial XYZ when waking the ball.
    _ball.location = (0.0, 0.0, REDBALL_PARK_Z)
    scene.collection.objects.link(_ball)
    _ball['wf_schema_path']         = ENEMY_OAD
    _ball['wf_Mesh Name']           = 'redball.iff'
    _ball['wf_original_mesh_name']  = 'redball.iff'
    _ball['wf_Model Type']          = 'Mesh'
    _ball['wf_Mobility']            = 'Anchored'
    _ball['wf_Mass']                = 0.0
    _ball['wf_Visibility Mailbox']  = 1
    _ball['wf_NumberOfLocalMailboxes'] = 0   # state lives in globals 462..485
    _ball['wf_Script']              = redball_script(_k)

# Sanity assertion mirroring the cube-base drift check in section 7.
_post_redball_actor_count = sum(1 for o in bpy.data.objects if o.get(SCHEMA_PATH_KEY))
assert _post_redball_actor_count == _pre_redball_actor_count + REDBALL_COUNT, (
    f"Red ball actor count drift: expected +{REDBALL_COUNT}, got "
    f"{_post_redball_actor_count - _pre_redball_actor_count}")

print(f"[qbert] Created {REDBALL_COUNT} red balls "
      f"(actor indices {REDBALL_ACTOR_BASE}..{REDBALL_ACTOR_BASE + REDBALL_COUNT - 1}); "
      f"hop {REDBALL_HOP_TICKS} ticks; "
      f"per-ball mailbox bases "
      f"{', '.join(str(_rb_mb(k, 0)) for k in range(REDBALL_COUNT))}")

# ── 6. Director — wire its Script for the game loop ───────────────────────────
# MVP director: cube-state advance, visibility fan-out, win check, camera
# fan-out, HUD plumbing. Per actor.cc:665 statplats forbid scripts, so the
# 84 cube children are script-free; the director drives their visibility
# mailboxes every tick from the per-cube state mailboxes.
#
# Forth must be single-line in the .lev STR field, with \n escapes.
# Important Forth gotchas (learned the hard way):
#  - zForth has NO `\` line-comment word. The script handler in
#    engine/stubs/scripting_zforth.cc skips only the FIRST line as the
#    `\ wf` sigil; all subsequent `\` lines get parsed as the unknown
#    word `\` and abort with NOT_A_WORD.
#  - Use real "\n" newline chars in Python strings; the wf_blender
#    exporter converts them to the .lev `\n` escape, which iffcomp
#    decodes back to a runtime newline. Writing literal "\\n" in Python
#    causes the exporter to double-escape, producing a runtime "\n"
#    (backslash + n) that confuses the tokenizer.
#  - Stay within ASCII in the script body — non-ASCII bytes break
#    parsing.
# Camshot actor indices (assigned by .lev OBJ load order — verified via debug
# bridge: `wf_game --debug-port 7777` then watch INDEXOF_CAMSHOT=1021 at idle).
# These shift if you add/remove actors above them in blender_create_qbert.py.
# If the order changes, re-run the engine with --debug-port and re-check.
CS_PYRAMID_IDX = 8
CS_DEATH_IDX = 12
# cs_intro_0..cs_intro_4 are added immediately after cs_death in the actor
# list (see "Intro cinematic CamShots" block above), so they take indices
# 13..17 in OBJ load order. The director script references them as
# (intro phase + CS_INTRO_BASE_IDX). Cubes shift to idx 18+; cube indices
# don't matter (cubes are referenced by mailbox slot, not actor idx).
CS_INTRO_BASE_IDX = 13  # cs_intro_0 = 13, ..., cs_intro_4 = 17

# Death cutscene duration in ticks (~60 = 1s at 60 Hz).
CS_DEATH_HOLD_FRAMES = 60

# Intro state machine — leg durations in frames at 60 Hz (must match each
# destination CamShot's Pan Time in INTRO_CAMSHOTS / cs_pyramid Pan Time).
# Phase N: write shot[N] on first tick (timer==0), then wait
# INTRO_LEG_FRAMES[N] frames for the pan to complete before advancing.
#   phase 0 → cs_intro_0  (instant cut, 1 frame, before phase 1's pan starts)
#   phase 1 → cs_intro_1  (1.2 s pan from cs_intro_0)
#   phase 2 → cs_intro_2  (0.5 s pan)
#   phase 3 → cs_intro_3  (0.3 s pan)
#   phase 4 → cs_intro_4  (0.5 s pan)
#   phase 5 → cs_pyramid  (1.2 s pan; on advance to phase 6 set INTRO_DONE=1)
#   phase 6 → terminal (intro complete)
# Total: 1 + 72 + 30 + 18 + 30 + 72 = 223 frames ≈ 3.72 s at 60 Hz.
INTRO_LEG_FRAMES = [1, 72, 30, 18, 30, 72]

# ── Import Phase-1 color tables from gen_cube (data-only import) ──────────────
# We need the per-round/per-state TOP color LUT and the per-level LIT/SHADOW
# colors for the director Forth. gen_cube.py exposes them as module globals.
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("_gen_cube", os.path.join(SCRIPT_DIR, "gen_cube.py"))
_gen_cube = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_gen_cube)
ROUND_TOP_COLORS    = _gen_cube.ROUND_TOP_COLORS    # 16 × (s0, s1, s2)
LEVEL_SIDE_COLORS   = _gen_cube.LEVEL_SIDE_COLORS   # 4 × (lit, shadow)
ROUND_SIDE_OVERRIDES = _gen_cube.ROUND_SIDE_OVERRIDES  # {round_idx: (lit, shadow)}

# Compute CUBE_ACTOR_BASE here (before the director script needs it). The
# level loader assigns 1-based actor indices in scene-collection order.
# Cubes are appended last, so cube N's actor index = pre-cube count + 1 + N.
SCHEMA_PATH_KEY = 'wf_schema_path'
_pre_cube_actor_count = sum(1 for o in bpy.data.objects if o.get(SCHEMA_PATH_KEY))
CUBE_ACTOR_BASE = _pre_cube_actor_count + 1
print(f"[qbert] Pre-cube actor count = {_pre_cube_actor_count}; "
      f"CUBE_ACTOR_BASE = {CUBE_ACTOR_BASE} (first cube's actor index)")

# Forth fragment: populate ROUND_TOP_LUT (mb 256..303) at level init.
#   slot 256 + r*3 + s = top RGB for (round r, state s)
_top_lut_init = ""
for _r, (_s0, _s1, _s2) in enumerate(ROUND_TOP_COLORS):
    for _s, _rgb in enumerate((_s0, _s1, _s2)):
        _slot = INDEXOF_ROUND_TOP_LUT_BASE + _r * 3 + _s
        _top_lut_init += f"0x{_rgb:06X} {_slot} write-mailbox "

def _broadcast_color_to_all_cubes(rgb, mb_idx):
    """Forth fragment: write packed RGB to `mb_idx` on every one of the 28 cubes."""
    return (
        f"28 0 do "
        f"0x{rgb:06X} {mb_idx} {CUBE_ACTOR_BASE} i + write-actor-mailbox "
        f"loop "
    )

DIRECTOR_SCRIPT = "".join([
    "\\ wf qbert director MVP\n",  # first line skipped as sigil
    # One-shot level init — sets lives = 3 once on first tick. The player's
    # restart trigger ALSO writes lives=3 directly (mb 72=3) without
    # touching mb 421, so subsequent runs of this block are no-ops. Also
    # touches mb 70/71 so the HUD shows SCORE/TIMER lines from the start.
    # Phase 1 cube consolidation also populates the ROUND_TOP_LUT and writes
    # initial TOP/LIT/SHADOW colors to all 28 cubes so the first rendered
    # frame shows the L1R1 palette.
    "421 read-mailbox 0 = if ",
    "3 72 write-mailbox ",
    "0 70 write-mailbox 0 71 write-mailbox ",
    # Populate ROUND_TOP_LUT (mb 256..303) — 48 entries.
    _top_lut_init,
    # Initialize CUBE_PREV_STATE_BASE[N] to a sentinel (99) so the per-tick
    # state-change detector below fires once for every cube on the next tick
    # and writes their (R0, S0) TOP color.
    "28 0 do 99 228 i + write-mailbox loop ",
    # Write initial LIT/SHADOW for L1 to all 28 cubes.
    _broadcast_color_to_all_cubes(LEVEL_SIDE_COLORS[0][0], 3038),  # LIT
    _broadcast_color_to_all_cubes(LEVEL_SIDE_COLORS[0][1], 3039),  # SHADOW
    "0 427 write-mailbox ",   # LAST_LEVEL = 0 (L1)
    # Red Ball Phase B: seed LFSR, set first-ball delay, clear per-ball active mirrors.
    f"0xACE1 {RB_MB_LFSR} write-mailbox "          # LFSR seed (non-zero, arbitrary)
    f"120 {RB_MB_SPAWN_TIMER} write-mailbox "      # first ball ~2 s after INTRO_DONE
    + " ".join(f"0 {RB_MB_ACTIVE_BASE + k} write-mailbox" for k in range(REDBALL_COUNT))
    + " ",
    "1 421 write-mailbox ",   # LEVEL_INITIALIZED
    "then\n",
    # Intro state machine — runs only while phase 0..5; gates the rest of
    # the camera routing via mb 418 (INTRO_DONE). See the per-phase
    # narrative in the Python comments above INTRO_LEG_FRAMES.
    "416 read-mailbox 6 < if ",
    # First tick of this phase (timer==0): write the matching CamShot index.
    # Phase 0..4 → cs_intro_0..4 (indices 13..17). Phase 5 → cs_pyramid (8).
    "417 read-mailbox 0 = if ",
    f"416 read-mailbox dup 5 < if {CS_INTRO_BASE_IDX} + else drop {CS_PYRAMID_IDX} then ",
    "INDEXOF_CAMSHOT write-mailbox ",
    "then ",
    # Increment timer (every tick).
    "417 read-mailbox 1 + 417 write-mailbox ",
    # Compare timer to this phase's leg-duration threshold.
    "417 read-mailbox 416 read-mailbox ",
    f"dup 0 = if drop {INTRO_LEG_FRAMES[0]} else ",
    f"dup 1 = if drop {INTRO_LEG_FRAMES[1]} else ",
    f"dup 2 = if drop {INTRO_LEG_FRAMES[2]} else ",
    f"dup 3 = if drop {INTRO_LEG_FRAMES[3]} else ",
    f"dup 4 = if drop {INTRO_LEG_FRAMES[4]} else ",
    f"drop {INTRO_LEG_FRAMES[5]} ",
    "then then then then then ",
    # Threshold met: advance phase, reset timer. If just entered phase 6,
    # latch INTRO_DONE.
    "= if ",
    "416 read-mailbox 1 + dup 416 write-mailbox ",
    "0 417 write-mailbox ",
    "6 = if 1 418 write-mailbox then ",
    "then ",
    "then\n",
    # ── Red Ball Phase B spawn timing ─────────────────────────────────────────
    # Gated on INTRO_DONE. Each tick:
    #   - decrement RB_SPAWN_TIMER (mb 512)
    #   - when timer reaches 0: try to claim and wake the lowest-index idle ball,
    #     then re-arm timer to max(60, 300 - 12 * ROUND_NUMBER) ticks.
    # Each ball's activation writes 8 state mailboxes (COL/ROW/FROM_ROW/FROM_COL/
    # COOLDOWN/START_Z/END_Z/PHASE) via write-actor-mailbox + 1 director-mirror
    # write (RB_ACTIVE[K]) + 1 claim latch (RB_SPAWN_CLAIMED).
    f"418 read-mailbox 1 = if "
    f"{RB_MB_SPAWN_TIMER} read-mailbox dup 0 > if "
    f"1 - {RB_MB_SPAWN_TIMER} write-mailbox "
    f"else drop "
    # claimed := 0
    f"0 {RB_MB_SPAWN_CLAIMED} write-mailbox "
    + " ".join(
        # For each ball K, try to claim. Each block: if not yet claimed AND
        # ball K is idle, step LFSR, write all 8 ball mailboxes, mirror active,
        # latch claimed.
        f"{RB_MB_SPAWN_CLAIMED} read-mailbox 0 = if "
        f"{RB_MB_ACTIVE_BASE + k} read-mailbox 0 = if "
        # LFSR step → ( bit )
        f"{_RB_LFSR_STEP}"
        # Activate ball K (write-actor-mailbox stack: val mb actor):
        #   COL := bit (consumes the bit on top of stack)
        f"{_rb_mb(k, _RB_OFF_COL)} {REDBALL_ACTOR_BASE + k} write-actor-mailbox "
        #   ROW := 1, FROM_ROW := 0, FROM_COL := 0
        f"1 {_rb_mb(k, _RB_OFF_ROW)} {REDBALL_ACTOR_BASE + k} write-actor-mailbox "
        f"0 {_rb_mb(k, _RB_OFF_FROM_ROW)} {REDBALL_ACTOR_BASE + k} write-actor-mailbox "
        f"0 {_rb_mb(k, _RB_OFF_FROM_COL)} {REDBALL_ACTOR_BASE + k} write-actor-mailbox "
        #   COOLDOWN := HOP_TICKS
        f"{REDBALL_HOP_TICKS} {_rb_mb(k, _RB_OFF_COOLDOWN)} {REDBALL_ACTOR_BASE + k} write-actor-mailbox "
        #   START_Z := Z@row0 (apex), END_Z := Z@row1
        f"{_RB_Z_AT_ROW_0} {_rb_mb(k, _RB_OFF_START_Z)} {REDBALL_ACTOR_BASE + k} write-actor-mailbox "
        f"{_RB_Z_AT_ROW_1} {_rb_mb(k, _RB_OFF_END_Z)} {REDBALL_ACTOR_BASE + k} write-actor-mailbox "
        #   PHASE := 1 (start hopping)
        f"1 {_rb_mb(k, _RB_OFF_PHASE)} {REDBALL_ACTOR_BASE + k} write-actor-mailbox "
        # Director-mirror RB_ACTIVE[K] := 1 ; CLAIMED := 1
        f"1 {RB_MB_ACTIVE_BASE + k} write-mailbox "
        f"1 {RB_MB_SPAWN_CLAIMED} write-mailbox "
        f"then then "
        for k in range(REDBALL_COUNT)
    )
    + " "
    # Re-arm timer = max(60, 300 - 12 * ROUND_NUMBER)
    f"425 read-mailbox 12 * 300 swap - dup 60 < if drop 60 then {RB_MB_SPAWN_TIMER} write-mailbox "
    f"then then\n",
    # Camshot routing: cs_death hold + FALL_DEATH latch + game-over fold-in.
    f"414 read-mailbox 1 = if {CS_DEATH_IDX} INDEXOF_CAMSHOT write-mailbox ",
    f"{CS_DEATH_HOLD_FRAMES} 415 write-mailbox ",
    "72 read-mailbox 1 - dup 72 write-mailbox ",
    "0 = if 1 420 write-mailbox then ",
    "0 414 write-mailbox then\n",
    "418 read-mailbox 1 = if ",
    "415 read-mailbox dup 0 > if 1 - dup 415 write-mailbox ",
    f"0 = if {CS_PYRAMID_IDX} INDEXOF_CAMSHOT write-mailbox then ",
    "else drop 100 read-mailbox dup 0 <> if INDEXOF_CAMSHOT write-mailbox else drop then ",
    "then ",
    "then\n",
    # Cube-state advance on landed event (unchanged from prior design).
    "411 read-mailbox 0 <> if ",
    "400 read-mailbox dup 1 + * 2 / 401 read-mailbox + 200 + ",
    "dup read-mailbox 0 = if 2 swap write-mailbox else drop then ",
    "0 411 write-mailbox then\n",
    # ── Per-cube TOP-color update on state change ───────────────────────────
    # Every tick, for each cube N (0..27):
    #   cur  = read CUBE_STATE_BASE + N         ( 200..227 )
    #   prev = read CUBE_PREV_STATE_BASE + N    ( 228..255 )
    #   if cur != prev:
    #     rgb = read ROUND_TOP_LUT[ROUND_NUMBER * 3 + cur]
    #     write rgb to actor (CUBE_ACTOR_BASE + N) mailbox 3037 (FACE_COLOR_TOP)
    #     write cur to CUBE_PREV_STATE_BASE + N
    # Inner body stack notes inline.
    "28 0 do ",
    # ( -- )
    "200 i + read-mailbox ",      # ( cur )
    "228 i + read-mailbox ",      # ( cur prev )
    "over over <> if ",           # ( cur prev )  — branch if cur != prev
    "drop ",                      # ( cur ) — drop prev
    # Look up rgb = ROUND_TOP_LUT[ROUND_NUMBER * 3 + cur]
    "425 read-mailbox 3 * over + 256 + read-mailbox ",  # ( cur rgb )
    # write rgb 3037 (CUBE_ACTOR_BASE + i) write-actor-mailbox
    f"3037 {CUBE_ACTOR_BASE} i + write-actor-mailbox ",  # ( cur ) — rgb consumed
    # Update prev: 228 + i = i + 228, i is loop index. Actually we still have cur on stack.
    "228 i + write-mailbox ",     # ( ) — wrote `cur` to mb 228+i
    "else ",
    "drop drop ",                 # ( ) — drop cur and prev (no change)
    "then ",
    "loop\n",
    # ── Level-transition LIT/SHADOW broadcast ───────────────────────────────
    # cur_level = ROUND_NUMBER // 4 (with int-cast, since `/` is float in zForth).
    # If cur_level != LAST_LEVEL, broadcast new lit/shadow to all 28 cubes,
    # then set LAST_LEVEL = cur_level.
    # zForth int-divide trick: `n dup 4 % - 4 /` → integer (n // 4).
    "425 read-mailbox dup 4 % - 4 / ",   # ( cur_level )
    "dup 427 read-mailbox <> if ",       # ( cur_level )
    # Save cur_level to LAST_LEVEL first, then look up colors.
    "dup 427 write-mailbox ",            # ( cur_level ) — wrote LAST_LEVEL
    # Look up lit/shadow per level via if/else cascade (4 levels).
    "dup 0 = if drop ",
    f"  {_broadcast_color_to_all_cubes(LEVEL_SIDE_COLORS[0][0], 3038)}",
    f"  {_broadcast_color_to_all_cubes(LEVEL_SIDE_COLORS[0][1], 3039)}",
    "else dup 1 = if drop ",
    f"  {_broadcast_color_to_all_cubes(LEVEL_SIDE_COLORS[1][0], 3038)}",
    f"  {_broadcast_color_to_all_cubes(LEVEL_SIDE_COLORS[1][1], 3039)}",
    "else dup 2 = if drop ",
    f"  {_broadcast_color_to_all_cubes(LEVEL_SIDE_COLORS[2][0], 3038)}",
    f"  {_broadcast_color_to_all_cubes(LEVEL_SIDE_COLORS[2][1], 3039)}",
    "else drop ",
    f"  {_broadcast_color_to_all_cubes(LEVEL_SIDE_COLORS[3][0], 3038)}",
    f"  {_broadcast_color_to_all_cubes(LEVEL_SIDE_COLORS[3][1], 3039)}",
    "then then then ",
    "else drop then\n",
    # Win check: count cubes with state != 2. Latch ROUND_CLEAR when count == 0.
    "0 28 0 do 200 i + read-mailbox 2 <> if 1 + then loop ",
    "dup 412 write-mailbox 0 = if 1 413 write-mailbox then\n",
    # Round-clear countdown — start 90-tick timer on win latch, on expiry
    # reset cube states, clear win flag, increment ROUND_NUMBER, respawn.
    # capture-trigger fires at LATCH so the host snaps the won state.
    "413 read-mailbox 1 = if 424 read-mailbox 0 = if ",
    "90 424 write-mailbox 3 432 write-mailbox ",
    "then then\n",
    "424 read-mailbox dup 0 > if ",
    "1 - dup 424 write-mailbox ",
    "0 = if ",
    # Reset per-cube state to 0 — the per-tick state-change detector above
    # will see (cur=0, prev=2) on the next tick and re-write the new round's
    # state-0 TOP color to every cube. No visibility fan-out needed.
    "28 0 do 0 200 i + write-mailbox loop ",
    "0 411 write-mailbox ",
    "0 413 write-mailbox ",
    "425 read-mailbox dup 15 < if 1 + then 425 write-mailbox ",
    "0 400 write-mailbox 0 401 write-mailbox 0 402 write-mailbox ",
    "0 414 write-mailbox 0 415 write-mailbox 0 419 write-mailbox ",
    "1 426 write-mailbox ",   # apex respawn flag for player
    "then ",
    "else drop then\n",
])
if director:
    director['wf_Script'] = DIRECTOR_SCRIPT

# ── 7. Create 28 cube actors at pyramid positions ────────────────────────────
# Phase 1 (2026-05-10) collapsed the prior 1344-actor visibility-fan-out (28
# positions × 16 rounds × 3 states) down to 28 actors. Per-frame face colors
# come from runtime EMAILBOX_FACE_COLOR_TOP/LIT/SHADOW writes by the director,
# not from baked-in .iff variants. All 28 actors reference the same cube.iff.
#
# CUBE_ACTOR_BASE was computed above (before the director script generation)
# from the count of objects already in scene.objects when the cube creation
# loop runs. The director uses CUBE_ACTOR_BASE + N to address cube N.
#
# Verify that the count we captured still matches now. If anything between
# the count and this point added/removed actors, the indices will be wrong.
_now_actor_count = sum(1 for o in bpy.data.objects if o.get(SCHEMA_PATH_KEY))
assert _now_actor_count == _pre_cube_actor_count, (
    f"Actor count drifted between CUBE_ACTOR_BASE capture ({_pre_cube_actor_count}) "
    f"and cube creation ({_now_actor_count}); director Forth will address the "
    f"wrong actors. Move the CUBE_ACTOR_BASE calculation closer to here.")

# One shared mesh datablock for all 28 cubes (saves Blender memory; engine
# reads geometry from cube.iff regardless).
_cube_mesh = bpy.data.meshes.new('cube_mesh_shared')
_s = CUBE_SIZE / 2
_box_verts = [
    (-_s, -_s, -_s), ( _s, -_s, -_s), ( _s,  _s, -_s), (-_s,  _s, -_s),
    (-_s, -_s,  _s), ( _s, -_s,  _s), ( _s,  _s,  _s), (-_s,  _s,  _s),
]
_box_faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
              (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
_cube_mesh.from_pydata(_box_verts, [], _box_faces)
_cube_mesh.update()

print(f"[qbert] Creating {TOTAL_CUBES} cube actors (one per pyramid position, "
      f"all referencing cube.iff)...")
created_count = 0
for row in range(NUM_ROWS):
    for col in range(row + 1):
        N = cube_index(row, col)
        wx, wy, wz = cube_world_position(row, col)
        obj_name = f"cube_{N:02d}"
        obj = bpy.data.objects.new(obj_name, _cube_mesh)
        obj.location = (wx, wy, wz)
        obj.rotation_euler = (0.0, 0.0, math.pi / 4)  # diamond top
        scene.collection.objects.link(obj)

        obj['wf_schema_path'] = STATPLAT_OAD
        obj['wf_Mesh Name'] = 'cube.iff'
        # The exporter (export_level.py:986) chooses mesh_filename from
        # wf_original_mesh_name if set, else obj.name + ".iff". Without setting
        # this, each cube would get its own cube_NN.iff entry — defeating the
        # whole point of consolidation. Force the shared name.
        obj['wf_original_mesh_name'] = 'cube.iff'
        obj['wf_Model Type'] = 'Mesh'
        obj['wf_Mobility'] = 'Anchored'
        obj['wf_Mass'] = 0.0
        # Visibility: always-visible. mb 1 is hardwired to TRUE
        # (mailbox.inc:10), so this slot reads 1 forever and the cube stays
        # rendered. Per-cube hide/show is no longer needed in Phase 1.
        obj['wf_Visibility Mailbox'] = 1
        created_count += 1

print(f"[qbert] Created {created_count} cube actors.")

# ── 8. Wireframe-display non-rendering infrastructure ────────────────────────
# Per docs/level-building.md "Blender Viewport Display by Object Type": anything
# whose wf_Model Type is not 'Mesh' or 'Matte' doesn't render in the game
# engine, so display it as Wire in Blender to keep the viewport readable.
RENDERED_MODEL_TYPES = ('Mesh', 'Matte')
wire_count = 0
for obj in bpy.data.objects:
    if obj.type != 'MESH':
        continue
    mt = obj.get('wf_Model Type', None)
    if mt not in RENDERED_MODEL_TYPES:
        obj.display_type = 'WIRE'
        wire_count += 1
print(f"[qbert] Set {wire_count} non-rendering objects to wireframe display.")

# ── 9. Save the .blend so the user can open it interactively ─────────────────
OUT_BLEND = os.path.join(SCRIPT_DIR, 'qbert_practice.blend')
print(f"[qbert] Saving .blend to {OUT_BLEND}")
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)

# ── 9. Export the level ─────────────────────────────────────────────────────────
print(f"[qbert] Exporting to {OUT_LEV}")
bpy.ops.wf.export_level(filepath=OUT_LEV)

# Phase 1 cube consolidation (2026-05-10):
# All 28 cube actors reference the same cube.iff via wf_Mesh Name. The Blender
# exporter writes a placeholder cube.iff with the shared mesh's default
# (white) materials; we overwrite it with the gen_cube.py output (proper
# 3-material MATL chunk). One file replaces the prior 1344-file fan-out.
import subprocess
gen_cube_py = os.path.join(SCRIPT_DIR, 'gen_cube.py')
print(f"[qbert] Generating cube.iff via gen_cube.py")
subprocess.check_call([sys.executable, gen_cube_py, SCRIPT_DIR])

# Clean up stale per-actor cube .iff files from the prior fan-out design so
# build_level_binary.sh / iffcomp doesn't pick them up by accident.
import glob
stale_count = 0
# Old fan-out: cube_NN_rR_sS.iff (1344 files)
for stale in glob.glob(os.path.join(SCRIPT_DIR, 'cube_[0-9][0-9]_r*_s*.iff')):
    os.remove(stale)
    stale_count += 1
# Old gen_cube.py output: cube_state{0,1,2}_r{0..15}.iff (48 files) and the
# even older cube_state{0,1,2}.iff (3 files) from before the per-round expansion.
for stale in glob.glob(os.path.join(SCRIPT_DIR, 'cube_state*.iff')):
    os.remove(stale)
    stale_count += 1
# Per-actor placeholders the exporter may also have written from earlier runs
# before we set wf_original_mesh_name='cube.iff' — cube_NN.iff and cube_NN_sN.iff.
for stale in glob.glob(os.path.join(SCRIPT_DIR, 'cube_[0-9][0-9].iff')):
    os.remove(stale)
    stale_count += 1
for stale in glob.glob(os.path.join(SCRIPT_DIR, 'cube_[0-9][0-9]_s*.iff')):
    os.remove(stale)
    stale_count += 1
if stale_count:
    print(f"[qbert] Removed {stale_count} stale cube .iff files from prior designs.")

print(f"[qbert] Done — {OUT_LEV}")
