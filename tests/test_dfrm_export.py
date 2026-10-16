"""DFRM v1 export round trip, and the reference maths against the tail-rig mockup.

The exporter (wftools/wf_blender/export_level.py, ``wf_dfrm_rig``) gathers
bones, weights and sampled actions from Blender and hands them to
dfrm_chunk.build_chunk; these tests build the same inputs for a synthetic
35-ring tail without Blender. Clip frames go through the exporter's own path:
a joint rotation matrix (what Blender's matrix_basis gives) -> decompose ->
int16 centidegrees. docs/plans/2026-10-16-saltwater-seahorses.md, E1 and E6.
"""
from __future__ import annotations

import json
import math
import random
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'wftools' / 'wf_blender'))
sys.path.insert(0, str(ROOT / 'wflevels' / 'aquarium_tanks'))
import dfrm_chunk as dc  # noqa: E402
import dfrm_ref  # noqa: E402

N = 35
CHAIN = [f'tail_{i:02d}' for i in range(N)]
XF = ['head', 'eye_l', 'eye_r']


def synthetic_tail():
    """35 bones hanging down -Z from the origin, ventral +X; 8 vertices per ring.

    Each ring vertex is weighted 0.7 to its own bone and 0.3 to a neighbour, so
    the binding must pick the max-weight bone. Head vertices blend 'head' with
    tail_34; one vertex has no rig group and one has no group at all.
    """
    d, v = (0.0, 0.0, -1.0), (1.0, 0.0, 0.0)
    lengths = [dfrm_ref.LEN[i] * dfrm_ref.MM for i in range(N)]
    chain, positions, weights, expected = [], [], [], []
    z = 0.0
    for i in range(N):
        head, tail = (0.0, 0.0, z), (0.0, 0.0, z - lengths[i])
        chain.append({'head': head, 'tail': tail, 'z_axis': v, 'limits': dfrm_ref.LIM(i)})
        half = dfrm_ref.WID[i] / 2 * dfrm_ref.MM
        for end in (0.0, 1.15 * lengths[i]):
            for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1)):
                positions.append((sx * half, sy * half, z - end))
                other = CHAIN[i + 1] if i + 1 < N else CHAIN[i - 1]
                weights.append({CHAIN[i]: 0.7, other: 0.3})
                expected.append((dc.ON_SAMPLE, i))
        z -= lengths[i]
    for w in (0.8, 0.5):
        positions.append((0.05, 0.0, 0.6 + w))
        weights.append({'head': w, CHAIN[-1]: 0.1})
        expected.append((dc.ON_TRANSFORM, 0))
    positions.append((0.2, 0.0, 0.3)); weights.append({'pectoral': 1.0}); expected.append((dc.NONE, 0))
    positions.append((0.2, 0.1, 0.3)); weights.append({}); expected.append((dc.NONE, 0))
    transforms = [{'pivot': (0.0, 0.0, 0.6), 'axis': (0.0, 1.0, 0.0), 'lo': -30.0, 'hi': 30.0},
                  {'pivot': (0.03, 0.02, 0.7), 'axis': (0.0, 0.0, 1.0), 'lo': -40.0, 'hi': 40.0},
                  {'pivot': (0.03, -0.02, 0.7), 'axis': (0.0, 0.0, 1.0), 'lo': -40.0, 'hi': 40.0}]
    return chain, positions, weights, expected, transforms


