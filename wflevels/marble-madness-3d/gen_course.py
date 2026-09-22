#!/usr/bin/env python3
"""gen_course.py -- course-description JSON -> marble-madness-3d.lev (headless Blender).

    blender --background --python gen_course.py -- course-test.json
    blender --background --python gen_course.py -- --help

Strategy mirrors the non-marble pipeline templates (wflevels/pilot_demo,
wflevels/qbert_practice, wflevels/smb_w1_1): import snowgoons-blender.lev for
known-good infrastructure actors (room / camera / camshot / target / director /
levelobj / matte / light / player), strip snowgoons' gameplay actors, then
rebuild the scene from the course JSON and export via the wf_blender addon.

Everything about the level that depends on the course -- geometry, spawn, goal
AABB, kill plane, room bbox, camera anchor -- is computed from the JSON.  Nothing
is hand-tuned per course.  See README.md for the contract and the numbers.
"""

from __future__ import annotations

import math
import os
import sys

import addon_utils
import bpy

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(SCRIPT_DIR, '..', '..'))
SNOWGOONS_LEV = os.path.join(REPO, 'wflevels', 'snowgoons-blender', 'snowgoons-blender.lev')
OAD_DIR = os.path.join(REPO, 'wfsource', 'source', 'oas')
STATPLAT_OAD = os.path.join(REPO, 'wftools', 'wf_oad', 'tests', 'fixtures', 'statplat.oad')
OUT_LEV = os.path.join(SCRIPT_DIR, 'marble-madness-3d.lev')
OUT_BLEND = os.path.join(SCRIPT_DIR, 'marble-madness-3d.blend')

sys.path.insert(0, SCRIPT_DIR)
import course_geom as cg   # noqa: E402

# ── Marble ────────────────────────────────────────────────────────────────────
MARBLE_R = 0.5
SPHERE_SEGMENTS = 20
SPHERE_RINGS = 12

# ── Camera: true-isometric SW follow shot ─────────────────────────────────────
# offset (-d, -d, +d): horizontal distance d*sqrt(2), so elevation =
# atan(d / (d*sqrt(2))) = 35.264 deg -- TRUE isometric, the closest a perspective
# camera gets to the arcade's 2:1 view.  The elevation is scale-free, so CAM_D
# controls ONLY how much course is on screen.
#
# ENGINE TRUTH, not doc truth: the CamShot FOV / Hither / Yon fields are DEAD.
# CameraHandler::SetCamera (movecam.cc:190) writes position + orientation and
# carries an explicit `#pragma message ("KTS: write field of view, hither and yon
# code")` -- it never touches them -- and the renderer hardcodes a 60 deg VERTICAL
# fov with near=1, far=1000 (gfx/gl/display.cc:666).  So framing is distance-only:
#     visible vertical extent = 2 * (CAM_D * sqrt(3)) * tan(30 deg) = 2 * CAM_D
# CAM_D = 8 puts 16 m of course on screen and the 1 m marble at ~30 px of 480.
# The FOV/Yon values below are authored to MATCH the renderer so the .lev does not
# claim something the engine does not honour.
CAM_D = 8.0
CAM_OFFSET = (-CAM_D, -CAM_D, CAM_D)
CAM_FOV = 60.0
CAM_HITHER = 1.0
CAM_YON = 1000.0
# BungeeCam spring: vel = (desired - pos) / (dt * Elasticity) (movecam.cc:971).
# The OAD default of 10 lags the marble far enough to push it off-centre at speed;
# 1.0 (the field minimum) converges within a couple of frames.
CAM_ELASTICITY = 1.0
CAM_CLIMB_RATE = 0.0

