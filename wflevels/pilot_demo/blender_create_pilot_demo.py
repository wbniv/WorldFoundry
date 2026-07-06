#!/usr/bin/env python3
"""blender_create_pilot_demo.py — minimal WF level with an in-level PILOT {Script}.

Mirrors qbert_practice's strategy: import snowgoons-blender for known-good
infrastructure (room / camera / light / matte / camshot / player), strip the
snowgoons gameplay actors, and set the PLAYER's Script to a PILOT program.

The PILOT script's first line is the `R:pilot` sigil — the engine's ScriptRouter
content-sniff sees the hardcoded Forth language id (actor.cc), detects `R:pilot`,
and re-routes to the PILOT engine (kDispatch slot 6). The program is a
frame-resumable state machine: set a sentinel into GOLD (proves it ran), then
every 0.1 LevelClock-seconds (PA:) bump GOLD and slide the player +X — so the run
is verifiable over the debug bridge (GOLD ≥ 1234, rising) AND visible (player
drifts right).

Run:
  blender --background --python wflevels/pilot_demo/blender_create_pilot_demo.py
Then:
  bash wftools/wf_blender/build_level_binary.sh pilot_demo
"""
import os
import addon_utils
import bpy

SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
REPO          = os.path.normpath(os.path.join(SCRIPT_DIR, '..', '..'))
SNOWGOONS_LEV = os.path.join(REPO, 'wflevels', 'snowgoons-blender', 'snowgoons-blender.lev')
OUT_LEV       = os.path.join(SCRIPT_DIR, 'pilot_demo.lev')
OUT_BLEND     = os.path.join(SCRIPT_DIR, 'pilot_demo.blend')
STATPLAT_OAD  = os.path.join(REPO, 'wftools', 'wf_oad', 'tests', 'fixtures', 'statplat.oad')

# ── The in-level PILOT script (set on the player) ───────────────────────────────
# Real newlines; one statement per line. mb(GOLD)=3001, mb(X_POS)=3009 are the
# player's own local-system mailboxes; PA: waits LevelClock seconds.
PILOT_SCRIPT = (
    "R:pilot  in-level PILOT demo — drives the player actor\n"
    "C:#tick = 0\n"
    "C:mb(GOLD) = 1234\n"
    "*top\n"
    "C:#tick = #tick + 1\n"
    "C:mb(GOLD) = mb(GOLD) + 1\n"
    "C:mb(X_POS) = mb(X_POS) + 0.05\n"
    "PA:0.1\n"
    "J:*top\n"
)

KEEP_CLASSES   = {'director', 'camera', 'levelobj', 'matte', 'light',
                  'room', 'camshot', 'target', 'actboxor', 'player'}
# Drop ALL snowgoons gameplay geometry (incl. statplat) — its meshes reference
# dozens of snowgoons .tga textures we don't ship, which fail textile. We build
# our own flat-colored primitive floor instead (no texture files), and that
# floor is the room's renderable geometry (without one, levcomp emits nRooms=0
# and the engine's room-slot loader hits assets.cc:190 roundedSize==entry._size).
DELETE_CLASSES = {'statplat', 'enemy', 'snowman01', 'missile',
                  'tool', 'tool01', 'ground01', 'hp'}


def get_class(obj):
    schema = obj.get('wf_schema_path', '')
    return os.path.splitext(os.path.basename(schema))[0] if schema else ''


def find_by_class(cn):
    for obj in bpy.data.objects:
        if get_class(obj) == cn:
            return obj
    return None


# 1. Clean scene + enable the addon.
bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("wf_blender", default_set=False, persistent=False)
scene = bpy.context.scene

# 2. Import snowgoons infrastructure.
print(f"[pilot_demo] importing {SNOWGOONS_LEV}")
bpy.ops.wf.import_level(filepath=SNOWGOONS_LEV)

# 3. Strip snowgoons gameplay; dedup infrastructure (qbert's recipe).
for obj in list(bpy.data.objects):
    if get_class(obj) in DELETE_CLASSES:
        bpy.data.objects.remove(obj, do_unlink=True)
seen = set()
for obj in list(bpy.data.objects):
    cn = get_class(obj)
    if cn in KEEP_CLASSES:
        if cn in seen:
            bpy.data.objects.remove(obj, do_unlink=True)
        else:
            seen.add(cn)
print("[pilot_demo] classes after strip:", sorted({get_class(o) for o in bpy.data.objects}))

