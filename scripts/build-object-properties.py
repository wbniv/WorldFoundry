#!/usr/bin/env python3
"""Cook OAD-derived object properties; append an optional sector-aligned catalog.

The Rust normalizer used by Blender owns schema semantics. Bindings add IDs,
exposure/effects and initial instance values; labels/ranges stay in OAD.
"""
import argparse
import json
from pathlib import Path
import struct
import subprocess

ROOT=Path(__file__).resolve().parents[1]
KINDS={'Int':0,'Float':1,'Enum':2,'Str':3,'Bool':4,'Section':5,'Group':6,'GroupEnd':7,'FileRef':8,'ObjRef':8,'Annotation':8}

def string(value):
    b=str(value).encode('utf8')
    return struct.pack('<I',len(b))+b

def catalog(oad,bindings,actor):
    tool=ROOT/'wftools/wf_attr_edit/target/release/catalog'
    schema=json.loads(subprocess.check_output([tool,str(oad)],text=True))
    out=bytearray(b'RP01'+struct.pack('<II',1,actor))
    out+=string(schema['name'])+string(bindings.get('title',schema['name']))
    fields=[];used=set();seen=set()
    for f in schema['fields']:
        if f['kind']=='Skip' or f['show']==6:continue
        setting=bindings.get('fields',{}).get(f['key'])
        kind=KINDS.get(f['kind'],8)
        structural=kind in (5,6,7)
        if not structural and setting is None:continue
        setting=setting or {}
        field_id=int(setting.get('id',0))
        if not structural:
            if not 1<=field_id<=32767 or field_id in used:raise ValueError('Invalid/duplicate field ID')
            used.add(field_id);seen.add(f['key'])
        default=str(f['default']/f['scale']) if f['kind']=='Float' else str(f['default'])
        if f['kind']=='Str':default=''
        f=dict(f,id=field_id,kind_id=kind,readonly=kind==8 or setting.get('readonly',False),
               rule=1 if setting.get('rule')=='uint32-decimal' else 0,
               max_length=setting.get('max_length',f['max'] if f['max']>0 else 256),
               initial=str(setting.get('initial',default)))
        fields.append(f)
    if seen!=set(bindings.get('fields',{})):raise ValueError('Bindings refer to missing/hidden OAD fields')
    for action in bindings.get('actions',[]):
        i=action['id']
        if i in used:raise ValueError('Duplicate action ID')
        used.add(i)
        fields.append(dict(id=i,kind_id=10 if action['action']=='spacer' else 9,show=0,readonly=False,rule=0,
            min=0,max=0,scale=0,width=0,max_length=0,key=action['action'],label=action['label'],help='',group='',choices='',initial=''))
    out+=struct.pack('<I',len(fields))
    for f in fields:
        out+=struct.pack('<IBBBBiiIII',f['id'],f['kind_id'],f['show'],int(f['readonly']),f['rule'],f['min'],f['max'],f['scale'],f['width'],f['max_length'])
        for k in ('key','label','help','group','choices','initial'):out+=string(f[k])
    return bytes(out)

def attach(level,payload):
    d=bytearray(level)
    if len(d)<4096 or d[2048:2052]!=b'RAM\0':raise ValueError('Expected a standalone level with RAM at sector one')
    old_size=struct.unpack_from('<I',d,2052)[0]
    ram_end=2056+old_size
    if d[ram_end:ram_end+4]!=b'ALGN':raise ValueError('RAM padding absent')
    # Rebuilding a level is normal; replacing our existing catalog is idempotent.
    if old_size>=48 and d[ram_end-12:ram_end-8]==b'RPRP':
        offset,size=struct.unpack_from('<II',d,ram_end-8)
        d=d[:2048+offset]
        chunk=b'RPRP'+struct.pack('<I',len(payload))+payload
        chunk+=bytes((-len(chunk))%2048)
        struct.pack_into('<II',d,ram_end-8,len(d)-2048,len(chunk))
        d.extend(chunk);struct.pack_into('<I',d,4,len(d)-8)
        return bytes(d)
    pad=struct.unpack_from('<I',d,ram_end+4)[0]
    if pad<12:raise ValueError('Insufficient RAM padding')
    catalog_offset=len(d)-2048
    chunk=b'RPRP'+struct.pack('<I',len(payload))+payload
    chunk+=bytes((-len(chunk))%2048)
    d.extend(chunk)
    struct.pack_into('<I',d,2052,old_size+12)
    d[ram_end:ram_end+20]=b'RPRP'+struct.pack('<II',catalog_offset,len(chunk))+b'ALGN'+struct.pack('<I',pad-12)
    struct.pack_into('<I',d,4,len(d)-8)
    return bytes(d)

def main():
    p=argparse.ArgumentParser();p.add_argument('--oad',type=Path,required=True);p.add_argument('--bindings',type=Path,required=True)
    p.add_argument('--actor-map',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--level',type=Path);p.add_argument('--include',type=Path)
    a=p.parse_args();b=json.loads(a.bindings.read_text());mapping=json.loads(a.actor_map.read_text())['indices']
    data=catalog(a.oad,b,mapping[b['owner']]);a.out.write_bytes(data)
    if a.level:a.level.write_bytes(attach(a.level.read_bytes(),data))
    if a.include:a.include.write_text('// Generated from OAD; do not hand-edit.\n'+','.join(str(v) for v in data)+'\n')
    print(f'Property catalog: {a.out} ({len(data)} bytes)')

if __name__=='__main__':main()
