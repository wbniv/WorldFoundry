"""Geometry and reference-motion invariants before runtime integration."""
import importlib.util
import math
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('anemone_model',Path(__file__).resolve().parents[1]/'wflevels/aquarium/anemone_model.py')
import sys
M=importlib.util.module_from_spec(spec);sys.modules[spec.name]=M;spec.loader.exec_module(M)

@pytest.mark.parametrize('count',[24,48,72])
def test_density_trials_have_valid_geometry(count):
    m=M.geometry(count)
    assert len(m.tentacles)==count
    assert len(m.vertices)==len(m.uvs)==len(m.rig)
    for f in m.faces:
        assert len(set(f))==len(f)
        assert all(0<=i<len(m.vertices) for i in f)
        a,b,c=[m.vertices[i] for i in f[:3]]
        u=[b[i]-a[i] for i in range(3)];v=[c[i]-a[i] for i in range(3)]
        cross=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
        assert sum(x*x for x in cross)>1e-14
    assert all(0<=q<=1 for uv in m.uvs for q in uv)
    assert all(math.isfinite(q) for p in m.vertices for q in p)


def test_seed_is_repeatable_but_changes_crown():
    assert M.geometry().vertices==M.geometry().vertices
    assert M.geometry(seed=18).vertices!=M.geometry().vertices

@pytest.mark.parametrize('withdraw',[0,.5,1])
def test_tentacle_roots_follow_disc_and_do_not_sway(withdraw):
    m=M.geometry()
    for r in m.rig:
        if r['region']!=1 or r['u']!=0:continue
        root=r['root']
        expected=M.pose_vertex(root,dict(region=0),withdraw=withdraw)
        for phase in [0,.25,.5,.75]:
            assert M.pose_vertex(root,r,phase=phase,withdraw=withdraw)==pytest.approx(expected)


def test_foot_and_texture_coordinates_are_preserved():
    m=M.geometry();uvs=list(m.uvs)
    for p,r in zip(m.vertices,m.rig):
        posed=M.pose_vertex(p,r,phase=.25,withdraw=.8)
        if r['region']==0 and p[2]==0:assert posed==p
    assert m.uvs==uvs


def test_pose_rejects_nan_and_clamps_withdrawal():
    r=dict(region=0)
    with pytest.raises(ValueError):M.pose_vertex((0,0,.3),r,phase=float('nan'))
    assert M.pose_vertex((0,0,.3),r,withdraw=3)==M.pose_vertex((0,0,.3),r,withdraw=1)


def test_surface_texture_is_pigmented_and_256(tmp_path):
    image=M.write_textures(tmp_path)
    assert image.size==(256,256)
    pixels=[image.getpixel((x,y)) for y in range(256) for x in range(256)]
    assert len(set(pixels))>1000
    assert all(a==255 for _,_,_,a in pixels)
    assert max(sum(p[:3])/3 for p in pixels)<210
