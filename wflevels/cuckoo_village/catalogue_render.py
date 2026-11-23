"""Render the parts catalogue's pictures, inside Blender (plan: docs/plans/2026-11-21-cuckoo-village.md; scripts/cuckoo-village-catalogue.py).

Called by blender_create_cuckoo_village.py when CUCKOO_CATALOGUE=<dir> is set, after every actor exists and is posed. For each entry of
catalogue_entries.py it writes into <dir>:

    <id>-iso.png    the part on its own, from the front left and above (Cycles, CPU), fitted to its bounding box
    <id>-ctx.png    where it is: the village or the tower with the part in magenta
    <id>-wire.svg   the same view as the iso picture, as vector edges with the hidden lines removed (painter's order)
    views.json      per entry: triangles, vertices, size in metres, instance count

Pure bpy; the entry texts are in catalogue_entries.py so the host script can lay the pages out without Blender.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

import bmesh
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

W, H = 560, 420
INK, PAPER = "#1d2a36", "#e9edf1"
HIGHLIGHT = (1.0, 0.16, 0.84, 1.0)
CANDLE_CELLS = set(range(214, 227))     # sticks and flames
WINDOW_CELLS = set(range(200, 213))
BIRD_CELL, BLOCKS_CELL, FLOWERS_CELL, BAVARIA_CELL, CLASSIC_CELL = 213, 228, 227, 230, 231


def _scene():
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 16
    sc.cycles.use_denoising = False
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
    sc.view_settings.view_transform = "Standard"
    sc.render.image_settings.file_format = "PNG"
    sc.world = bpy.data.worlds.new("catalogue_world")
    sc.world.use_nodes = True
    bg = sc.world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.70, 0.76, 0.84, 1.0)
    bg.inputs[1].default_value = 1.1
    sun = bpy.data.objects.new("catalogue_sun", bpy.data.lights.new("catalogue_sun", "SUN"))
    sun.data.energy = 3.4
    sun.rotation_euler = (math.radians(52), math.radians(8), math.radians(-32))
    sc.collection.objects.link(sun)
    cam_data = bpy.data.cameras.new("catalogue_cam")
    cam = bpy.data.objects.new("catalogue_cam", cam_data)
    sc.collection.objects.link(cam)
    sc.camera = cam
    return sc, cam, cam_data


def _highlight_material():
    m = bpy.data.materials.new("catalogue_highlight")
    m.use_nodes = True
    nodes, links = m.node_tree.nodes, m.node_tree.links
    nodes.clear()
    em = nodes.new("ShaderNodeEmission")
    em.inputs[0].default_value = HIGHLIGHT
    em.inputs[1].default_value = 3.0
    out = nodes.new("ShaderNodeOutputMaterial")
    links.new(em.outputs[0], out.inputs[0])
    return m


def _face_range(obj, label):
    """The polygon index range of the labelled section of `obj` (recorded by the part builders as `cat_sections`)."""
    spans = json.loads(obj.get("cat_sections", "[]"))
    n = len(obj.data.polygons)
    for i, (name, start) in enumerate(spans):
        if name == label:
            return start, (spans[i + 1][1] if i + 1 < len(spans) else n)
    raise KeyError(f"{obj.name} has no section {label!r}: {[s[0] for s in spans]}")


def _subset(obj, faces, name):
    """A new object holding only the polygons whose index passes `faces`, with the source's materials, UVs and place."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    doomed = [f for f in bm.faces if not faces(f.index)]
    bmesh.ops.delete(bm, geom=doomed, context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    for m in obj.data.materials:
        mesh.materials.append(m)
    new = bpy.data.objects.new(name, mesh)
    new.matrix_world = obj.matrix_world.copy()
    bpy.context.scene.collection.objects.link(new)
    return new


def _world_points(objs):
    pts = []
    for o in objs:
        mw = o.matrix_world
        pts.extend(mw @ v.co for v in o.data.vertices)
    return pts


def _stats(objs, instances):
    pts = _world_points(objs)
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return dict(triangles=sum(len(p.vertices) - 2 for o in objs for p in o.data.polygons), vertices=sum(len(o.data.vertices) for o in objs),
                size_m=[round(hi[i] - lo[i], 3) for i in range(3)], instances=instances), lo, hi


def _aim(cam, cam_data, points, direction):
    """An orthographic camera looking along -direction at `points`, centred and scaled to fit them."""
    d = Vector(direction).normalized()
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    rot = cam.rotation_euler.to_matrix()                       # not matrix_world: that is stale until the dependency graph runs
    right, up = rot @ Vector((1, 0, 0)), rot @ Vector((0, 1, 0))
    us, vs = [p.dot(right) for p in points], [p.dot(up) for p in points]
    umid, vmid = (min(us) + max(us)) / 2, (min(vs) + max(vs)) / 2
    centre = right * umid + up * vmid + d * (sum(p.dot(d) for p in points) / len(points))
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = max(max(us) - min(us), (max(vs) - min(vs)) * W / H, 0.05) * 1.18
    cam_data.clip_start, cam_data.clip_end = 0.01, 400.0
    cam.location = centre + d * 60.0
    bpy.context.view_layer.update()


def _perspective(cam, cam_data, location, target, lens=45.0):
    cam_data.type = "PERSP"
    cam_data.lens = lens
    cam_data.clip_start, cam_data.clip_end = 0.1, 400.0
    cam.location = Vector(location)
    cam.rotation_euler = (Vector(target) - Vector(location)).to_track_quat("-Z", "Y").to_euler()
    bpy.context.view_layer.update()


def _wire_svg(sc, cam, objs, fill_limit=3200):
    """The objects' polygon edges as SVG, seen from `cam`: far polygons first, each filled with the paper colour so near ones hide far ones."""
    polys = []
    for o in objs:
        mw = o.matrix_world
        pts = [world_to_camera_view(sc, cam, mw @ v.co) for v in o.data.vertices]
        for p in o.data.polygons:
            ring = [pts[i] for i in p.vertices]
            polys.append((sum(r.z for r in ring) / len(ring), [(r.x * W, (1 - r.y) * H) for r in ring]))
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">', f'<rect width="{W}" height="{H}" fill="{PAPER}"/>']
    if len(polys) <= fill_limit:
        polys.sort(key=lambda t: -t[0])
        out.append(f'<g fill="{PAPER}" stroke="{INK}" stroke-width="0.7" stroke-linejoin="round">')
        out.extend('<polygon points="%s"/>' % " ".join(f"{x:.1f},{y:.1f}" for x, y in ring) for _, ring in polys)
        out.append("</g>")
    else:                                                                    # too dense to fill: plain edges, drawn lightly
        d = "".join("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in ring) + "Z" for _, ring in polys)
        out.append(f'<path d="{d}" fill="none" stroke="{INK}" stroke-width="0.35" stroke-opacity="0.55"/>')
    out.append("</svg>")
    return "\n".join(out)


def run(objs_all, entries, out_dir, tower_z, all_entries=None):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    sc, cam, cam_data = _scene()
    bpy.context.view_layer.update()          # the builder moved and posed actors: matrix_world is stale until the dependency graph runs
    hl = _highlight_material()
    engine = {n for e in (all_entries or entries) if e["kind"] == "engine" for n in e["actors"]}
    meshes = [o for o in objs_all if o.type == "MESH" and o.name not in engine]
    for o in objs_all:
        if o.name in engine:
            o.hide_render = True
    views_file = out / "views.json"
    stats = json.loads(views_file.read_text()) if views_file.is_file() else {}          # a partial run adds to what is there
    draw = not os.environ.get("CUCKOO_CATALOGUE_NORENDER")             # NORENDER: recompute the measurements and rings only

    def show_only(names):
        for o in meshes:
            o.hide_render = o.name not in names

    def context_visibility(entry):
        """The village as the entry's context picture shows it: the Bavarian set or the Classic one, candles and the bird only when the card is about them."""
        bav = entry.get("mode") == "bavaria"
        about = set(entry["actors"])
        by_name = {o.name: o for o in meshes}
        candles_on = any(by_name[n].get("wf_Visibility Mailbox") in CANDLE_CELLS for n in about if n in by_name)
        blocks_on = any(by_name[n].get("wf_Visibility Mailbox") == BLOCKS_CELL for n in about if n in by_name)
        glow_on = any(by_name[n].get("wf_Visibility Mailbox") in WINDOW_CELLS for n in about if n in by_name)
        for o in meshes:
            cell = o.get("wf_Visibility Mailbox")
            hide = False
            if cell == BAVARIA_CELL:
                hide = not bav
            elif cell == CLASSIC_CELL:
                hide = bav
            elif cell in CANDLE_CELLS:
                hide = not candles_on
            elif cell in WINDOW_CELLS:
                hide = not glow_on
            elif cell == BLOCKS_CELL:
                hide = not blocks_on
            elif cell == FLOWERS_CELL:
                hide = blocks_on
            o.hide_render = hide
            if o.name in about:
                o.hide_render = False

    for entry in entries:
        if entry["kind"] == "engine":
            continue
        eid, names = entry["id"], entry["actors"]
        src = [o for o in meshes if o.name in names]
        assert len(src) == len(names), f"{eid}: missing actors {set(names) - {o.name for o in src}}"
        iso_names = entry.get("iso") or names
        temp = []
        # ---- the part on its own
        if entry["kind"] == "section" and entry.get("section"):
            base = next(o for o in src)
            f0, f1 = _face_range(base, entry["section"])
            piece = _subset(base, lambda i, a=f0, b=f1: a <= i < b, f"cat_{eid}")
            temp.append(piece)
            shown = [piece]
        else:
            shown = [o for o in meshes if o.name in iso_names]
        extra = [o for o in meshes if o.name in entry.get("with", [])]          # shown beside it for scale or sense (a tree beside its candles)
        show_only({o.name for o in shown + extra})
        st, lo, hi = _stats(shown, len(names) if entry.get("iso") else 1)
        stats[eid] = st
        framing = [o for o in meshes if o.name in entry["frame"]] if entry.get("frame") else shown
        pts = _world_points(framing)
        ground = entry["group"].startswith("The ground")
        size = st["size_m"]
        thin = min(range(3), key=lambda a: size[a])
        if min(size) < 0.12 * max(size) and thin == 1:          # a flat plate or a bar seen edge-on from the side: look at it from the front
            direction = (-0.22, -1.0, 0.18)
        elif ground or (min(size) < 0.12 * max(size) and thin == 2):
            direction = (-0.45, -0.7, 1.25)
        else:
            direction = (-0.55, -1.0, 0.50)
        _aim(cam, cam_data, pts, direction)
        sc.render.filepath = str(out / f"{eid}-iso.png")
        if draw:
            bpy.ops.render.render(write_still=True)
        if entry.get("wire"):
            (out / f"{eid}-wire.svg").write_text(_wire_svg(sc, cam, shown))
        for t in temp:
            t.hide_render = True
        # ---- where it is
        context_visibility(entry)
        swapped = []
        if entry["kind"] == "section" and entry.get("section"):
            base = src[0]
            f0, f1 = _face_range(base, entry["section"])
            base.hide_render = True
            rest = _subset(base, lambda i, a=f0, b=f1: not (a <= i < b), f"cat_rest_{eid}")
            mark = _subset(base, lambda i, a=f0, b=f1: a <= i < b, f"cat_mark_{eid}")
            mark.data.materials.clear()
            mark.data.materials.append(hl)
            for p in mark.data.polygons:
                p.material_index = 0
            temp += [rest, mark]
        else:
            seen = set()                                        # thirteen cottages share one mesh: swap and restore each mesh once
            for o in src:
                if o.data.name in seen:
                    continue
                seen.add(o.data.name)
                swapped.append((o, [m for m in o.data.materials]))
                for i in range(len(o.data.materials)):
                    o.data.materials[i] = hl
        if entry.get("ctx", "village") == "tower":
            _perspective(cam, cam_data, (-4.2, -12.6, tower_z + 4.4), (0.0, -1.0, tower_z + 3.5), 42.0)
        else:
            cam_data.type = "ORTHO"
            cam_data.ortho_scale = 38.0
            cam_data.clip_start, cam_data.clip_end = 0.1, 400.0
            cam.location = Vector((-22.0, -34.0, 31.0))
            cam.rotation_euler = (Vector((0.5, -0.5, 0.8)) - cam.location).to_track_quat("-Z", "Y").to_euler()
            bpy.context.view_layer.update()
        focus = [o for o in temp if o.name.startswith("cat_mark_")] or src                 # what is magenta: ringed by the host when it is small
        box = [world_to_camera_view(sc, cam, o.matrix_world @ v.co) for o in focus for v in o.data.vertices]
        stats[eid]["ctx_box"] = [round(min(b.x for b in box) * W, 1), round((1 - max(b.y for b in box)) * H, 1),
                                 round(max(b.x for b in box) * W, 1), round((1 - min(b.y for b in box)) * H, 1)]
        sc.render.filepath = str(out / f"{eid}-ctx.png")
        if draw:
            bpy.ops.render.render(write_still=True)
        for o, mats in swapped:
            for i, m in enumerate(mats):
                o.data.materials[i] = m
        if entry["kind"] == "section" and entry.get("section"):
            src[0].hide_render = False
        for t in temp:
            bpy.data.objects.remove(t, do_unlink=True)
        views_file.write_text(json.dumps(stats, indent=1))
        print(f"[cuckoo-village] catalogue: {eid}")
    (out / "views.json").write_text(json.dumps(stats, indent=1))
    return stats