# ── Lighting ──────────────────────────────────────────────────────────────────
# Light::Set reads the direction off the actor's local +X axis and hands it to the
# shader UNNEGATED, so it points TOWARD the light:
#   Rz(C).Ry(B).(1,0,0) = (cos B cos C, cos B sin C, -sin B)   =>   B = -alt, C = az.
# Course geometry is wound OUTWARD (floors +Z), so a face is lit when the vector has
# a positive Z -- i.e. a POSITIVE altitude.  (smb_w1_1 uses a negative altitude only
# because its box meshes are wound inward.)  Bearing 200 deg == SSW, near the camera,
# so the wall faces the iso view actually sees are the lit ones.
SUN_ALT_DEG = 55.0
SUN_AZ_DEG = 200.0
SUN_KEY = 0.85
SUN_AMBIENT = 0.55
SKY_COLOR = 0x141c2c          # matte background

# ── Marble physics (MarbleHandler; see README.md "Marble physics") ────────────
RUNNING_ACCEL = 26.0
RUNNING_DECEL = 0.004         # terminal slope speed = a / (30 * decel)
MAX_GROUND_SPEED = 20.0
MAX_AIR_SPEED = 60.0
FALLING_ACCEL = 9.8

# ── Mailbox map (global user range 2..999) ───────────────────────────────────
MB_STATE = 13        # 0 = rolling, 2 = FINISH (marble frozen in the goal)
MB_PX, MB_PY, MB_PZ = 20, 21, 22
MB_T0 = 23           # level TIME at which the current countdown started
MB_RESPAWN = 24      # Director -> Player one-shot
MB_FALLS = 25        # respawn counter (falls + timeouts)
HUD_SCORE, HUD_TIMER, HUD_LIVES = 70, 71, 72   # read by game.cc:614-616
NUM_MAILBOXES = 100
TIME_LIMIT = 60.0    # seconds

# ── Materials (index order MUST match course_geom.MAT_*) ──────────────────────
MATERIALS = (
    ('mm3d_floor_a', (0.62, 0.63, 0.66)),   # MAT_FLOOR_A -- light grey
    ('mm3d_floor_b', (0.42, 0.43, 0.47)),   # MAT_FLOOR_B -- dark grey
    ('mm3d_wall',    (0.34, 0.28, 0.36)),   # MAT_WALL    -- cliff faces
    ('mm3d_skirt',   (0.20, 0.18, 0.24)),   # MAT_SKIRT   -- void sides
    ('mm3d_goal',    (0.95, 0.72, 0.12)),   # MAT_GOAL    -- amber platform
)
MARBLE_COLOR = (0.22, 0.52, 1.00)

KEEP_CLASSES = {'director', 'camera', 'levelobj', 'matte', 'light',
                'room', 'camshot', 'target', 'player'}
# Every snowgoons gameplay actor goes: their meshes reference snowgoons .tga files
# we do not ship, and textile aborts the build if it cannot find them (see
# docs/level-design-troubleshooting.md "the four-gotcha chain", gotcha 3).
DELETE_CLASSES = {'statplat', 'enemy', 'snowman01', 'missile', 'tool', 'tool01',
                  'ground01', 'hp', 'gold', 'generator', 'actboxor', 'actbox'}


# ═══════════════════════════════════════════════════════════════════════════════
# helpers


def get_class(obj):
    schema = obj.get('wf_schema_path', '')
    return os.path.splitext(os.path.basename(schema))[0] if schema else ''


def find_by_class(cn):
    for obj in bpy.data.objects:
        if get_class(obj) == cn:
            return obj
    return None


def make_material(name, rgb):
    """Flat Principled BSDF, base colour only -- no texture image.

    export_level._extract_mat_info reads `Base Color`.default_value verbatim and
    packs it as R<<16|G<<8|B with flags=0 (FLAT_SHADED), so these numbers ARE the
    final in-game colour.  No texture => textile has nothing to look up, which is
    what keeps the build from dying on a missing .tga.
    """
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bsdf is not None:
        bsdf.inputs['Base Color'].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
    mat.diffuse_color = (rgb[0], rgb[1], rgb[2], 1.0)
    return mat


def fnum(v):
    """Forth literal -- plain ASCII, bounded precision."""
    return ('%.4f' % float(v)).rstrip('0').rstrip('.') or '0'


