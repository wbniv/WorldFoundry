"""Opaque Asian arowana hero, metres at the Aquarium x10 world scale.

Dedicated geometry; shared clownfish motion is a game approximation, not
measured arowana kinematics. +X points toward the mouth.
"""
import math
import re
from pathlib import Path
import sys
from mesh import Mesh
def membrane(name, outline, key, thickness=.028):
    m=Mesh(name)
    # Both faces and the perimeter are closed, so fins stay visible when turning.
    front=[(x,-thickness/2,z) for x,z in outline]
    back=[(x,thickness/2,z) for x,z in outline]
    m.face(front,key); m.face(list(reversed(back)),key)
    for i in range(len(outline)):
        j=(i+1)%len(outline)
        m.face([front[i],back[i],back[j],front[j]],key)
    return m

TOTAL_LENGTH=6.5
MODEL_SCALE=TOTAL_LENGTH/5.94
TAIL_X=-3.25*MODEL_SCALE
NOSE_X=2.69*MODEL_SCALE

COLORS = dict(ar_body=(.39,.48,.25), ar_gold=(.69,.67,.36),
              ar_scale=(.55,.59,.33), ar_edge=(.27,.34,.18),
              ar_fin=(.72,.70,.46), ar_ray=(.42,.46,.26),
              ar_eye=(.025,.03,.018), ar_iris=(.83,.73,.39), ar_glint=(.94,.94,.78))


def models():
    body=Mesh('ar_body')
    body.ellipsoid((.05,0,0),(2.48,.39,.61),'ar_body',32,32)
    body.ellipsoid((2.02,0,.04),(.67,.35,.48),'ar_gold',24,16)
    # Shallow overlapping scales follow both curved flanks and the silhouette.
    for side in (-1,1):
        for row in range(7):
            z=(row-3)*.155
            for col in range(17):
                x=-2.02+col*.245+(row%2)*.12
                if x>1.65: continue
                q=1-((x-.05)/2.48)**2-(z/.61)**2
                if q<.06: continue
                y=side*(.39*math.sqrt(q)+.016)
                points=[]
                for j in range(8):
                    a=math.tau*j/8
                    px=x+.17*math.cos(a); pz=z+.105*math.sin(a)
                    qq=max(.015,1-((px-.05)/2.48)**2-(pz/.61)**2)
                    points.append((px,side*(.39*math.sqrt(qq)+.018),pz))
                center=(x,y+side*.024,z)
                for j in range(8):
                    face=[center,points[j],points[(j+1)%8]]
                    body.face(face if side<0 else list(reversed(face)), 'ar_gold' if j<2 else 'ar_scale')
    # Both eyes, upturned mouth seam and curved opercula.
    for side in (-1,1):
        body.ellipsoid((2.24,side*.295,.20),(.135,.065,.135),'ar_iris',12,8)
        body.ellipsoid((2.26,side*.349,.21),(.077,.018,.077),'ar_eye',10,6)
        body.ellipsoid((2.28,side*.368,.24),(.025,.009,.025),'ar_glint',6,4)
        body.swept_tube([(1.60,side*.31,.35),(1.45,side*.37,.12),(1.52,side*.34,-.23)],.021,'ar_edge',5)
        body.swept_tube([(2.24,side*.30,-.11),(2.53,side*.22,.04),(2.66,side*.10,.16)],.018,'ar_edge',5)
    tail=membrane('ar_tail',[(0,.16),(-.55,.55),(-.90,.48),(-.99,.18),(-.99,-.18),(-.90,-.48),(-.55,-.55),(0,-.16)],'ar_fin',.04)
    for j in range(13):
        z=-.47+j*.078
        tail.swept_tube([(0,0,0),(-.48,-.028,z*.7),(-.94,-.028,z)],.014,'ar_ray',4)
    meshes=[body,tail]; offsets=[(0,0,0),(-2.26,0,0)]
    for name,sign in [('ar_dorsal',1),('ar_anal',-1)]:
        f=membrane(name,[(.72,0),(.50,sign*.32),(-.90,sign*.40),(-1.20,sign*.17),(-1.17,0)],'ar_fin',.035)
        for j in range(17):
            x=-1.12+j*.103
            f.swept_tube([(x,0,0),(x-.06,-.026,sign*.30)],.012,'ar_ray',4)
        meshes.append(f); offsets.append((-1.02,0,sign*.43))
    for label,x,z,width,length in [('pec',1.45,-.19,.64,.72),('pelvic',-.10,-.48,.32,.44)]:
        for side,side_name in [(-1,'near'),(1,'far')]:
            f=Mesh(f'ar_{label}_{side_name}')
            outline=[(0,0,0),(-length*.7,side*width,-.10),(-length,side*width*.6,-.19),(-length*.62,side*.10,-.12)]
            f.face(outline,'ar_fin'); f.face(list(reversed(outline)),'ar_fin')
            for j in range(7):
                f.swept_tube([(0,0,0),(-length*(.5+j*.075),side*width*(1-j*.12),-.10-j*.012)],.012,'ar_ray',4)
            meshes.append(f); offsets.append((x,side*.30,z))
    for side,side_name in [(-1,'near'),(1,'far')]:
        f=Mesh('ar_barbel_'+side_name)
        f.swept_tube([(0,0,0),(.22,side*.055,.02),(.49,side*.09,.08),(.59,side*.10,.12)],.026,'ar_gold',7)
        meshes.append(f);offsets.append((2.66,side*.105,.10))
    for mesh,off in zip(meshes,offsets):
        mesh.vertices=[tuple((p[i]+off[i])*MODEL_SCALE for i in range(3)) for p in mesh.vertices]
        mesh.uvs=[fin_uv(mesh.name,p) for p in mesh.vertices]
    return meshes, [(0,0,0)]*len(meshes)


