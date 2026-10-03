"""Run the shipped lionfish Forth dispatcher/lifecycle and validate goldfish geometry."""
import json
import math
import re
from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'docs/reference/swarming-poster'))
sys.path.insert(0,str(ROOT/'wflevels/aquarium_tanks'))
import zfhost
import goldfish

@pytest.fixture
def tank(tmp_path,request):
    h=zfhost.Host()
    try:
        fields={'HARDWARE_JOYSTICK1_RAW':1909,'DELTA_TIME':1907,'INPUT':1908,
                'X_POS':3009,'Y_POS':3010,'Z_POS':3011,'ROTATION_A':3012,'ROTATION_B':3013,'ROTATION_C':3014,
                'XSPEED':3018,'YSPEED':3019,'ZSPEED':3020,'X_SCALE':3040,'Y_SCALE':3041,'Z_SCALE':3042,'CAMSHOT':1921}
        buttons={'A':1,'B':2,'C':4,'UP':2048,'DOWN':4096,'RIGHT':8192,'LEFT':16384}
        assert h.eval(' '.join(f': INDEXOF_{n} {v} ;' for n,v in fields.items())+' '+
                      ' '.join(f': JOYSTICK_BUTTON_{n} {v} ;' for n,v in buttons.items())+
                      ' : read-actor-mailbox 100 * + read-mailbox ; '
                      ': write-actor-mailbox 100 * + write-mailbox ; : fish-deform drop drop drop ; '
                      ': profile-begin drop ; : profile-end drop ;')=='ok'
        # Compile the actual generated Director script, without executing its entry.
        text=(ROOT/'wflevels/aquarium_lionfish/aquarium_lionfish.lev').read_text()
        encoded=re.search(r'\{ \'STR\' \{ \'NAME\' "Script" \} \{ \'STR\' ("(?:\\.|[^"\\])*")',text).group(1)
        script=json.loads(encoded).removesuffix('\ntk-director-tick\n')
        script=script.replace(': gf-log-char 0 sys ;',': gf-log-char drop ;').replace(': gf-log-num 1 sys ;',': gf-log-num drop ;')
        if getattr(request,'param',False):script=script.replace(': tk-touch 0 ;',': tk-touch 1 ;')
        target=tmp_path/'director.fth';target.write_text(script)
        assert h.load(target)=='ok'
        h.write(1907,.05)
        h.write(3909,0);h.write(3910,0);h.write(3911,2.5)
        assert h.eval('tk-setup gf-setup')=='ok'
        yield h
    finally:h.close()

def evaluate(h,word):
    assert h.eval(word)=='ok',word

def live(h):return [int(h.read(1000+16*k)) for k in range(3)]

def test_release_limit_edges_and_chord_consumes_down(tank):
    h=tank
    for k in range(4):
        h.write(1909,0);evaluate(h,'tk-input')
        h.write(1909,4097);evaluate(h,'tk-input gf-tick')
        assert h.read(933)==min(k+1,3)
        assert h.read(605)==0
        assert h.read(609)==0
        evaluate(h,'tk-input gf-tick tk-input gf-tick')
        assert h.read(933)==min(k+1,3)
    assert live(h)==[1,1,1]
    # Rejected held A does not spawn when a fish subsequently disappears.
    evaluate(h,'0 gf-i tk! gf-hide 2 gf-count tk! tk-input gf-tick')
    assert h.read(933)==2
    h.write(1909,0);evaluate(h,'tk-input');h.write(1909,4097);evaluate(h,'tk-input gf-tick')
    assert h.read(933)==3

@pytest.mark.parametrize('pos,eaten',[(.65,True),(.9,False),(.2,False)])
def test_player_requires_a_and_mouth_proximity(tank,pos,eaten):
    h=tank
    evaluate(h,'gf-release-one 0 gf-i tk!')
    for slot,val in [(2,pos),(3,0),(4,2.5)]:evaluate(h,f'{val} {slot} gf!')
    evaluate(h,'tk-input')
    assert h.read(933)==1
    h.write(1909,1);evaluate(h,'tk-input gf-tick')
    if eaten:
        assert h.read(934)==0 and h.read(1015)==1 # reserved until capture, not eaten on A
        evaluate(h,'tk-input gf-tick')
    assert h.read(934)==int(eaten)
    assert h.read(933)==int(not eaten)
    if not eaten:assert h.read(605)>0