# 4. Retarget the player's Script to PILOT.
player = find_by_class('player')
assert player is not None, "no player object imported from snowgoons"
player['wf_Mobility'] = 'Anchored'
player['wf_Model Type'] = 'Mesh'
player['wf_Visibility Mailbox'] = 1
player['wf_Script'] = PILOT_SCRIPT
# Let the autodetect heuristic see it as non-Forth; the engine ignores this
# field (content-sniff is authoritative) but keep the authoring metadata honest.
player['wf_ScriptLanguage'] = 'Other'
# Stand the player on the floor near the origin corner, where the snowgoons
# camshot already looks. Its PILOT script slides it +X across the floor.
player.location = (3.0, 3.0, 1.0)
print("[pilot_demo] player Script set to PILOT")

# 4b. Build a flat-colored primitive floor: a 1 km × 1 km slab from the origin
# extending +X/+Y, top surface at z=0. A solid-color material (no texture file)
# keeps textile happy; this slab is the room's renderable geometry.
FX, FY, FZ = 1000.0, 1000.0, 1.0     # +X extent, +Y extent, thickness (down from z=0)
fmesh = bpy.data.meshes.new('floor_mesh')
verts = [(0, 0, -FZ), (FX, 0, -FZ), (FX, FY, -FZ), (0, FY, -FZ),   # bottom z=-FZ
         (0, 0, 0),   (FX, 0, 0),   (FX, FY, 0),   (0, FY, 0)]      # top    z=0
faces = [(4, 5, 6, 7),                                              # top (+Z, visible)
         (3, 2, 1, 0),                                              # bottom (-Z)
         (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]    # sides
fmesh.from_pydata(verts, [], faces)
fmesh.update()
fmat = bpy.data.materials.new('floor_slate')
fmat.use_nodes = True
_bsdf = fmat.node_tree.nodes.get('Principled BSDF')
if _bsdf:
    _bsdf.inputs['Base Color'].default_value = (0.30, 0.45, 0.35, 1.0)
fmat.diffuse_color = (0.30, 0.45, 0.35, 1.0)
fmesh.materials.append(fmat)
for poly in fmesh.polygons:
    poly.material_index = 0
floor = bpy.data.objects.new('floor', fmesh)
scene.collection.objects.link(floor)
floor.location = (0.0, 0.0, 0.0)
floor['wf_schema_path'] = STATPLAT_OAD
floor['wf_Mesh Name'] = 'floor.iff'
floor['wf_original_mesh_name'] = 'floor.iff'
floor['wf_Model Type'] = 'Mesh'
floor['wf_Mobility'] = 'Anchored'
floor['wf_Mass'] = 0.0
floor['wf_Visibility Mailbox'] = 1
print("[pilot_demo] built 1km floor (+X/+Y from origin)")

# 4c. Expand the room so its bbox contains the floor + player. levcomp assigns
# actors to rooms by world-center, so the slab (center ~(500,500,0)) needs a
# room large enough to claim it.
room = find_by_class('room')
if room:
    room.location = (0.0, 0.0, 0.0)
    room['wf_original_bbox'] = (-50.0, -50.0, -100.0, FX + 50.0, FY + 50.0, 100.0)
    print("[pilot_demo] room bbox expanded to cover the floor")

# 4d. Re-point the CamShot at the player. Both OBJREFERENCE fields (Target =
# look-at, Track Object = follow) held names of snowgoons objects we deleted, so
# their indices dangle → the camera asserts `shotData->Target` (movecam.cc:289)
# and the assert-exit then terminates on the bridge listener thread. Aim a fixed
# shot from in front of + above the player so it's framed in the screenshot.
camshot = find_by_class('camshot')
if camshot:
    px, py, pz = player.location
    camshot.location = (px, py - 25.0, pz + 16.0)
    camshot['wf_Position X'] = 'Absolute'
    camshot['wf_Position Y'] = 'Absolute'
    camshot['wf_Position Z'] = 'Absolute'
    camshot['wf_Rotation'] = 'Fixed'          # look at Target (not free-track)
    camshot['wf_Target'] = player.name        # look-at the player
    camshot['wf_Track Object'] = player.name   # follow the player
    print(f"[pilot_demo] camshot aimed at player '{player.name}'")

# 5. Export.
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print(f"[pilot_demo] exporting {OUT_LEV}")
bpy.ops.wf.export_level(filepath=OUT_LEV)
print("[pilot_demo] done")
