"""Cook bounded plant fixtures into the settings actor of a compiled level."""
import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OAS = ROOT/'wfsource/source/oas'
FIELDS = {'seed':'Seed','water':'Water type','age':'Initial age','speed':'Growth speed',
          'textures':'Textures','sway':'Sway','random_entry':'Random seed on entry',
          'seahorses':'Seahorses','greeting':'Greeting'}
MARKER = b'PLANTS settings-source=%s seed=%u water=%s age='

class NoPlantActor(ValueError):
    pass

def validate(options):
    if set(options)-set(FIELDS): raise ValueError('Unknown plant configuration key')
    result=dict(seed=0,water='freshwater',age=0,speed=3,textures=True,sway=True,random_entry=True,seahorses=6,greeting=True)
    result.update(options)
    for key,maximum in [('seed',2147483647),('speed',6),('seahorses',6)]:
        if type(result[key]) is not int or not 0<=result[key]<=maximum: raise ValueError('Invalid '+key)
    if type(result['age']) not in (int,float) or not math.isfinite(result['age']) or not 0<=result['age']<=240: raise ValueError('Invalid age')
    if result['water'] not in ('freshwater','saltwater'): raise ValueError('Invalid water')
    for key in ['textures','sway','random_entry','greeting']:
        if type(result[key]) is not bool: raise ValueError('Invalid '+key)
    if 'seed' in options and 'random_entry' not in options: result['random_entry']=False
    return result

def chunks(data, start, end):
    while start < end:
        if start+8>end: raise ValueError('Truncated IFF chunk')
        tag=data[start:start+4];size=struct.unpack_from('<I',data,start+4)[0]
        begin=start+8;finish=begin+size
        if finish>end: raise ValueError('IFF chunk exceeds container')
        yield tag,begin,finish
        start=(finish+3)&~3
    if start!=end: raise ValueError('Invalid IFF alignment')

def level_data(level):
    if len(level)<8 or level[:4]!=b'L4\0\0' or struct.unpack_from('<I',level,4)[0]+8!=len(level):
        raise ValueError('Expected standalone L4 level')
    outer=list(chunks(level,8,len(level)))
    lvas=[(a,b) for tag,a,b in outer if tag==b'LVAS']
    if len(lvas)!=1: raise ValueError('Expected one LVAS chunk')
    inner=list(chunks(level,*lvas[0]))
    lvls=[(a,b) for tag,a,b in inner if tag==b'LVL\0']
    if len(lvls)!=1: raise ValueError('Expected one LVL chunk')
    return lvls[0]

