#!/usr/bin/env python3
"""Read committed seahorse chunks for the GPU proposal; no asset conversion.

Run from the repository root. This checks rest geometry and palette capacity,
not posed winding, intended viewing side or GPU rendering.
"""
import argparse
from collections import Counter
import hashlib
import json
import struct
import subprocess


def require(ok, message):
    if not ok:
        raise ValueError(message)


def inspect(data):
    require(data[:4] == b'MODL', 'expected a MODL root')
    end = 8 + struct.unpack_from('<I', data, 4)[0]
    require(end == len(data), 'root size does not match file')
    chunks, offset = {}, 8
    while offset < end:
        require(offset + 8 <= end, 'truncated chunk header')
        tag, size = struct.unpack_from('<4sI', data, offset)
        start, stop = offset + 8, offset + 8 + size
        require(stop <= end and tag not in chunks, 'truncated or duplicate chunk')
        chunks[tag] = data[start:stop]
        offset = (stop + 3) & ~3
    require(offset == end, 'chunk alignment exceeds root')
    vertices, faces, rig = (chunks[tag] for tag in (b'VRTX', b'FACE', b'DFRM'))
    require(len(vertices) % 24 == 0 and len(faces) % 8 == 0, 'invalid VRTX/FACE stride')
    positions = [tuple(x / 65536 for x in row[3:]) for row in struct.iter_unpack('<iiIiii', vertices)]
    triangles = list(struct.iter_unpack('<hhhh', faces))
    require(all(0 <= i < len(positions) for face in triangles for i in face[:3]), 'invalid vertex index')
    require(len(chunks[b'MATL']) % 264 == 0, 'invalid material stride')
    flags = [struct.unpack_from('<I', chunks[b'MATL'], i)[0] for i in range(0, len(chunks[b'MATL']), 264)]
    require(all(0 <= f[3] < len(flags) for f in triangles), 'invalid material index')
    areas = []
    for a, b, c, _material in triangles:
        u = [positions[b][k] - positions[a][k] for k in range(3)]
        v = [positions[c][k] - positions[a][k] for k in range(3)]
        cross = [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]]
        areas.append(sum(x*x for x in cross) ** .5)
    version, reserved, curves, samples, transforms, influences, clips, frames = struct.unpack_from('<8I', rig)
    require(version == 1 and reserved == 0 and curves == 1, 'unexpected DFRM header')
    require(influences == len(positions), 'DFRM influence count mismatch')
    first = 32 + 52*curves + 16*samples + 28*transforms
    stride = 3*samples + transforms
    expected = first + 16*influences + 16*clips + ((2*stride*frames + 3) & ~3)
    require(len(rig) == expected, 'DFRM chunk size mismatch')
    bindings = [struct.unpack_from('<BBHiii', rig, first + 16*i) for i in range(influences)]
    require(all(k == 0 or k == 1 and j < samples or k == 2 and j < transforms and 0 <= a <= 65536
                for k, _pad, j, a, _b, _c in bindings), 'invalid DFRM binding')
    weighted = sorted({(j, a) for k, _pad, j, a, _b, _c in bindings if k == 2})
    groups = [(k, j if k else 0, a if k == 2 else 0) for k, _pad, j, a, _b, _c in bindings]
    opacities = [1.0] * len(flags)
    if b'OPAC' in chunks:
        opacity = chunks[b'OPAC']
        require(len(opacity) == 8 + 4*len(flags), 'invalid opacity stride')
        require(struct.unpack_from('<II', opacity) == (1, len(flags)), 'invalid opacity header')
        opacities = [x[0]/65536 for x in struct.iter_unpack('<I', opacity[8:])]
        require(all(0 <= a <= 1 for a in opacities), 'invalid opacity')
    return dict(vertices=len(positions), triangles=len(triangles),
                material_flags=flags, material_face_counts=dict(Counter(f[3] for f in triangles)),
                material_opacities=opacities,
                double_sided_faces=sum(bool(flags[f[3]] & 8) for f in triangles),
                alpha_cutout_faces=sum(bool(flags[f[3]] & 16) for f in triangles),
                native_handle_bytes=len(chunks.get(b'HNDL', b'')),
                degenerate_rest_faces=sum(a == 0 for a in areas),
                minimum_rest_double_area_model_units_squared=min(areas),
                samples=samples, transforms=transforms, clip_frames=frames,
                transform_angle_weight_groups=[dict(transform=j, weight=a/65536) for j, a in weighted],
                proposed_palette_entries=1 + samples + len(weighted),
                faces_spanning_bindings=sum(len({groups[i] for i in f[:3]}) > 1 for f in triangles))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', default='HEAD')
    args = parser.parse_args()
    revision = subprocess.check_output(['git', 'rev-parse', args.revision], text=True).strip()
    source_review = 'docs/diagnostics/blender-normal-convention/integration-seahorse-source-review.json'
    review = {r['path']: r for r in json.loads(subprocess.check_output(['git', 'show', f'{revision}:{source_review}']))}
    models = []
    for sex in ('f', 'm'):
        path = f'wflevels/aquarium_plants/seahorse_{sex}_body.iff'
        data = subprocess.check_output(['git', 'show', f'{revision}:{path}'])
        digest = hashlib.sha256(data).hexdigest()
        require(digest == review[path]['current_export_sha256'], 'asset differs from reviewed export')
        models.append(dict(path=path, sha256=digest, matches_reviewed_export=True, **inspect(data)))
    print(json.dumps(dict(revision=revision, scope='Rest geometry and palette preflight only; not posed winding or GPU parity.',
                          source_review=source_review,
                          models=models), indent=2))


if __name__ == '__main__':
    main()