# ═══════════════════════════════════════════════════════════════════════════════
# Forth


def player_script(spawn, goal, kill_z):
    """Per-frame marble script: camera-relative input, fall respawn, goal latch.

    zForth rules honoured here (docs/level-design-troubleshooting.md
    "zForth scripts"): real newlines, no `\\` comments after line 1, ASCII only,
    `&`/`|` not `and`/`or`, and every `if/else/then` lives AFTER the last `;` so it
    compiles in compile mode.
    """
    gmin, gmax = goal['min'], goal['max']
    return '\n'.join([
        '\\ wf mm3d marble',
        # Rotate the four direction bits 45 deg CW so screen-up == world NE for the
        # SW-iso camera.  Valid because the marble's Euler C is pi/2, which makes
        # MarbleHandler's fwd = currentDir() = (cos C, sin C, 0) = +Y and
        # right = (fwd.Y, -fwd.X, 0) = +X.  (physicalobject.hpi:52 is authoritative;
        # the movement.cc:698 comment saying (sin C, cos C, 0) is wrong.)
        ': cam-remap  0',
        '  over 0x0800 & if 0x2800 | then',
        '  over 0x1000 & if 0x5000 | then',
        '  over 0x2000 & if 0x3000 | then',
        '  over 0x4000 & if 0x4800 | then',
        '  swap drop ;',
        ': px INDEXOF_X_POS read-mailbox ;',
        ': py INDEXOF_Y_POS read-mailbox ;',
        ': pz INDEXOF_Z_POS read-mailbox ;',
        ': publish px %d write-mailbox py %d write-mailbox pz %d write-mailbox ;'
        % (MB_PX, MB_PY, MB_PZ),
        ': halt 0 INDEXOF_XSPEED write-mailbox 0 INDEXOF_YSPEED write-mailbox'
        ' 0 INDEXOF_ZSPEED write-mailbox ;',
        ': home %s INDEXOF_X_POS write-mailbox %s INDEXOF_Y_POS write-mailbox'
        ' %s INDEXOF_Z_POS write-mailbox halt ;'
        % (fnum(spawn[0]), fnum(spawn[1]), fnum(spawn[2])),
        # FINISH: kill the input and the HORIZONTAL velocity only.  Zeroing Z too
        # would leave the marble hanging wherever it happened to latch -- and it
        # would still creep, because the script runs AFTER MarbleHandler has already
        # applied one frame of gravity.  Letting Z alone lets it settle onto the
        # goal platform and stay there.
        ': freeze 0 INDEXOF_INPUT write-mailbox'
        ' 0 INDEXOF_XSPEED write-mailbox 0 INDEXOF_YSPEED write-mailbox ;',
        ': drive INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox cam-remap'
        ' INDEXOF_INPUT write-mailbox ;',
        ': bail home %d read-mailbox 1 + %d write-mailbox %d read-mailbox %d write-mailbox ;'
        % (MB_FALLS, MB_FALLS, MB_FALLS, HUD_SCORE),
        ': goal? px %s >= px %s <= & py %s >= & py %s <= & pz %s >= & pz %s <= & ;'
        % (fnum(gmin[0]), fnum(gmax[0]), fnum(gmin[1]),
           fnum(gmax[1]), fnum(gmin[2]), fnum(gmax[2])),
        'publish',
        '%d read-mailbox 2 = if freeze else' % MB_STATE,
        '  %d read-mailbox if 0 %d write-mailbox bail then' % (MB_RESPAWN, MB_RESPAWN),
        '  goal? if 2 %d write-mailbox freeze else' % MB_STATE,
        '    drive',
        '    pz %s < if bail then' % fnum(kill_z),
        '  then',
        'then',
    ]) + '\n'