def scripts(indices, parts, offsets, profile, config):
    # Reuse the canonical library and controller directly; only headers and the
    # additional appendage poses are species-specific.
    aquarium=Path(__file__).resolve().parent.parent/'aquarium'
    sys.path.insert(0,str(aquarium))
    import clownfish as cf
    def word(name,value):return f': {name} {value:.7f} ;\n'
    header='\\ Asian arowana, x10 scale. Game motion tuning.\n: fish-off 0 ;\n'
    tuning={'fish-bob-amp':.018,'fish-tail-idle-amp':.012,'fish-tail-idle-hz':.7,
            'fish-tail-app':1.0,'fish-tail-swim-amp':.038,'fish-tail-hz-max':3,
            'fish-counter-yaw':0,'fish-pec-idle-hz':.65,'fish-pec-hz-hi':1.2,
            'fish-pec-v-hi':3,'fish-pec-sync-lo':.5,'fish-pec-sync-hi':2,
            'fish-pec-idle-amp':.025,'fish-pec-swim-amp':.025,'fish-pec-brake':.045,
            'fish-sway-yaw':.003,'fish-sway-pitch':.002}
    for name,value,_,_ in cf.TUNABLES:header+=word(name,tuning.get(name,value))
    for name,_ in cf.MAILBOXES:header+=word(name,cf.MB[name])
    roles={'body':0,'tail':1,'dorsal':2,'pec-near':4,'pec-far':5}
    for role,j in roles.items():
        header+=word('fish-actor-'+role,indices['animal-00-'+parts[j]])
        for axis,v in zip('xyz',offsets[j]):header+=word('fish-off-'+role+'-'+axis,v)
    header+=word('fish-actor-player',indices['Player'])
    state=['prev','mode','dart-t','dart-req','in-b','dx','dy','dz','vx','vy','vz','t1','cap','brake','flat','was-moving']
    steer=['yaw','yaw-w','yaw-t','pitch','pitch-w','pitch-t','roll','speed','cyc','burst','fx','fy','fz','pushed','lox','hix','loy','hiy','loz','hiz']
    values={**{'aq-'+n:700+j for j,n in enumerate(state)},**{'aq-'+n:740+j for j,n in enumerate(steer)},
        'aq-sway-b':720,'aq-touch':int(profile=='touch'),'aq-remote':int(profile=='remote'),
        'aq-ix':config.DIMENSIONS_M[0]*config.WORLD_SCALE/2-.23,'aq-iy':config.DIMENSIONS_M[1]*config.WORLD_SCALE/2-.23,'aq-zlo':config.BOTTOM,'aq-zhi':config.TOP,'aq-zmin':.7,
        # Conservative envelope includes bob, scales, all fins and animated barbels.
        'aq-box-cx':0,'aq-box-cz':0,'aq-box-hx':3.70,'aq-box-hy':1.50,'aq-box-hz':1.19,
        'aq-v':2.8,'aq-burst-v':2.6,'aq-cycle':1.3,'aq-duty':.55,'aq-tau-a':.22,
        'aq-tau-c':1,'aq-tau-glide':.45,'aq-tau-dart':.18,'aq-dart-v':4,'aq-dart-time':.30,
        'aq-yaw-wn':6,'aq-yaw-zeta':1,'aq-yaw-wmax':.23,'aq-pitch-wn':4,'aq-pitch-zeta':1,
        'aq-pitch-wmax':.08,'aq-pitch-max':1/12,'aq-pitch-diag':1/18,'aq-bank':.35,
        'aq-bank-max':8/360,'aq-turn-dip':.55,'aq-tau-wall':1.0,'aq-flatten-d':1,
        'aq-zone-x':0,'aq-zone-y':0,'aq-zone-z':config.CLOSE_LOOK[2],'aq-zone-in':4,'aq-zone-out':5,
        'aq-shot-a':indices['cs_wide'],'aq-shot-b':indices['cs_close'],'aq-look-b':indices['LookClose'],
        'aq-look-b-x':0,'aq-look-b-z':config.CLOSE_LOOK[2],'aq-look-follow':.4}
    ar_state=['init','neutral','cool','turn','radius','yaw-cap','error','state','room-mb','bend',
              'cam-x','cam-z','cam-init','target-last','turn-side','yaw-old']
    values.update({'ar-'+n:760+j for j,n in enumerate(ar_state)})
    values.update({'ar-length':6.5,'ar-radius-cruise':6.5*.75,'ar-radius-wall':6.5*1.25,
        'ar-recovery':1.2,'ar-pivot-rate':.18,'ar-turn-speed':.9,
        'ar-inner-x':values['aq-ix'],'ar-inner-y':values['aq-iy'],
        'ar-bottom':config.BOTTOM,'ar-top':config.TOP,'ar-sweep-xy':4.25,'ar-sweep-z':3.30})
    for n,v in values.items():header+=word(n,v)
    lib=(aquarium/'clownfish_idle.fth').read_text()
    swim=(aquarium/'aquarium_swim.fth').read_text()
    # Species controller extends shared input/trig/physics primitives only.
    motion=(Path(__file__).resolve().parent/'arowana_motion.fth').read_text()
    lib=re.sub(r': fish-dt\b.*?;', ': fish-dt INDEXOF_DELTA_TIME read-mailbox .05 min ;',lib,flags=re.S)
    pose=': ar-rig-tick fish-phases .25 fish-ph-swim fish-advance fish-channels\n'
    for j,name in enumerate(parts):
        a=indices['animal-00-'+name]
        pose+=f' 0 0 0 fish-place {a} fish-put\n'
        pose+=f' fish-a@ fish-body-b fish@ fish-body-c fish@ {a} fish-orient\n'
        fin_phase='fish-ph-swim fish@'
        fin_amp='.025 fish-speed@ aq-v / fish-clamp01 .04 * +'
        if j==0:fin_amp='0'
        if j in (4,5):
            fin_phase='fish-ph-pec fish@'+(' fish-pec-lag +' if j==5 else '')
            fin_amp='.025 fish-brake fish@ .09 * + fish-yaw-rate fish@ '+('.35' if j==4 else '-.35')+' * + 0 max .15 min'
        if j in (6,7):fin_amp='.012'
        if j in (8,9):fin_amp='.005'
        pose+=f' fish-ph-swim fish@ .012 fish-speed@ aq-v / fish-clamp01 .18 * + ar-bend fish@ {fin_phase} {fin_amp} {TAIL_X:.7f} {NOSE_X:.7f} {a} swim-deform\n'
    pose+=';\n'
    camera="""
: ar-camera-tick
 aq-zone-d2 aq-in-b fish@
 if aq-zone-out aq-sq > if 0 aq-in-b fish! then
 else aq-zone-in aq-sq < if 1 aq-in-b fish! then then
 aq-in-b fish@ if aq-shot-b else aq-shot-a then INDEXOF_CAMSHOT write-mailbox
 ar-cam-init fish@ 0 = if
  aq-look-b-x ar-cam-x fish! aq-look-b-z ar-cam-z fish! 1 ar-cam-init fish!
 then
 aq-look-b-x INDEXOF_X_POS aq-player@ aq-look-b-x - aq-look-follow * +
 ar-cam-x fish@ - fish-dt .6 / fish-clamp01 * ar-cam-x fish@ + dup ar-cam-x fish!
 INDEXOF_X_POS aq-look-b write-actor-mailbox
 aq-look-b-z INDEXOF_Z_POS aq-player@ aq-look-b-z - aq-look-follow * +
 ar-cam-z fish@ - fish-dt .6 / fish-clamp01 * ar-cam-z fish@ + dup ar-cam-z fish!
 INDEXOF_Z_POS aq-look-b write-actor-mailbox ;
"""
    base=header+lib+swim+motion
    # The embedded zForth dictionary is bounded. Compile just the definitions
    # reachable from each entry, preserving the canonical source order.
    def compact(source, entry):
        source='\n'.join(line.split('\\',1)[0] for line in source.splitlines())
        definitions=re.findall(r':\s+(\S+)\s+(.*?);',source,re.S)
        bodies=dict(definitions); needed=set(); pending=entry.split()
        while pending:
            name=pending.pop()
            if name in bodies and name not in needed:
                needed.add(name); pending.extend(bodies[name].split())
        return '\n'.join(': '+name+' '+' '.join(body.split())+' ;'
                         for name,body in definitions if name in needed)+'\n'+entry+'\n'
    return compact(base,'ar-player-tick'),compact(base+pose+camera,'ar-rig-tick ar-camera-tick'),values


def fin_uv(name, point):
    x,y,z=(v/MODEL_SCALE for v in point)
    if name=='ar_body':return 0,0
    if name=='ar_tail':tip=(-2.26-x)/.99
    elif name in ('ar_dorsal','ar_anal'):tip=(abs(z)-.43)/.40
    elif name.startswith('ar_pec_'):tip=(abs(y)-.30)/.64
    elif name.startswith('ar_pelvic_'):tip=(abs(y)-.30)/.32
    else:tip=(x-2.66)/.59
    return max(0,min(1,(x+3.25)/5.94)),max(0,min(1,tip))