def authored_clips():
    """Known joint angles, and the frames the exporter derives from their matrices."""
    rng = random.Random(7)
    truth, clips = {}, []
    for name, loop, count in (('curl', False, 12), ('sway', True, 30)):
        rows, frames = [], []
        for k in range(count):
            row = []
            for i in range(N):
                ven, dor, lat, tw = dfrm_ref.LIM(i)
                row += [rng.uniform(-dor, ven), rng.uniform(-lat, lat), rng.uniform(-tw, tw)]
            row += [rng.uniform(-30, 30), rng.uniform(-40, 40), rng.uniform(-40, 40)]
            rows.append(row)
            frame = []
            for i in range(N):
                frame += dc.decompose(dc.compose(*row[3 * i:3 * i + 3]))
            frame += [dc.angle_about_x(dc.rx(math.radians(a))) for a in row[3 * N:]]
            frames.append(frame)
        truth[name] = rows
        clips.append({'name': name, 'loop': loop, 'frames': frames})
    return truth, clips


@pytest.fixture(scope='module')
def exported():
    chain, positions, weights, expected, transforms = synthetic_tail()
    bindings = dc.bind_vertices(weights, CHAIN, XF)
    truth, clips = authored_clips()
    payload = dc.build_chunk(chain, positions, bindings, transforms, clips)
    return {'payload': payload, 'decoded': dc.decode(payload), 'positions': positions, 'expected': expected,
            'truth': truth, 'chain': chain}


def test_angles_round_trip_within_a_hundredth_of_a_degree(exported):
    dec = exported['decoded']
    worst = 0.0
    for clip, name in zip(dec['clips'], ('curl', 'sway')):
        assert clip['hash'] == dc.fnv1a(name) and clip['fps'] == dc.FPS
        for k, row in enumerate(exported['truth'][name]):
            got = dec['frames'][clip['first'] + k]
            worst = max(worst, max(abs(a - b) for a, b in zip(got, row)))
    assert worst < 0.01, worst
    assert [c['loop'] for c in dec['clips']] == [False, True]
    assert [c['frames'] for c in dec['clips']] == [12, 30]


def test_influence_count_equals_vertex_count_and_binds_max_weight(exported):
    dec = exported['decoded']
    assert len(dec['influences']) == len(exported['positions'])
    assert [(k, i) for k, i, *_ in dec['influences']] == exported['expected']
    head = [inf for inf in dec['influences'] if inf[0] == dc.ON_TRANSFORM]
    assert [round(inf[2], 4) for inf in head] == [0.8, 0.5]


def test_offsets_put_every_ring_vertex_back_at_rest(exported):
    dec = exported['decoded']
    cv = dec['curves'][0]
    joints = [cv['root']]
    for s in dec['samples']:
        joints.append([joints[-1][k] + cv['d'][k] * s['length'] for k in range(3)])
    s_axis = dc._cross(cv['v'], cv['d'])
    for p, (kind, i, a, b, c) in zip(exported['positions'], dec['influences']):
        if kind == dc.ON_SAMPLE:
            q = [joints[i][k] + a * cv['d'][k] + b * cv['v'][k] + c * s_axis[k] for k in range(3)]
            assert max(abs(x - y) for x, y in zip(p, q)) < 5e-5


def test_header_tables_and_limits(exported):
    dec, payload = exported['decoded'], exported['payload']
    assert dec['version'] == 1 and dec['flags'] == 0
    cv = dec['curves'][0]
    assert cv['count'] == N and cv['knots'] == [0, 6, 12, 18, 24, 30, 34]
    stride = 3 * N + 3
    assert len(payload) == 32 + 52 + 16 * N + 28 * 3 + 16 * len(exported['positions']) + 16 * 2 + \
        (2 * stride * 42 + 3) // 4 * 4
    for i, s in enumerate(dec['samples']):
        assert s['limits'] == [round(x, 2) for x in dfrm_ref.LIM(i)]
        assert abs(s['length'] - dfrm_ref.LEN[i] * dfrm_ref.MM) < 2e-5
        assert abs(s['half_width'] - dfrm_ref.WID[i] / 2 * dfrm_ref.MM) < 2e-5   # widest bound vertex


