#!/usr/bin/env python3
"""Desktop pose trace (the plan's verification step 8): the exported seahorse rig in the
mockup's seven poses, through the DFRM reference evaluator (the engine's maths in
Python), with the Phase 3 contact solve holding each grip on its post.

For each pose it writes one PNG (side view as the tank camera sees it, the post in grey,
tail rings shaded by how much of their joint limit they use, red at >= 97 %) and records:

- max_limit_use: the largest |angle| / limit over every joint (flex, lateral, twist, head
  and eyes), over the pose and its 1 s ease in from rest (30 frames);
- frame_flips: frames whose sample frame turns more than 90 degrees from one joint to the
  next, or from one frame to the next, or loses its handedness (FK never re-derives
  angles, so this must be 0);
- wrap_centre_error_mm (grips only): the Director's solve run as the game runs it, one
  frame late with the centre extrapolated, while the body sways on its holdfast (the
  hold_idle clip under the pose's knots) for 6 s at 20 Hz: the largest distance (real
  mm) between this frame's wrap centre and the post axis.

The poses are dfrm_ref.PRESETS (tail-rig.html), except that a vertical grip takes its wrap
start from the post radius (seahorse.wrap_start, Phase 3), so no ring exceeds its limit.

    python3 wflevels/aquarium_tanks/seahorse_poses.py --out docs/plans/2026-10-16-saltwater-seahorses/evidence/phase3
"""
from __future__ import annotations

import argparse
import json
import math
import struct
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import dfrm_ref as ref  # noqa: E402
import seahorse as sh  # noqa: E402

dc = ref.dc
POSES = [('rest', 'rest'), ('grip-branch', 'branch'), ('grip-stem', 'stem'), ('swim', 'swim'),
         ('probe', 'probe'), ('twine', 'twine'), ('startle', 'startle')]
MM = .01
DT = .05
SIZE = 700
SCALE = 520            # pixels per world unit