def test_slot_reuse_nearest_choice_and_player_priority(tank):
    h=tank
    evaluate(h,'gf-release-one gf-release-one')
    for k,x in [(0,.64),(1,.72)]:
        evaluate(h,f'{k} gf-i tk! {x} 2 gf! 0 3 gf! 2.5 4 gf!')
    # Resident mouth coincides with the player mouth.
    h.write(1100,.14);h.write(1101,0);h.write(1102,2.5);h.write(1103,0)
    old=h.read(1001)
    h.write(1909,1);evaluate(h,'tk-input gf-tick')
    assert h.read(1015)==1 and h.read(934)==0
    evaluate(h,'tk-input gf-tick')
    assert h.read(934)==1
    assert h.read(1000)==0
    # An independent resident may catch the other fish, but cannot eat slot0 again.
    assert h.read(935)<=1
    evaluate(h,'gf-release-one')
    assert h.read(1000)==1 and h.read(1001)==old+1
    assert h.read(930)==h.read(931)==0

@pytest.mark.parametrize('tank',[True],indirect=True)
def test_touch_mode_retained_on_c_and_feeding_stays_a(tank):
    h=tank
    h.write(1909,4);evaluate(h,'tk-input');assert h.read(604)==1
    h.write(1909,0);evaluate(h,'tk-input')
    h.write(1909,4097);evaluate(h,'tk-input gf-tick')
    assert h.read(933)==1 and h.read(608)==h.read(609)==0

def test_target_retention_and_lost_target(tank):
    h=tank;evaluate(h,'gf-release-one gf-release-one')
    evaluate(h,'0 gf-i tk! -1 2 gf! 1 gf-i tk! -.4 2 gf!')
    h.write(1100,1.5);h.write(1102,3.2);h.write(1103,.5)
    evaluate(h,'gf-acquire');assert h.read(932)==-1
    for _ in range(14):evaluate(h,'gf-acquire')
    assert h.read(932) in (0,1)
    selected=int(h.read(932));evaluate(h,f'{selected} gf-i tk! gf-hide gf-acquire')
    assert h.read(932)==1-selected

def test_release_point_avoids_both_predators_and_existing_prey(tank):
    h=tank
    h.write(3909,-1);h.write(3911,3.65)
    h.write(1100,2.8);h.write(1102,3.65)
    for k in range(3):evaluate(h,'gf-release-one')
    assert h.read(933)==3
    positions=[(h.read(1002+16*k),h.read(1003+16*k),h.read(1004+16*k)) for k in range(3)]
    for point in positions:
        assert math.dist(point,(-1,0,3.65))>=1.45
        assert math.dist(point,(2.8,.12,3.65))>=1.45
    assert all(math.dist(a,b)>=.5 for i,a in enumerate(positions) for b in positions[i+1:])

def test_export_slots_visibility_material_and_mailboxes():
    import struct
    here=ROOT/'wflevels/aquarium_lionfish'
    mapping=json.loads((here/'actor-map.json').read_text())
    assert len(mapping['indices'])==41 and mapping['feeding']['slots']==3
    assert len([n for n in mapping['indices'] if n.endswith(('_mouth'))])==4
    assert len([n for n in mapping['indices'] if n.startswith('goldfish-')])==3
    text=(here/'aquarium_lionfish.lev').read_text()
    for k in range(3):
        block=text.split(f'"goldfish-{k}"',1)[1].split("{ 'OBJ'",1)[0]
        assert 'Anchored' in block and 'goldfish.iff' in block
        assert re.search(r'"Visibility Mailbox".*?'+str(1000+16*k),block,re.S)
    b=(here/'goldfish.iff').read_bytes();offset=b.index(b'MATL')
    assert struct.unpack_from('<I',b,offset+4)[0]==264 # one native material record
    assert struct.unpack_from('<I',b,offset+8)[0]==6 # textured and prelit
    assert 627<650<655<800<811<930<978<1000<1047<1050<1073<1100<1109<1200<1231<1900