def director_script():
    """Level countdown.  Runs last each tick (level.cc:881-888), so the respawn
    one-shot it raises is consumed by the marble on the NEXT tick -- 16 ms, invisible."""
    return '\n'.join([
        '\\ wf mm3d director',
        ': now INDEXOF_TIME read-mailbox ;',
        ': t0 %d read-mailbox ;' % MB_T0,
        ': remain %s now t0 - - ;' % fnum(TIME_LIMIT),
        # display.cc:1225 gates the whole arcade HUD on
        #   (score | timer | lives | game_over | ...) != 0
        # so a level that lets all of them fall to zero loses its HUD entirely.
        # Writing LIVES every tick keeps it up even when the score and the frozen
        # timer are both 0.
        '1 %d write-mailbox' % HUD_LIVES,
        't0 0= if now %d write-mailbox then' % MB_T0,
        # On FINISH the clock simply stops being written, so the HUD holds the
        # time the marble finished with.
        '%d read-mailbox 2 <> if' % MB_STATE,
        '  remain dup 0 <= if',
        '    drop 0 %d write-mailbox 1 %d write-mailbox now %d write-mailbox'
        % (HUD_TIMER, MB_RESPAWN, MB_T0),
        '  else',
        '    %d write-mailbox' % HUD_TIMER,
        '  then',
        'then',
    ]) + '\n'


# ═══════════════════════════════════════════════════════════════════════════════
# scene construction


