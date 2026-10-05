"""Atlas/material correctness and valid geometry for the cooked urchin assets."""
import hashlib
import json
from pathlib import Path
import struct
import sys
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'wflevels/aquarium_tanks'))
from urchin import urchin,tube_foot,write_texture,spine_specs,spine_mesh,PIVOT_SPINES

def chunks(path):
    data=path.read_bytes();out={};offset=8
    while offset<len(data):
        tag=data[offset:offset+4];size=struct.unpack_from('<I',data,offset+4)[0]
        out[tag]=data[offset+8:offset+8+size];offset+=8+(size+3)//4*4
    return out

def test_atlas_is_deterministic_colored_and_256_square(tmp_path):
    write_texture(tmp_path);first=hashlib.sha256((tmp_path/'urchin_surfaces.tga').read_bytes()).digest()
    write_texture(tmp_path);assert hashlib.sha256((tmp_path/'urchin_surfaces.tga').read_bytes()).digest()==first
    image=Image.open(tmp_path/'urchin_surfaces.tga');assert image.size==(256,256)
    body=image.getpixel((60,80));foot=image.getpixel((180,220))
    assert body[2]>body[0]>body[1] and min(foot)>120
    pixels=image.tobytes()
    assert len(set(pixels[i:i+3] for i in range(0,len(pixels),3)))>1000

def test_texture_coordinates_and_geometry_budget():
    models=[urchin(),tube_foot(),*[spine_mesh(k) for k in PIVOT_SPINES]]
    assert len(spine_specs())==101
    assert 2000<=sum(len(f)-2 for f in models[0].faces)+8*sum(len(f)-2 for f in models[1].faces)+sum(len(f)-2 for m in models[2:] for f in m.faces)<=4000
    for mesh in models:
        assert len(mesh.uvs)==len(mesh.vertices)
        assert all(0<=u<=1 and 0<=v<=1 for u,v in mesh.uvs)

def test_cooked_materials_share_permanent_atlas_and_foot_opacity():
    here=ROOT/'wflevels/aquarium_plants'
    body,foot=[chunks(here/name) for name in ('sea_urchin.iff','urchin_tube_foot.iff')]
    spines=[chunks(here/f'urchin_spine_{k}.iff') for k in range(8)]
    for mesh in (body,foot,*spines):
        flags,color=struct.unpack_from('<iI',mesh[b'MATL'])
        assert flags&6==6 and color==0xffffff
        assert mesh[b'MATL'][8:].split(b'\0',1)[0]==b'urchin_surfaces.tga'
    assert b'OPAC' not in body and all(b'OPAC' not in mesh for mesh in spines)
    version,count,opacity=struct.unpack('<III',foot[b'OPAC'])
    assert (version,count)==(1,1) and abs(opacity/65536-.78)<.00002
    ini=(here/'aquarium_plants.ini').read_text()
    perm=next(line for line in ini.splitlines() if line.startswith('Perm ='))
    assert 'sea_urchin.iff' in perm and 'urchin_tube_foot.iff' in perm
    assert all(f'urchin_spine_{k}.iff' in perm for k in range(8))
    assert Image.open(here/'Room0.tga').size==(256,256)
