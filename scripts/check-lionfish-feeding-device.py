#!/usr/bin/env python3
"""Verify the shipped Chromecast build through its real phone-controller path."""
import argparse,hashlib,json,math,re,socket,subprocess,sys,threading,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tests'))
from phonepad_harness import WS
class DeviceWS(WS):
    def __init__(self,host,port,pin):
        self.sock=socket.create_connection((host,port),timeout=5)
        self.sock.sendall((f'GET /ws?k={pin} HTTP/1.1\r\nHost: {host}:{port}\r\n'
            'Upgrade: websocket\r\nConnection: Upgrade\r\n'
            'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n'
            'Sec-WebSocket-Version: 13\r\n\r\n').encode())
        response=b''
        while b'\r\n\r\n' not in response:
            chunk=self.sock.recv(4096)
            if not chunk:break
            response+=chunk
        head,_,self.buf=response.partition(b'\r\n\r\n')
        assert head.startswith(b'HTTP/1.1 101'),head
ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--serial',required=True);args=ap.parse_args()
ADB='/home/will/android-sdk-local/platform-tools/adb';PKG='org.worldfoundry.wf_game.aquarium'
OUT=ROOT/'docs/plans/2026-10-02-lionfish-goldfish-feeding/device';OUT.mkdir(exist_ok=True)
def adb(*words):return subprocess.check_output([ADB,'-s',args.serial,*words],timeout=60)
def key(code):adb('shell','input','keyevent',str(code));time.sleep(.25)
def shot(name):(OUT/(name+'.png')).write_bytes(adb('exec-out','screencap','-p'))
def launch():
    adb('shell','am','force-stop',PKG);adb('shell','am','start','-n',PKG+'/android.app.NativeActivity');time.sleep(4)
    shot('selector')
    for _ in range(4):key(20)
    key(23);time.sleep(3)
def log():return adb('shell','tail','-c','200000',f'/sdcard/Android/data/{PKG}/files/wf.log').decode(errors='replace').rsplit('=== wf_game android_main',1)[-1]
def events():return [list(map(float,line.split())) for line in re.findall(r'^GF ([^\n]+)',log(),re.M)]
launch();pid=adb('shell','pidof',PKG).decode().strip()
cat=adb('logcat','-d','--pid='+pid,'-v','brief').decode(errors='replace')
assert 'level-menu: level 4 starts' in cat
host,port,pin=re.findall(r'phone controller: open http://([\d.]+):(\d+)/\?k=(\d+)',cat)[-1]
ws=DeviceWS(host,int(port),pin)
report={}
input_mask=[0];stop=threading.Event();connection_errors=[]
def heartbeat():
    try:
        while not stop.is_set():
            ws.send_mask(input_mask[0]);stop.wait(.05)
    except OSError as error:connection_errors.append(error)
sender=threading.Thread(target=heartbeat,daemon=True);sender.start()
def hold(mask,seconds=.16):
    input_mask[0]=mask;time.sleep(seconds)
    if connection_errors:raise connection_errors[0]
try:
    hold(0);shot('lionfish-empty')
    hold(4097);hold(4097,.8)
    assert len([e for e in events() if e[0]==1])==1,'Held chord repeated'
    for _ in range(2):hold(0);hold(4097)
    first=events();releases=[e for e in first if e[0]==1]
    assert [e[3] for e in releases]==[1,2,3],releases
    hold(0);hold(4097);hold(0)
    assert len([e for e in events() if e[0]==1])==3,'Fourth release exceeded cap'
    shot('three-goldfish');report['phone_release_edges_held_input_cap']='PASS'
    # Real movement only: approach a visible prey, then press A without DOWN.
    hold(2048,1.1);hold(0);hold(1);hold(0)
    target=None
    for attempt in range(30):
        rows=events()
        if any(e[0]==3 and e[4]==1 for e in rows):break
        snapshots=[e for e in rows if e[0]==4]
        if not snapshots:raise RuntimeError('No player action snapshots')
        # The latest action logs each live slot. Prefer a farther prey to allow turning.
        batch=snapshots[-max(1,int(snapshots[-1][3])):];latest={int(e[1]):e for e in batch}
        if target not in latest:target=max(latest,key=lambda k:abs(latest[k][5]-latest[k][8]))
        e=latest[target];px=e[8]-.56*math.cos(e[11]*math.tau)
        dx=e[5]-px;dz=e[7]-e[10]
        desired=0 if dx>=0 else .5;heading_error=abs((e[11]-desired+.5)%1-.5)
        mask=(8192 if dx>0 else 16384) if abs(dx)>.65 or heading_error>.06 else 0
        mask|=(2048 if dz>0 else 4096) if abs(dz)>.06 else 0
        hold(mask,.22);hold(0,.12);hold(1,.12);hold(0,.10)
    else:raise AssertionError('Player never captured prey through actual steering: '+repr(events()[-15:]))
    shot('after-player-gulp');report['player_near_then_a_whole_gulp']='PASS'
    # Reuse a consumed slot and allow the resident to resolve its natural hunt.
    before=len([e for e in events() if e[0]==1]);hold(4097);hold(0)
    assert len([e for e in events() if e[0]==1])==before+1
    report['consumed_slot_reuse']='PASS'
    for _ in range(40):
        hold(0,.5)
        if any(e[0]==3 and e[4]==2 for e in events()):break
    else:raise AssertionError('Resident did not capture prey')
    shot('after-resident-gulp');report['resident_natural_capture']='PASS'
    rows=events();report['events']=rows
    assert all(0<=e[3]<=3 for e in rows)
finally:
    input_mask[0]=0;time.sleep(.1);stop.set();sender.join(timeout=1);ws.close()
text=log();(OUT/'wf.log').write_text(text)
assert not any(t in text for t in ['ASSERTION FAILED','zforth compile error','zforth eval error','Fatal signal']),text[-2000:]
installed=adb('shell','pm','path',PKG).decode().strip().removeprefix('package:')
actual=adb('shell','sha256sum',installed).decode().split()[0]
assert actual==json.loads((OUT/'build.json').read_text())['apk_sha256']
menu_levels=sum(line.startswith('level ') for line in (ROOT/'wflevels/aquarium-menu.manifest').read_text().splitlines())
report.update(status='PASS',serial=args.serial,installed_apk_sha256=actual,menu_levels=menu_levels,actors=41,
              note='Real shipped phone-controller masks over WebSocket from this PC; no actor teleports or desktop debug bridge. Physical phone/gamepad and held remote Back remain separate checks.')
(OUT/'checks.json').write_text(json.dumps(report,indent=2)+'\n');(OUT/'.gitignore').write_text('*.log\n')
print(json.dumps({k:v for k,v in report.items() if k!='events'},indent=2))
launch() # Leave a fresh zero-prey tank ready for normal play.
