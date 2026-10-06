"""Authored goby geometry and actual Forth locomotion; no desktop profiling."""
import math
import json
import re
import sys
from pathlib import Path
import pytest
from PIL import Image
from test_urchin_motion import binaries, zf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'wflevels/aquarium_tanks'))
import goby


def test_goby_geometry_and_rooted_membranes():
    models = [goby.body(), goby.fins()]
    assert sum(len(f)-2 for m in models for f in m.faces) < 1600
    for m in models:
        assert len(m.uvs) == len(m.vertices)
        assert all(0 <= u <= 1 and 0 <= v <= 1 for u,v in m.uvs)
        assert all(math.isfinite(p) for v in m.vertices for p in v)
        # Nondegenerate source triangles, including poles and root strips.
        for f in m.faces:
            for i in range(1,len(f)-1):
                a,b,c = [m.vertices[k] for k in (f[0],f[i],f[i+1])]
                ab,ac = [[q[j]-a[j] for j in range(3)] for q in (b,c)]
                cross = [ab[1]*ac[2]-ab[2]*ac[1], ab[2]*ac[0]-ab[0]*ac[2], ab[0]*ac[1]-ab[1]*ac[0]]
                # Engine normal construction must survive the fixed-point floor.
                assert math.sqrt(sum(x*x for x in cross)) > 6/65536
    assert sum(v == 0 for u,v in models[1].uvs) > 100


def test_textures_are_256_and_reproducible(tmp_path):
    goby.write_textures(tmp_path)
    before = [(tmp_path/p).read_bytes() for p in (goby.BODY_TEXTURE,goby.FIN_TEXTURE)]
    goby.write_textures(tmp_path)
    assert before == [(tmp_path/p).read_bytes() for p in (goby.BODY_TEXTURE,goby.FIN_TEXTURE)]
    for p in (goby.BODY_TEXTURE,goby.FIN_TEXTURE):
        im = Image.open(tmp_path/p)
        assert im.size == (256,256) and im.mode == 'RGB'
    r,g,b = Image.open(tmp_path/goby.BODY_TEXTURE).getpixel((174,101))
    assert b > g > r


def test_cooked_plant_scripts_compile(host, tmp_path):
    """Compile both actual exported scripts together, within the engine dictionary."""
    h = host
    mailbox = (ROOT/'wfsource/source/mailbox/mailbox.inc').read_text()
    constants = re.findall(r'MAILBOXENTRY\(\s*(\w+)\s*,\s*(\d+)\s*\)', mailbox)
    for name, value in constants:
        assert h.eval(f': INDEXOF_{name} {value} ;') == 'ok'
    for name, value in [('LEFT',1),('RIGHT',2),('UP',4),('DOWN',8),('A',16)]:
        assert h.eval(f': JOYSTICK_BUTTON_{name} {value} ;') == 'ok'
    # Published engine bridge names; these stubs are only compiled, never called.
    for name in ['read-actor-mailbox', 'write-actor-mailbox', 'property@',
                 'swim-deform', 'plant-register', 'plant-step']:
        assert h.eval(f': {name} 0 ;') == 'ok'
    lev = (ROOT/'wflevels/aquarium_plants/aquarium_plants.lev').read_text()
    scripts = re.findall(r"\{ 'NAME' \"Script\" \} \{ 'STR' (\"(?:\\.|[^\"\\])*\")", lev)
    assert len([s for s in scripts if 'Generated standalone' in s]) == 2
    for k, encoded in enumerate(scripts):
        source = json.loads(encoded)
        if 'Generated standalone' not in source:
            continue
        definitions = source[:source.rfind(';')+1]
        path = tmp_path/f'actor-{k}.fth'
        path.write_text(definitions)
        assert h.load(path) == 'ok'
    assert h.size() < 65536


@pytest.fixture(params=['float','fixed'])
def host(request,binaries):
    zf.BIN = binaries[request.param]
    h = zf.Host()
    assert h.eval(': INDEXOF_DELTA_TIME 790 ; : INDEXOF_INPUT 3015 ; '
                  ': INDEXOF_X_POS 3009 ; : INDEXOF_Z_POS 3011 ; '
                  ': INDEXOF_XSPEED 3020 ; : INDEXOF_YSPEED 3021 ; : INDEXOF_ZSPEED 3022 ; '
                  ': gb-floor .865 ; : gb-ceiling 4.2 ; : gb-limit 4.7 ;') == 'ok'
    assert h.load(ROOT/'wflevels/aquarium_tanks/goby_controller.fth') == 'ok'
    h.write(790,.05);h.write(3011,.865)
    yield h
    h.close()


def step(h,n=1):
    for _ in range(n):
        assert h.eval('gb-player-tick') == 'ok'
        for pos,vel in ((3009,3020),(3011,3022)):
            h.write(pos,h.read(pos)+h.read(vel)*.05)


def test_lift_swim_release_settle_graze(host):
    h = host
    step(h,20)
    assert h.read(1146) == 3 and h.read(3020) == h.read(3022) == 0
    h.write(1141,1);h.write(1142,1);step(h,30)
    assert h.read(3009) > .6 and h.read(3011) > 1.3
    assert h.read(1146) == 1
    h.write(1141,0);h.write(1142,0);step(h,160)
    assert abs(h.read(3011)-.865)<.003
    assert h.read(1146) == 3 and h.read(3022) == 0


def test_modal_and_long_frame_require_release(host):
    h = host
    h.write(1141,1);step(h,10)
    h.write(1144,1);step(h)
    assert h.read(3020) == h.read(3022) == 0
    h.write(1144,0);step(h,10)
    assert h.read(3020) == 0
    h.write(1141,0);step(h);h.write(1141,1);step(h,10)
    assert h.read(3020) > .3
    h.write(790,.5);step(h)
    assert h.read(3020) == h.read(3022) == 0


def test_glass_clamp_and_bounded_state(host):
    h = host
    h.write(3009,4.7);h.write(3011,4.2)
    h.write(1141,1);h.write(1142,1);step(h,100)
    assert abs(h.read(3009)-4.7)<.0001 and abs(h.read(3011)-4.2)<.0001
    assert h.read(3020) == h.read(3022) == 0
    h.write(1141,0);h.write(1142,0);step(h,800)
    assert h.read(1152) <= 1.20001 and 0 <= h.read(1153) < 1
