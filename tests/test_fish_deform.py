"""Exercise the mesh wave independently of rendering and actor placement."""
from pathlib import Path
import itertools
import math
import subprocess
import sys


def test_wave_preserves_head_and_rest_pose_without_accumulation(tmp_path):
    root = Path(__file__).resolve().parents[1]
    source = tmp_path / 'wave.cc'
    source.write_text(r'''
#include "wfsource/source/renderassets/fish_deform.h"
#include <cassert>
#include <cmath>
int main() {
    using wf_render::FishWaveWeight;
    auto head = FishWaveWeight::make(1, .1f, -1, 1);
    auto tail = FishWaveWeight::make(-1, .1f, -1, 1);
    auto point = FishWaveWeight::make(-.4f, .2f, -1, 1);
    for (int frame=0; frame<10000; ++frame) {
        float phase=frame*.03f, s=std::sin(phase), c=std::cos(phase);
        assert(head.deform(s,c,.08f)==.1f);
        assert(tail.deform(s,c,0)==.1f);
        assert(std::abs(tail.deform(s,c,.08f)-.1f)<=.080001f);
        assert(std::abs(point.deform(s,c,.08f)-.2f)<.024f);
    }
    assert(std::abs(tail.deform(1,0,.08f)-.02f)<.00001f);
    assert(std::abs(tail.deform(-1,0,.08f)-.18f)<.00001f);
    assert(point.y==.2f && tail.y==.1f);
    assert(FishWaveWeight::make(1,.3f,1,1).deform(1,0,.08f)==.3f);
}
''')
    binary = tmp_path / 'wave'
    subprocess.run(['c++', '-std=c++11', '-I', str(root), str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)


def test_exported_mesh_has_no_polygons_below_engine_normalisation_limit():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'wflevels/aquarium'))
    import tiger_barb
    vertices, faces = tiger_barb.geometry()
    # Quantise as the level exporter does, and cover both possible quad diagonals.
    vertices = [tuple(round(x*65536)/65536 for x in p) for p in vertices]
    for face in faces:
        for a, b, c in itertools.combinations(face, 3):
            p = [vertices[b][i]-vertices[a][i] for i in range(3)]
            q = [vertices[c][i]-vertices[a][i] for i in range(3)]
            cross = [p[(i+1)%3]*q[(i+2)%3]-p[(i+2)%3]*q[(i+1)%3] for i in range(3)]
            assert math.sqrt(sum(x*x for x in cross)) > 4/65536


def test_body_uvs_keep_the_mesh_closed_in_the_cutout_texture():
    from PIL import Image
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'wflevels/aquarium'))
    import tiger_barb as tb
    im = Image.open(root / 'wflevels/aquarium/art/tiger-barb-source.png')
    vertices, faces = tb.geometry()
    for face in faces:
        if max(face) >= tb.BODY_VERTEX_COUNT:
            continue
        for tri in itertools.combinations(face, 3):
            for a in range(9):
                for b in range(9-a):
                    weights = (a/8, b/8, (8-a-b)/8)
                    x = sum(vertices[i][0]*w for i,w in zip(tri,weights))
                    z = sum(vertices[i][2]*w for i,w in zip(tri,weights))
                    u,v=tb.body_uv(x,z)
                    assert im.getpixel((int(u*im.width),int((1-v)*im.height)))[3] >= 128, (u,v,tri,weights)


def test_body_faces_point_outward_and_each_fin_has_two_sides():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'wflevels/aquarium'))
    import tiger_barb as tb
    vertices, faces = tb.geometry()
    for face in faces:
        if max(face) >= tb.BODY_VERTEX_COUNT:
            assert tuple(reversed(face)) in faces
            continue
        a,b,c = [vertices[i] for i in face[:3]]
        p=[b[i]-a[i] for i in range(3)]; q=[c[i]-a[i] for i in range(3)]
        normal=[p[(i+1)%3]*q[(i+2)%3]-p[(i+2)%3]*q[(i+1)%3] for i in range(3)]
        centre=[sum(vertices[v][i] for v in face)/len(face) for i in range(3)]
        if len(face)==3:  # planar end cap
            assert normal[0]*centre[0] > 0
        else:
            assert normal[1]*centre[1]+normal[2]*centre[2] > 0