def load_rig(sex='f'):
    data = (ROOT / f'wflevels/aquarium_plants/seahorse_{sex}_body.iff').read_bytes()
    o, chunks = 8, {}
    while o < len(data):
        size = struct.unpack_from('<I', data, o + 4)[0]
        chunks[data[o:o + 4].decode()] = data[o + 8:o + 8 + size]
        o += 8 + size + (-size % 4)
    verts = [struct.unpack_from('<iiIiii', chunks['VRTX'], 24 * i) for i in range(len(chunks['VRTX']) // 24)]
    rest = [[x / 65536, y / 65536, z / 65536] for _u, _v, _c, x, y, z in verts]
    faces = [struct.unpack_from('<hhhh', chunks['FACE'], 8 * i)[:3] for i in range(len(chunks['FACE']) // 8)]
    return ref.Rig(dc.decode(chunks['DFRM']), rest, faces)


def to_world(world, p):
    return [p[0] * world[0] + p[1] * world[3] + p[2] * world[6],
            p[0] * world[1] + p[1] * world[4] + p[2] * world[7],
            p[0] * world[2] + p[1] * world[5] + p[2] * world[8]]


def block_for(name):
    """The preset's block; a vertical grip takes the Phase 3 wrap start for its radius."""
    block = ref.preset_block(name)
    if int(block[21]) == 2:
        block[22] = float(sh.wrap_start(block[23]))
    return block


def limit_use(rig, angles, block):
    F, L, T = angles
    use = 0.0
    for i, smp in enumerate(rig.c['samples']):
        ven, dor, lat, tw = smp['limits']
        use = max(use, F[i] / ven if F[i] > 0 else -F[i] / dor, abs(L[i]) / lat, abs(T[i]) / tw)
    for t, tr in enumerate(rig.c['transforms']):
        v = block[30 + t]
        use = max(use, v / tr['hi'] if v > 0 else (v / tr['lo'] if tr['lo'] < 0 else 0.0))
    return use


def frames_of(rig, angles):
    """The FK sample frames (d, v, s), recomputed from the evaluated angles exactly as the
    evaluator propagates them."""
    F, L, T = angles
    d, v, s = rig.d0[:], rig.v0[:], rig.s0[:]
    out = []
    for i in range(len(F)):
        d, v = ref.rot(d, v, math.radians(F[i]))
        d, s = ref.rot(d, s, math.radians(L[i]))
        v, s = ref.rot(v, s, math.radians(T[i]))
        if (i + 1) % 8 == 0:
            d, v, s = ref.orthonormalize(d, v)
        out.append((d, v, s))
    return out


def flips(frames, previous=None):
    n = 0
    for i, (d, v, s) in enumerate(frames):
        if ref.dot(ref.cross(v, d), s) < .99:        # lost handedness or orthonormality (s = v x d)
            n += 1
        if i and (ref.dot(frames[i - 1][0], d) < 0 or ref.dot(frames[i - 1][1], v) < 0):
            n += 1
        if previous and (ref.dot(previous[i][0], d) < 0 or ref.dot(previous[i][1], v) < 0):
            n += 1
    return n


def ease_in(rig, name, world):
    """30 frames from the straight rest block to the pose (knots and wrap progress together)."""
    target = block_for(name)
    worst, flipped, prev, clamped = 0.0, 0, None, 0
    for k in range(31):
        a = k / 30
        b = [x * a for x in target]
        b[21], b[22], b[23] = target[21], target[22], target[23]
        r = ref.evaluate(rig, b, 0.0, world, chain_only=True)
        worst = max(worst, limit_use(rig, r['angles'], b))
        fr = frames_of(rig, r['angles'])
        flipped += flips(fr, prev)
        prev = fr
        clamped += r['status'] == 3
    return worst, flipped, clamped


def axis_of(mode, world):
    """The post axis direction in world: vertical, or the body's side axis for a branch."""
    return [0.0, 0.0, 1.0] if mode == 2 else ref.normalize(to_world(world, [0.0, 1.0, 0.0]))


def hold_trace(rig, name, world):
    """The Director's contact solve (seahorse_behaviour.fth sh-solve, generalised to a
    branch): the body moves so the extrapolated last-frame wrap centre lies on the axis,
    while hold_idle sways the free rings under the pose's knots. Returns the body position,
    the post anchor and the worst error (world units) over 6 s at 20 Hz."""
    base = block_for(name)
    base[25], base[26] = float(sh.CLIP_IDS['hold_idle']), 0.0
    mode = int(base[21])
    u = axis_of(mode, world)
    anchor = [0.0, 0.0, 0.0]
    body = [0.0, 0.0, 0.0]
    c0 = ref.evaluate(rig, base, 0.0, world, chain_only=True)['outputs'][:3]
    w0 = to_world(world, c0)
    anchor = [w0[k] for k in range(3)]                  # the post passes through the first centre
    # The history is seeded as the Director seeds it on entry (sh-setup: the centre and
    # its velocity at hold_idle t = 0), so the first frames extrapolate too.
    cm = ref.evaluate(rig, base, -DT + 3.0, world, chain_only=True)['outputs'][:3]
    hist, worst = [cm, c0], 0.0
    for k in range(1, int(6 / DT) + 1):
        now = k * DT
        if len(hist) >= 1:
            c = hist[-1] if len(hist) < 2 else [2 * hist[-1][q] - hist[-2][q] for q in range(3)]
            w = [body[q] + to_world(world, c)[q] for q in range(3)]
            off = [anchor[q] - w[q] for q in range(3)]
            along = ref.dot(off, u)
            body = [body[q] + off[q] - along * u[q] for q in range(3)]
        r = ref.evaluate(rig, base, now, world, chain_only=True)
        c = r['outputs'][:3]
        hist.append(c)
        w = [body[q] + to_world(world, c)[q] for q in range(3)]
        off = [w[q] - anchor[q] for q in range(3)]
        along = ref.dot(off, u)
        worst = max(worst, math.sqrt(max(0.0, ref.dot(off, off) - along * along)))
    return worst


def render(rig, name, label, world, path, stats):
    block = block_for(name)
    r = ref.evaluate(rig, block, 0.0, world)
    pos = [to_world(world, p) for p in r['positions']]
    normals = [to_world(world, n) for n in r['normals']]
    F, L, T = r['angles']
    use = []
    for i, smp in enumerate(rig.c['samples']):
        ven, dor, lat, tw = smp['limits']
        use.append(max(F[i] / ven if F[i] > 0 else -F[i] / dor, abs(L[i]) / lat, abs(T[i]) / tw))
    img = Image.new('RGB', (SIZE, SIZE), (14, 34, 48))
    dr = ImageDraw.Draw(img)
    xs = [p[0] for p in pos]
    zs = [p[2] for p in pos]
    cx, cz = (min(xs) + max(xs)) / 2, (min(zs) + max(zs)) / 2
    scale = min(SCALE, (SIZE - 120) / (max(xs) - min(xs)), (SIZE - 120) / (max(zs) - min(zs)))

    def px(p):
        return (SIZE / 2 + (p[0] - cx) * scale, SIZE / 2 + 30 - (p[2] - cz) * scale)
    mode = int(block[21])
    if mode and block[24] > 0:
        centre = to_world(world, r['outputs'][:3])
        radius = block[23]
        if mode == 2:
            x0, y0 = px([centre[0] - radius, 0, cz + 2])
            x1, y1 = px([centre[0] + radius, 0, cz - 2])
            post = [(x0, y0), (x1, y1)]
            behind = True
        else:
            a, b = px([centre[0] - radius, 0, centre[2] + radius]), px([centre[0] + radius, 0, centre[2] - radius])
            post = [a, b]
            behind = False
        if behind:
            dr.rectangle(post, fill=(120, 120, 112))
    light = ref.normalize([-.4, -.8, .6])
    order = sorted(range(len(rig.faces)), key=lambda f: -sum(pos[i][1] for i in rig.faces[f]))
    for f in order:
        ia, ib, ic = rig.faces[f]
        n = normals[f]
        if n is None:
            continue
        if n[1] > .02:                                  # faces away from a camera looking +Y
            continue
        inf = rig.c['influences'][ia]
        shade = .35 + .65 * max(0.0, ref.dot(n, light))
        col = (232, 190, 64)
        if inf[0] == dc.ON_SAMPLE:
            u = use[inf[1]]
            col = (230, 70, 50) if u >= .97 else (int(232 - 40 * u), int(190 - 90 * u), int(64 + 20 * u))
        dr.polygon([px(pos[i]) for i in (ia, ib, ic)], fill=tuple(int(c * shade) for c in col))
    if mode and block[24] > 0 and not behind:
        dr.ellipse(post, fill=(120, 120, 112))
    if mode == 2 and block[24] > 0:
        # Inset: the coil from above, around the post's cross-section.
        box, k = 200, 700
        inset = Image.new('RGB', (box, box), (8, 22, 32))
        di = ImageDraw.Draw(inset)
        centre = to_world(world, r['outputs'][:3])
        q = lambda p: (box / 2 + (p[0] - centre[0]) * k, box / 2 - (p[1] - centre[1]) * k)  # noqa: E731
        rr = block[23] * k
        di.ellipse([box / 2 - rr, box / 2 - rr, box / 2 + rr, box / 2 + rr], fill=(120, 120, 112))
        joints = [to_world(world, j) for j in r['joints']]
        di.line([q(j) for j in joints[max(0, int(block[22]) - 5):]], fill=(232, 190, 64), width=3)
        di.text((8, 6), 'from above: lead-in and coil', fill=(200, 210, 216))
        di.rectangle([0, 0, box - 1, box - 1], outline=(70, 90, 100))
        img.paste(inset, (SIZE - box - 12, SIZE - box - 12))
    lines = [label, f"limit use {stats['max_limit_use']:.3f}   frame flips {stats['frame_flips']}"]
    if stats.get('wrap_centre_error_mm') is not None:
        lines.append(f"wrap {'vertical' if mode == 2 else 'horizontal'}, start {int(block[22])}, "
                     f"radius {block[23] / MM:.1f} mm; centre error {stats['wrap_centre_error_mm']:.3f} mm")
    for k, t in enumerate(lines):
        dr.text((16, 14 + 16 * k), t, fill=(230, 236, 240))
    img.save(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    rig = load_rig('f')
    result = {'rig': 'wflevels/aquarium_plants/seahorse_f_body.iff', 'rate_hz': 1 / DT, 'poses': {}}
    for file, name in POSES:
        _f, pitch, _wrap = ref.PRESETS[name]
        world = ref.world_rotation(pitch)
        block = block_for(name)
        final = ref.evaluate(rig, block, 0.0, world, chain_only=True)
        use, flipped, clamped = ease_in(rig, name, world)
        stats = {'max_limit_use': round(use, 4), 'frame_flips': flipped, 'clamped_frames': clamped,
                 'status': final['status'], 'pitch_deg': pitch,
                 'wrap': {'mode': int(block[21]), 'start': int(block[22]), 'radius_mm': round(block[23] / MM, 2),
                          'progress': block[24]}}
        if block[21] and block[24] > 0:
            stats['wrap_centre_error_mm'] = round(hold_trace(rig, name, world) / MM, 4)
        render(rig, name, f'{file}  ({name}, pitch {pitch} deg)', world, args.out / f'pose-{file}.png', stats)
        result['poses'][file] = stats
    grips = [p['wrap_centre_error_mm'] for p in result['poses'].values() if 'wrap_centre_error_mm' in p]
    result['max_limit_use'] = max(p['max_limit_use'] for p in result['poses'].values())
    result['frame_flips'] = sum(p['frame_flips'] for p in result['poses'].values())
    result['wrap_centre_error_mm'] = max(grips)
    result['pass'] = result['max_limit_use'] <= 1.0 and result['frame_flips'] == 0 and result['wrap_centre_error_mm'] <= .5
    (args.out / 'poses.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('max_limit_use', 'frame_flips', 'wrap_centre_error_mm', 'pass')}))


if __name__ == '__main__':
    main()