def test_decompose_inverts_the_engine_joint_rotation():
    rng = random.Random(3)
    for _ in range(2000):
        f, lat, t = rng.uniform(-80, 80), rng.uniform(-80, 80), rng.uniform(-80, 80)
        assert max(abs(a - b) for a, b in zip(dc.decompose(dc.compose(f, lat, t)), (f, lat, t))) < 1e-9


def test_joint_rotation_matches_the_engine_fk_convention():
    """compose() applied to the bone axes equals dfrm_ref's rot() sequence (the engine's FK)."""
    f, lat, t = 23.0, -11.0, 7.0
    m = dc.compose(f, lat, t)
    d, v, s = [0, 1, 0], [0, 0, 1], [-1, 0, 0]          # bone Y, Z, -X
    d, v = dfrm_ref.rot(d, v, math.radians(f))
    d, s = dfrm_ref.rot(d, s, math.radians(lat))
    v, s = dfrm_ref.rot(v, s, math.radians(t))
    col = lambda j: [m[0][j], m[1][j], m[2][j]]          # noqa: E731
    for got, want in ((col(1), d), (col(2), v), ([-x for x in col(0)], s)):
        assert max(abs(a - b) for a, b in zip(got, want)) < 1e-12


def test_bent_bind_pose_is_rejected():
    chain, positions, weights, _expected, transforms = synthetic_tail()
    chain[10] = dict(chain[10], z_axis=(0.9, 0.1, 0.0))
    with pytest.raises(ValueError, match='bind pose must be straight'):
        dc.build_chunk(chain, positions, dc.bind_vertices(weights, CHAIN, XF), transforms)


def test_angle_outside_int16_centidegrees_is_rejected():
    chain, positions, weights, _expected, transforms = synthetic_tail()
    frame = [400.0] + [0.0] * (3 * N + 2)
    with pytest.raises(ValueError, match='centidegrees'):
        dc.build_chunk(chain, positions, dc.bind_vertices(weights, CHAIN, XF), transforms,
                       [{'name': 'bad', 'loop': False, 'frames': [frame]}])


MOCKUP = ROOT / 'docs' / 'plans' / '2026-10-16-saltwater-seahorses' / 'tail-rig.html'


@pytest.mark.skipif(shutil.which('node') is None, reason='node is not installed')
def test_reference_expansion_matches_the_mockup_javascript():
    """dfrm_ref's expansion and FK against tail-rig.html's own interp/expand/fk."""
    html = MOCKUP.read_text()
    js = html[html.index('const N = 35'):html.index('// ── Body silhouette')]
    js += '''
const out = {};
for (const k of %s) { const P = PRESETS[k];
  const st = {f: P.f, l: zero7(), t: zero7(), pitch: P.pitch, mode: P.wrap.mode, start: P.wrap.start, r: P.wrap.r, p: P.wrap.p};
  const A = expand(st, {}); const K = fk(A, P.pitch); out[k] = {F: A.F, L: A.L, T: A.T, P: K.P}; }
console.log(JSON.stringify(out));
''' % json.dumps(list(dfrm_ref.PRESETS))
    mock = json.loads(subprocess.run(['node', '-e', js], check=True, capture_output=True, text=True).stdout)
    for name, (_f, pitch, _wrap) in dfrm_ref.PRESETS.items():
        pos, faces, payload = dfrm_ref.strand(pitch=pitch)
        rig = dfrm_ref.Rig(dc.decode(payload), dfrm_ref.quantized(pos), faces)
        ref = dfrm_ref.evaluate(rig, dfrm_ref.preset_block(name), 0.0)
        for got, want in zip(ref['angles'], (mock[name]['F'], mock[name]['L'], mock[name]['T'])):
            assert max(abs(a - b) for a, b in zip(got, want)) < 0.05, name      # degrees; data is 16.16
        joints_mm = [[x / dfrm_ref.MM for x in j] for j in ref['joints']]
        assert max(abs(a - b) for j, m in zip(joints_mm, mock[name]['P']) for a, b in zip(j, m)) < 0.1, name
