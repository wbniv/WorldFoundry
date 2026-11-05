"""Render neutral and posed exported DFRM meshes for the refinement catalogue."""
import os
os.environ.setdefault('MPLCONFIGDIR', '/tmp/reef-matplotlib')
from pathlib import Path
import struct
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

root = Path('/home/will/WorldFoundry-wbniv')
model_dir = Path(os.environ.get('REEF_MODEL_DIR', root / 'wflevels/aquarium_thai_reef'))
sys.path.insert(0, str(root / 'wflevels/aquarium_tanks'))
sys.path.insert(0, str(root / 'wftools/wf_blender'))
import dfrm_chunk as dc
from dfrm_ref import Rig, evaluate

out = Path(__file__).parent
for name, key, angles, scales in [
    ('reef_boxfish', 'boxfish_fin_motion', [20, -20, 20, 20, -20], [1]*5),
    ('giantclam', 'clam_motion', [22, 22, 0], [1, 1, .35]),
    ('featherdusters', 'duster_motion', [0]*4, [.02]*4),
    ('flowerpotcoral', 'flowerpot_motion', [7,-7]*6, [1]*12),
    ('leathercoral', 'leather_motion', [4,0], [.85,1]),
]:
    data = (model_dir / (name + '.iff')).read_bytes()
    chunks, offset = {}, 8
    while offset < len(data):
        tag, size = struct.unpack_from('<4sI', data, offset)
        chunks[tag] = data[offset+8:offset+8+size]
        offset += 8 + ((size+3) & ~3)
    verts = [tuple(v/65536 for v in struct.unpack_from('<iii', chunks[b'VRTX'], i+12))
             for i in range(0, len(chunks[b'VRTX']), 24)]
    faces = [struct.unpack_from('<hhh', chunks[b'FACE'], i) for i in range(0, len(chunks[b'FACE']), 8)]
    rig = Rig(dc.decode(chunks[b'DFRM']), verts, faces)
    for label in ('before', 'after'):
        block = [0.] * (40 + len(angles)*4)
        for i, angle in enumerate(angles):
            block[40+4*i] = scales[i] if label == 'after' else 1
            block[43+4*i] = angle if label == 'after' else 0
        positions = evaluate(rig, block, 0)['positions']
        fig = plt.figure(figsize=(8, 6), facecolor='#102a3a')
        ax = fig.add_subplot(projection='3d', facecolor='#102a3a')
        polys = [[positions[i] for i in face] for face in faces]
        ax.add_collection3d(Poly3DCollection(polys, facecolor='#e4bf52' if name == 'reef_boxfish' else '#93cbd0',
                                              edgecolor='#375460', linewidth=.12))
        radius = max(.48, max(max(v[k] for v in verts)-min(v[k] for v in verts) for k in range(3))*.6)
        for setter, k in ((ax.set_xlim, 0), (ax.set_ylim, 1), (ax.set_zlim, 2)):
            lo, hi = min(v[k] for v in verts), max(v[k] for v in verts)
            mid = (lo+hi)/2
            setter(mid-radius, mid+radius)
        ax.set_box_aspect((1, 1, 1))
        ax.view_init(elev=22, azim=-65)
        ax.set_axis_off()
        fig.savefig(out / f'{key}-{label}.png', dpi=120, facecolor=fig.get_facecolor())
        plt.close(fig)