def build_course_meshes(chunks, mats):
    """One statplat mesh actor per chunk.  Vertices are baked in WORLD space and
    the actor sits at the origin, so the Jolt trimesh body (actor pos + local verts,
    actor.cc:586 -> physical.hpi:JoltMakeStaticMesh) lands exactly on the course."""
    objs = []
    for ch in chunks:
        name = 'mm3d_course_%02d' % ch.index
        mesh = bpy.data.meshes.new(name + '_mesh')
        mesh.from_pydata([tuple(v) for v in ch.verts], [],
                         [(f[0], f[1], f[2]) for f in ch.faces])
        mesh.update()
        for mat_name, rgb in mats:
            mesh.materials.append(bpy.data.materials[mat_name])
        for poly, face in zip(mesh.polygons, ch.faces):
            poly.material_index = face[3]
        mesh.shade_flat()

        obj = bpy.data.objects.new(name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        obj.location = (0.0, 0.0, 0.0)
        obj['wf_schema_path'] = STATPLAT_OAD
        obj['wf_Mesh Name'] = name + '.iff'
        obj['wf_original_mesh_name'] = name + '.iff'      # <= 31 bytes (assets.cc:254)
        obj['wf_Model Type'] = 'Mesh'
        obj['wf_Mobility'] = 'Anchored'                    # StatPlats must be anchored
        obj['wf_Mass'] = 0.0
        obj['wf_Visibility Mailbox'] = 1
        objs.append(obj)
    return objs


def build_marble_mesh():
    bpy.ops.mesh.primitive_uv_sphere_add(radius=MARBLE_R, segments=SPHERE_SEGMENTS,
                                         ring_count=SPHERE_RINGS, location=(0, 0, 0))
    obj = bpy.context.object
    obj.data.materials.clear()
    obj.data.materials.append(bpy.data.materials['mm3d_marble'])
    for poly in obj.data.polygons:
        poly.material_index = 0
    obj.data.shade_flat()
    return obj


def wf_light_aim(alt_deg, az_deg):
    return (0.0, -math.radians(alt_deg), math.radians(az_deg))


def _min_tri_cross(mesh):
    """Smallest cross-product length over the mesh's triangles.

    Vector3::Normalize asserts length > Scalar(0,4) == 4/65536 == 6.1e-5
    ("Probably have a polygon which is too small", math/vector3.hpi:243), and the
    face normal is that cross product, so this must clear the threshold.
    """
    worst = float('inf')
    for poly in mesh.polygons:
        vs = [mesh.vertices[i].co for i in poly.vertices]
        for k in range(1, len(vs) - 1):
            _, _, _, ln = cg.tri_normal(tuple(vs[0]), tuple(vs[k]), tuple(vs[k + 1]))
            worst = min(worst, ln)
    return worst


def generate(course_path):
    course = cg.load_course(course_path)
    chunks, soup = cg.build_chunks(course)
    cmin, cmax = cg.course_bounds(chunks)

    spawn = list(course['spawn'])
    lifted = cg.spawn_clearance_z(chunks, spawn, MARBLE_R)
    if lifted > spawn[2] + 1e-9:
        print('[mm3d] spawn Z %.3f -> %.3f (Jolt zone-volume clearance: the marble must '
              'poke out of every static body that could otherwise swallow the course)'
              % (spawn[2], lifted))
        spawn[2] = lifted

    print('[mm3d] course "%s": %d cells, %d tris (%d degenerate dropped), %d chunk(s) %s verts'
          % (course['name'], len(course['cells']), len(soup.tris), soup.dropped_degenerate,
             len(chunks), [len(c.verts) for c in chunks]))

    # ── 1. Clean scene + addon ────────────────────────────────────────────────
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable('wf_blender', default_set=False, persistent=False)
    scene = bpy.context.scene

    # ── 2. Import snowgoons infrastructure, strip its gameplay ────────────────
    print('[mm3d] importing %s' % SNOWGOONS_LEV)
    bpy.ops.wf.import_level(filepath=SNOWGOONS_LEV)
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
        elif cn:
            bpy.data.objects.remove(obj, do_unlink=True)
    print('[mm3d] classes after strip:', sorted({get_class(o) for o in bpy.data.objects}))

    for name, rgb in MATERIALS:
        make_material(name, rgb)
    make_material('mm3d_marble', MARBLE_COLOR)

    # ── 3. Player FIRST ───────────────────────────────────────────────────────
    # Deliberate ordering: the exported .lev lists actors in scene order, and
    # JoltCharacterCreate's zone-volume filter only inspects static bodies that
    # ALREADY exist.  Creating the marble before the course chunks means there are
    # none -- belt-and-braces alongside the spawn lift above.
    player = find_by_class('player')
    assert player is not None, 'no player actor imported from snowgoons'
    player.name = 'Player'
    marble = build_marble_mesh()
    min_cross = _min_tri_cross(marble.data)
    assert min_cross > 1e-4, ('marble sphere has a sub-threshold triangle (cross=%g); '
                              'lower SPHERE_SEGMENTS/SPHERE_RINGS' % min_cross)
    old_data = player.data
    player.data = marble.data
    player.data.name = 'mm3d_marble_mesh'
    bpy.data.objects.remove(marble, do_unlink=True)
    if old_data is not None and old_data.users == 0:
        bpy.data.meshes.remove(old_data)

    player.location = tuple(spawn)
    # currentDir() = (cos C, sin C, 0); C = pi/2 -> fwd = +Y, right = +X, which is
    # what the cam-remap word above assumes.
    player.rotation_euler = (0.0, 0.0, math.pi / 2)
    player['wf_original_mesh_name'] = 'mm3d_marble.iff'
    player['wf_Mesh Name'] = 'mm3d_marble.iff'
    # Overwrite the bbox snowgoons' player carried -- it is the ColSpace the Jolt
    # CharacterVirtual is built from (jolt_backend.cc:JoltCharacterCreate), and a
    # cube-shaped box would not roll.  Equal half-extents in all three axes make
    # Jolt pick a SphereShape of radius 0.5.
    player['wf_original_bbox'] = (-MARBLE_R, -MARBLE_R, -MARBLE_R,
                                  MARBLE_R, MARBLE_R, MARBLE_R)
    player['wf_had_authored_bbox'] = True
    player['wf_Model Type'] = 'Mesh'
    player['wf_Visibility Mailbox'] = 1
    player['wf_Mobility'] = 'Physics'
    player['wf_Mass'] = 1.0
    player['wf_Moves Between Rooms'] = 'True'
    player['wf_Turn Rate'] = 0.0                    # selects MarbleHandler
    player['wf_Running Acceleration'] = RUNNING_ACCEL
    player['wf_Running Deceleration'] = RUNNING_DECEL
    player['wf_Max Ground Speed'] = MAX_GROUND_SPEED
    player['wf_Max Air Speed'] = MAX_AIR_SPEED      # 0 would zero gravity in AirHandler
    player['wf_Horiz Air Drag'] = 0.0
    player['wf_Vert Air Drag'] = 0.0
    player['wf_Air Acceleration'] = 0.0
    player['wf_Jumping Acceleration'] = 0.0
    player['wf_Falling Acceleration'] = FALLING_ACCEL
    player['wf_Script Controls Input'] = 'True'     # required before INPUT (3024) accepts writes
    player['wf_Script'] = player_script(spawn, course['goal'], course['kill_z'])

    # ── 4. Course geometry ────────────────────────────────────────────────────
    build_course_meshes(chunks, MATERIALS)

    # ── 5. Camera rig ─────────────────────────────────────────────────────────
    # SetCameraParametersFromShot (movecam.cc:247):
    #     position  = (camShotPos - Follow.pos) + TrackObject.pos   [Relative axes]
    #     direction =  Target.pos - camShotPos                      [absolute camShotPos]
    # Anchor BOTH Follow and Target on a target actor at the world origin and put the
    # camshot at the OFFSET itself, so
    #     position  = offset + playerPos        (follows exactly, every frame)
    #     direction = 0 - offset = -offset      (constant -- a genuinely fixed iso view)
    # Target = Player would instead make the view direction swing as the marble
    # travels away from spawn, because direction always uses the STATIC camshot pos.
    anchor = find_by_class('target')
    assert anchor is not None, 'no target actor imported from snowgoons'
    anchor.name = 'Target01'
    anchor.location = (0.0, 0.0, 0.0)
    anchor['wf_Model Type'] = 'None'

    camshot = find_by_class('camshot')
    assert camshot is not None, 'no camshot actor imported from snowgoons'
    camshot.name = 'cs_iso'
    camshot.location = CAM_OFFSET
    camshot['wf_Position X'] = 'Relative'
    camshot['wf_Position Y'] = 'Relative'
    camshot['wf_Position Z'] = 'Relative'
    camshot['wf_Rotation'] = 'Fixed'
    camshot['wf_Track Object'] = player.name
    camshot['wf_Follow'] = anchor.name
    camshot['wf_Target'] = anchor.name
    camshot['wf_FOV'] = CAM_FOV
    camshot['wf_Hither'] = CAM_HITHER
    camshot['wf_Yon'] = CAM_YON
    camshot['wf_Elasticity'] = CAM_ELASTICITY
    camshot['wf_Climb Rate'] = CAM_CLIMB_RATE
    camshot['wf_Pan Time In Seconds'] = 0.1
    camshot['wf_Model Type'] = 'None'

    cam_world = tuple(spawn[k] + CAM_OFFSET[k] for k in range(3))
    camera = find_by_class('camera')
    if camera:
        camera.name = 'Camera01'
        camera.location = cam_world
        camera['wf_FoggingStartDistance'] = 120.0
        camera['wf_FoggingCompleteDistance'] = CAM_YON
        camera['wf_FoggingColor'] = SKY_COLOR
        camera['wf_Model Type'] = 'None'

    # ── 6. Director / levelobj / matte ────────────────────────────────────────
    director = find_by_class('director')
    if director:
        director.name = 'Director'
        director.location = (0.0, 0.0, 0.0)
        director['wf_Model Type'] = 'None'
        director['wf_Script'] = director_script()

    levelobj = find_by_class('levelobj')
    if levelobj:
        levelobj.name = 'LevelObj'
        levelobj.location = (0.0, 0.0, 0.0)
        levelobj['wf_Number Of Mailboxes'] = NUM_MAILBOXES
        levelobj['wf_Model Type'] = 'None'

    matte = find_by_class('matte')
    if matte:
        matte.name = 'Matte'
        matte.location = (0.0, 0.0, 0.0)
        matte['wf_Matte Type'] = 'Color'
        matte['wf_Background Color'] = SKY_COLOR
        matte['wf_Visibility Mailbox'] = 1
        matte['wf_Model Type'] = 'None'

    # ── 7. Lighting ───────────────────────────────────────────────────────────
    light = find_by_class('light')
    assert light is not None, 'no light actor imported from snowgoons'
    light.name = 'Light01'
    light.location = ((cmin[0] + cmax[0]) / 2.0, (cmin[1] + cmax[1]) / 2.0, cmax[2] + 10.0)
    light.rotation_euler = wf_light_aim(SUN_ALT_DEG, SUN_AZ_DEG)
    light['wf_lightType'] = 'Directional'
    light['wf_lightRed'] = SUN_KEY
    light['wf_lightGreen'] = SUN_KEY
    light['wf_lightBlue'] = SUN_KEY
    # Mandatory: u_ambient defaults to Color::black (game/level.cc), so any face the
    # directional light does not face renders pure black.
    ambient = light.copy()
    scene.collection.objects.link(ambient)
    ambient.name = 'AmbientLight'
    ambient['wf_lightType'] = 'Ambient'
    ambient['wf_lightRed'] = SUN_AMBIENT
    ambient['wf_lightGreen'] = SUN_AMBIENT
    ambient['wf_lightBlue'] = SUN_AMBIENT

    # ── 8. Room bbox = everything, computed, never hand-tuned ────────────────
    # Must strictly contain: all geometry, the marble anywhere it can reach, the
    # camera at every marble position, the origin anchor, the camshot actor, the
    # lights, and the kill plane.  Too small => "fell out of room" + terminate
    # (docs/level-design-troubleshooting.md).
    pts = [cmin, cmax, (0.0, 0.0, 0.0), CAM_OFFSET, tuple(light.location)]
    for corner in (cmin, cmax):
        pts.append(tuple(corner[k] + CAM_OFFSET[k] for k in range(3)))
    rmin = [min(p[k] for p in pts) for k in range(3)]
    rmax = [max(p[k] for p in pts) for k in range(3)]
    MARGIN = 20.0
    rmin = [v - MARGIN for v in rmin]
    rmax = [v + MARGIN for v in rmax]
    # A falling marble is only caught on the frame its script sees Z < kill_z; at the
    # 0.2 s dt cap (display.cc) it can travel far in one step, so leave a deep floor.
    rmin[2] = min(rmin[2], course['kill_z'] - 60.0)

    room = find_by_class('room')
    assert room is not None, 'no room actor imported from snowgoons'
    room.name = 'Room'
    room.location = (0.0, 0.0, 0.0)
    room['wf_original_bbox'] = tuple(rmin) + tuple(rmax)
    room['wf_had_authored_bbox'] = True
    room['wf_Adjacent Room 1'] = ''
    room['wf_Adjacent Room 2'] = ''
    print('[mm3d] room bbox (%.1f, %.1f, %.1f) .. (%.1f, %.1f, %.1f)'
          % (rmin[0], rmin[1], rmin[2], rmax[0], rmax[1], rmax[2]))

    # ── 9. Export ─────────────────────────────────────────────────────────────
    order = [o.name for o in scene.objects if o.get('wf_schema_path')]
    print('[mm3d] export order:', order)
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    ok = bpy.ops.wf.export_level(filepath=OUT_LEV)
    print('[mm3d] exported %s (%r)' % (OUT_LEV, ok))
    return 0


def main():
    argv = sys.argv
    args = argv[argv.index('--') + 1:] if '--' in argv else []
    if not args or args[0] in ('-h', '--help'):
        print(__doc__.strip())
        print('\nusage: blender --background --python gen_course.py -- <course.json>')
        return 0 if args and args[0] in ('-h', '--help') else 2
    return generate(os.path.abspath(args[0]))


if __name__ == '__main__':
    rc = main()
    if rc:
        sys.exit(rc)