def test_one_mesh_geometry_survives_quantisation_and_animation():
    m=goldfish.geometry()
    assert len(m.faces)==len(m.colors)
    for sample in range(32):
        phase=sample%16
        amplitude=.04 if sample<16 else .12
        verts=[]
        for x,y,z in m.vertices:
            t=max(0,min(1,(.17-x)/.47));w=max(0,(t-.35)/.65)
            y+=amplitude*w*w*math.sin(phase*math.tau/16+t*math.pi)
            verts.append(tuple(round(v*65536)/65536 for v in (x,y,z)))
        for f in m.faces:
            for j in range(1,len(f)-1):
                a,b,c=[verts[k] for k in (f[0],f[j],f[j+1])]
                u=[b[k]-a[k] for k in range(3)];v=[c[k]-a[k] for k in range(3)]
                cross=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
                assert math.sqrt(sum(k*k for k in cross))>4/65536


def prey(h, pos=(0,0,2.5), yaw=0):
    evaluate(h,'gf-release-one 0 gf-i tk!')
    for field,val in zip([2,3,4,5],(*pos,yaw)):
        evaluate(h,f'{val} {field} gf!')


def test_behind_prey_unnoticed_until_visible_and_near_drop_exception(tank):
    h=tank;prey(h,(-1,0,2.5))
    h.write(1100,0);h.write(1101,0);h.write(1102,2.5);h.write(1103,0)
    for _ in range(30):evaluate(h,'gf-acquire')
    assert h.read(932)==-1 and h.read(1011)==0
    h.write(1103,.5)
    evaluate(h,'gf-acquire');assert h.read(932)==-1
    for _ in range(13):evaluate(h,'gf-acquire')
    assert h.read(932)==0
    # Near-mouth appearance bypasses ordinary observation, including just behind mouth.
    evaluate(h,'-1 gf-target tk! 0 11 gf! .3 2 gf!')
    h.write(1103,0);evaluate(h,'gf-acquire')
    assert h.read(932)==0


def test_sight_loss_uses_last_seen_position_then_forgets(tank):
    h=tank;prey(h,(1.4,0,2.5))
    h.write(1100,0);h.write(1101,0);h.write(1102,2.5);h.write(1103,0)
    for _ in range(14):evaluate(h,'gf-acquire')
    assert h.read(932)==0
    remembered=h.read(1050)
    evaluate(h,'-2 2 gf! gf-acquire')
    assert h.read(932)==0 and h.read(1050)==remembered
    for _ in range(17):evaluate(h,'gf-acquire')
    assert h.read(932)==-1


def test_rock_occlusion_for_detection_and_capture(tank):
    h=tank;prey(h,(-4.2,.8,1.1))
    evaluate(h,'-4.2 gf-mouth-x tk! .8 gf-mouth-y tk! 1.0 gf-mouth-z tk! 0 gf-mouth-yaw tk!')
    evaluate(h,'gf-clear-ray 1500 tk! gf-edible 1501 tk!')
    assert h.read(1500)==h.read(1501)==0
    evaluate(h,'2.5 4 gf! 2.5 gf-mouth-z tk! gf-clear-ray 1500 tk!')
    assert h.read(1500)==1


@pytest.mark.parametrize('dt',[1/60,1/30,1/20,1/15])
def test_whole_gulp_once_at_varied_frame_rates(tank,dt):
    h=tank;prey(h,(.65,0,2.5));h.write(1907,dt);h.write(1909,1)
    evaluate(h,'tk-input gf-tick')
    assert h.read(934)==0 and h.read(1015)==1 and h.read(936)>0
    samples=[]
    for _ in range(math.ceil(.4/dt)):
        evaluate(h,'tk-input gf-tick');samples.append(h.read(936))
    assert h.read(934)==1 and h.read(933)==0 and h.read(1200)==-1
    assert max(samples)>.65 and samples[-1]==0
    assert h.read(1015)==0


