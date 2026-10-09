"""Cook bounded plant fixtures into existing level/CD catalogs, preserving assets."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
HERE=ROOT/'wflevels/aquarium_plants'
MARKER=b'PLANTS settings-source=%s seed=%u water=%s age='
FIELDS={'seed':'Seed','water':'Water type','age':'Initial age','speed':'Growth speed',
        'textures':'Textures','sway':'Sway','random_entry':'Random seed on entry'}

def validate(options):
    if set(options)-set(FIELDS):raise ValueError('Unknown plant configuration key')
    result=dict(seed=0,water='freshwater',age=0,speed=3,textures=True,sway=True,random_entry=True)
    result.update(options)
    for key,maximum in [('seed',4294967295),('speed',6)]:
        if type(result[key]) is not int or not 0<=result[key]<=maximum:raise ValueError('Invalid '+key)
    if type(result['age']) not in (int,float) or not math.isfinite(result['age']) or not 0<=result['age']<=240:raise ValueError('Invalid age')
    if result['water'] not in ('freshwater','saltwater'):raise ValueError('Invalid water')
    for key in ['textures','sway','random_entry']:
        if type(result[key]) is not bool:raise ValueError('Invalid '+key)
    # Providing a seed is deterministic unless random entry is explicitly chosen.
    if 'seed' in options and 'random_entry' not in options:result['random_entry']=False
    return result

def records(payload):
    if len(payload)<8 or payload[:4]!=b'RP01':raise ValueError('Invalid property catalog')
    position=8;count=struct.unpack_from('<I',payload,4)[0]
    if count>4096:raise ValueError('Too many catalog owners')
    def take(n):
        nonlocal position
        if n<0 or position+n>len(payload):raise ValueError('Truncated property catalog')
        value=payload[position:position+n];position+=n;return value
    def integer():return struct.unpack('<I',take(4))[0]
    def text():
        length=integer()
        if length>65536:raise ValueError('Oversized property string')
        return take(length).decode('utf8')
    result=[]
    for _ in range(count):
        start=position;actor=integer();schema=text();text();field_count=integer()
        if field_count>16384:raise ValueError('Too many fields')
        for _ in range(field_count):
            take(28)
            for _ in range(6):text()
        result.append((actor,schema,payload[start:position]))
    if position!=len(payload):raise ValueError('Trailing catalog bytes')
    return result

def catalog_payload(level):
    if len(level)<4096 or level[2048:2052]!=b'RAM\0':raise ValueError('Expected standalone RAM at sector one')
    ram_size=struct.unpack_from('<I',level,2052)[0];locator=2056+ram_size-12
    if locator<2056 or locator+12>len(level):raise ValueError('Invalid RAM size')
    if level[locator:locator+4]!=b'RPRP':return None
    offset,size=struct.unpack_from('<II',level,locator+4);start=2048+offset
    if offset<2048 or offset%2048 or size<8 or size%2048 or start+size>len(level) or level[start:start+4]!=b'RPRP':raise ValueError('Invalid catalog locator')
    length=struct.unpack_from('<I',level,start+4)[0]
    if length>size-8:raise ValueError('Invalid catalog length')
    return level[start+8:start+8+length]

def configure_level(level,options):
    options=validate(options)
    existing=catalog_payload(level);owners=records(existing) if existing else []
    matches=[a for a,s,_ in owners if s=='PlantedTankSettings']
    if len(matches)>1:raise ValueError('Ambiguous planted tank owner')
    actor=matches[0] if matches else json.loads((HERE/'actor-map.json').read_text())['indices']['Director']
    bindings=json.loads((HERE/'settings-bindings.json').read_text())
    for key,value in options.items():
        if key=='water':value=int(value=='saltwater')
        elif key=='age':value=float(value)
        elif isinstance(value,bool):value=int(value)
        bindings['fields'][FIELDS[key]]['initial']=str(value)
    with tempfile.TemporaryDirectory(prefix='plant-catalog-') as temporary:
        directory=Path(temporary)
        for name in ['types3ds.s','types.h']:shutil.copyfile(ROOT/'wfsource/source/oas'/name,directory/name)
        oad=directory/'settings.oad'
        subprocess.run([str(ROOT/'wftools/oas2oad-rs/target/release/oas2oad'),
            '--types='+str(directory/'types3ds.s'),'--prep='+str(ROOT/'wftools/prep/prep'),
            '-o',str(oad),str(HERE/'settings.oas')],check=True)
        spec=importlib.util.spec_from_file_location('plant_property_cooker',ROOT/'scripts/build-object-properties.py')
        cooker=importlib.util.module_from_spec(spec);spec.loader.exec_module(cooker)
        cooked=cooker.catalog(oad,bindings,actor)
        replacement=cooked[8:]
        combined=[replacement if schema=='PlantedTankSettings' else record for _,schema,record in owners]
        if not matches:combined.append(replacement)
        payload=b'RP01'+struct.pack('<I',len(combined))+b''.join(combined)
        result=cooker.attach(level,payload)
        receipt=dict(settings=options,actor=actor,source='RPRP',
            oas_sha256=hashlib.sha256((HERE/'settings.oas').read_bytes()).hexdigest(),
            oad_sha256=hashlib.sha256(oad.read_bytes()).hexdigest(),
            bindings_sha256=hashlib.sha256(json.dumps(bindings,sort_keys=True).encode()).hexdigest(),
            catalog_sha256=hashlib.sha256(payload).hexdigest(),level_sha256=hashlib.sha256(result).hexdigest())
    return result,receipt

def configure_cd(data,options):
    options=validate(options)
    if len(data)<2048 or data[:4]!=b'GAME' or data[8:12]!=b'TOC\0':raise ValueError('Expected GAME/TOC bundle')
    length=struct.unpack_from('<I',data,12)[0]
    if not length or length%12 or 16+length+8>2048:raise ValueError('Invalid TOC size')
    entries=[struct.unpack_from('<4sII',data,16+i) for i in range(0,length,12)]
    starts=[e[1] for e in entries]
    if starts!=sorted(set(starts)) or any(n<2048 or n%2048 for n in starts) or starts[-1]>=len(data):raise ValueError('Invalid TOC offsets')
    result=bytearray(data[:2048]);receipts=[]
    for index,(tag,start,size) in enumerate(entries):
        end=starts[index+1] if index+1<len(entries) else len(data)
        block=data[start:end]
        if size>len(block):raise ValueError('Invalid TOC length')
        if tag[:1]==b'L':
            payload=catalog_payload(block[:size])
            if payload and any(schema=='PlantedTankSettings' for _,schema,_ in records(payload)):
                block,receipt=configure_level(block[:size],options);receipts.append(receipt);size=len(block)
        offset=len(result);result+=block;result+=bytes((-len(result))%2048)
        struct.pack_into('<II',result,20+12*index,offset,size)
    if len(receipts)!=1:raise ValueError('Expected exactly one planted tank catalog in bundle')
    struct.pack_into('<I',result,4,len(result)-8)
    receipt=receipts[0];receipt['cd_sha256']=hashlib.sha256(result).hexdigest()
    return bytes(result),receipt

def require_catalog_runtime(apk):
    libraries=[n for n in apk.namelist() if n.startswith('lib/') and n.endswith('/libwf_game.so')]
    if not libraries or any(MARKER not in apk.read(n) for n in libraries):
        raise ValueError('Rebuild the frozen runtime with the plant RPRP consumer before cooking profiling fixtures')

def reject_removed_arguments(text):
    if any(line.strip().startswith('--plant-') for line in text.splitlines()):
        raise ValueError('Stale plant CLI arguments; convert these values to authored RPRP settings')