def actor_layout(level):
    start,end=level_data(level)
    if end-start<52: raise ValueError('Truncated LVL header')
    count,array=struct.unpack_from('<ii',level,start+4)
    common_size,common_off=struct.unpack_from('<ii',level,start+44)
    if count<1 or array<0 or array+4*count>end-start or common_size<0 or common_off<0 or common_off+common_size>end-start:
        raise ValueError('Invalid LVL offsets')
    types=(OAS/'objects.lc').read_text().split('{',1)[1].split('}',1)[0].split()
    plant_type=types.index('plantedtanksettings'); level_type=types.index('levelobj')
    actors=[];level_payload=None
    for index in range(1,count):
        relative=struct.unpack_from('<i',level,start+array+4*index)[0]
        if relative<0 or relative+68>end-start: raise ValueError('Invalid actor offset')
        at=start+relative;kind=struct.unpack_from('<h',level,at)[0];size=struct.unpack_from('<h',level,at+66)[0]
        if size<0 or relative+68+size>end-start: raise ValueError('Invalid actor payload')
        if kind==plant_type: actors.append((index,at+68,size))
        if kind==level_type: level_payload=(at+68,size)
    if not actors: raise NoPlantActor('Level has no PlantedTankSettings actor')
    if len(actors)!=1 or not level_payload or level_payload[1]<584: raise ValueError('Ambiguous or incomplete settings metadata')
    descriptor_offset=struct.unpack_from('<i',level,level_payload[0]+580)[0]
    common=start+common_off
    if descriptor_offset<0 or descriptor_offset+4>common_size: raise ValueError('Invalid descriptor table')
    table=common+descriptor_offset;entries=struct.unpack_from('<i',level,table)[0]
    if entries<0 or descriptor_offset+4+entries*20>common_size: raise ValueError('Invalid descriptor count')
    matches=[]
    for i in range(entries):
        kind,first,prefix,offset,length=struct.unpack_from('<iiiii',level,table+4+i*20)
        if kind==plant_type: matches.append((first,prefix,offset,length))
    if len(matches)!=1: raise ValueError('Expected one planted descriptor')
    first,prefix,offset,length=matches[0];schema=(OAS/'plantedtanksettings.oad').read_bytes()
    if first<0 or prefix<0 or offset<0 or length<0 or offset+length>common_size:
        raise ValueError('Invalid planted descriptor bounds')
    expected=schema[:80]+schema[80+first*1491:]
    if bytes(level[common+offset:common+offset+length])!=expected:
        raise ValueError('Level uses a different planted descriptor')
    normalized=json.loads(subprocess.check_output([str(ROOT/'wftools/wf_attr_edit/target/release/catalog'),str(OAS/'plantedtanksettings.oad')],text=True))
    cursor=prefix;positions={}
    for field in normalized['fields']:
        if field['index']<first or field['kind'] not in ('Int','Float','Enum','Bool'): continue
        if field['width']!=4: raise ValueError('Unexpected planted field width')
        positions[field['key']]=cursor;cursor+=4
    actor,at,size=actors[0]
    if cursor>size or not set(FIELDS.values())<=set(positions): raise ValueError('Incomplete planted actor payload')
    return actor,at,positions

def configure_level(level,options):
    options=validate(options);actor,at,positions=actor_layout(level);out=bytearray(level);offsets=[]
    for key,value in options.items():
        if key=='water': value=int(value=='saltwater')
        elif key=='age': value=round(float(value)*65536)
        elif isinstance(value,bool): value=int(value)
        offset=at+positions[FIELDS[key]];struct.pack_into('<i',out,offset,value);offsets.append(offset)
    result=bytes(out)
    return result,dict(settings=options,actor=actor,source='OAD',field_offsets=offsets,
                       oad_sha256=hashlib.sha256((OAS/'plantedtanksettings.oad').read_bytes()).hexdigest(),
                       level_sha256=hashlib.sha256(result).hexdigest())

def configure_cd(data,options):
    options=validate(options)
    if len(data)<2048 or data[:4]!=b'GAME' or data[8:12]!=b'TOC\0': raise ValueError('Expected GAME/TOC bundle')
    length=struct.unpack_from('<I',data,12)[0]
    if not length or length%12 or 16+length+8>2048: raise ValueError('Invalid TOC size')
    out=bytearray(data);receipts=[]
    for i in range(length//12):
        tag,start,size=struct.unpack_from('<4sII',data,16+12*i)
        if start+size>len(data): raise ValueError('Invalid TOC bounds')
        if tag[:1]!=b'L': continue
        try: changed,receipt=configure_level(data[start:start+size],options)
        except NoPlantActor: continue
        if len(changed)!=size: raise ValueError('Actor edit changed level size')
        out[start:start+size]=changed;receipts.append(receipt)
    if len(receipts)!=1: raise ValueError('Expected exactly one planted settings actor in bundle')
    result=bytes(out);receipt=receipts[0];receipt['cd_sha256']=hashlib.sha256(result).hexdigest()
    return result,receipt

def require_actor_runtime(apk):
    libraries=[n for n in apk.namelist() if n.startswith('lib/') and n.endswith('/libwf_game.so')]
    if not libraries or any(MARKER not in apk.read(n) for n in libraries):
        raise ValueError('Rebuild the frozen runtime with the actor-backed plant consumer')

def reject_removed_arguments(text):
    if any(line.strip().startswith('--plant-') for line in text.splitlines()):
        raise ValueError('Stale plant CLI arguments; author values on the settings actor')