def test_missed_strike_finishes_animation_without_consuming(tank):
    h=tank;prey(h,(.65,0,2.5));h.write(1909,1)
    evaluate(h,'tk-input gf-tick');assert h.read(1015)==1
    evaluate(h,'0 gf-i tk! 2 2 gf! tk-input gf-tick')
    assert h.read(934)==0 and h.read(933)==1 and h.read(1015)==0 and h.read(936)>0
    for _ in range(6):evaluate(h,'tk-input gf-tick')
    assert h.read(1200)==-1 and h.read(934)==0 and h.read(936)==0


def test_stale_strike_cannot_consume_reused_generation(tank):
    h=tank;prey(h,(.65,0,2.5));h.write(1909,1)
    evaluate(h,'tk-input gf-tick');old=h.read(1001)
    evaluate(h,'0 gf-i tk! gf-hide 0 gf-count tk! gf-release-one 0 gf-i tk! .65 2 gf! 0 3 gf! 2.5 4 gf! tk-input gf-tick')
    assert h.read(1001)==old+1 and h.read(1000)==1 and h.read(934)==0


def test_goldfish_alarm_requires_actual_approach_and_recovers(tank):
    h=tank;prey(h,(0,0,2.5),.5);h.write(3909,-1.46)
    evaluate(h,'gf-threats')
    for _ in range(10):evaluate(h,'gf-threats')
    assert h.read(1012)==h.read(1013)==0
    h.write(1909,1);evaluate(h,'tk-input gf-threats')
    assert h.read(1012)==h.read(1013)==0 # button alone is not a sensory cue
    h.write(3909,-1.11);evaluate(h,'gf-threats')
    assert h.read(1012)==1 and h.read(1013)>0 and h.read(1014)>0
    cooldown=h.read(1014);evaluate(h,'gf-threats')
    assert h.read(1014)<cooldown
    for _ in range(30):evaluate(h,'gf-threats')
    assert h.read(1012)==h.read(1013)==h.read(1014)==0


def test_goldfish_behind_or_receding_threat_does_not_burst(tank):
    h=tank;prey(h,(0,0,2.5),0);h.write(3909,-1.46)
    evaluate(h,'gf-threats');h.write(3909,-1.11);evaluate(h,'gf-threats')
    assert h.read(1013)==0 # behind sensory envelope
    evaluate(h,'.5 5 gf!');h.write(3909,-1.46);evaluate(h,'gf-threats')
    assert h.read(1013)==0 # now visible but receding


def test_articulated_mouth_geometry_and_complete_bounds():
    from lionfish_mouth import feeding_models
    meshes,offsets=feeding_models()
    for j in (4,5):
        m=meshes[j]
        for face in m.faces:
            for k in range(1,len(face)-1):
                a,b,c=(m.vertices[t] for t in (face[0],face[k],face[k+1]))
                u=[b[t]-a[t] for t in range(3)];v=[c[t]-a[t] for t in range(3)]
                cross=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
                assert math.sqrt(sum(t*t for t in cross))>8/65536
        for gape in [k/10 for k in range(11)]:
            angle=gape*(-.025 if j==4 else .09)*math.tau
            for x,y,z in m.vertices:
                wx=x*math.cos(angle)+z*math.sin(angle)+.20+.08*gape
                wz=-x*math.sin(angle)+z*math.cos(angle)-.025
                assert abs(wx)+4.7<6.096-.127
                assert abs(y)+.27<1.651-.127
                assert wz+1.30>.635 and wz+3.75<4.826


def test_pitched_mouth_and_sight_follow_forward_axis(tank):
    h=tank
    evaluate(h,'gf-release-one 0 gf-i tk! .083333333 tk-pitch tk!')
    # A prey ahead of the raised mouth is edible; a prey at the old level mouth is not.
    evaluate(h,'.5715768 2 gf! 0 3 gf! 2.83 4 gf! gf-player-mouth')
    assert h.read(943)==pytest.approx(2.78,abs=.002)
    evaluate(h,'gf-edible gf-see tk!')
    assert h.read(964)==1
    evaluate(h,'.65 2 gf! 0 3 gf! 2.5 4 gf! gf-player-mouth gf-edible gf-see tk!')
    assert h.read(964)==0
