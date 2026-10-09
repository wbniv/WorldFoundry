#!/usr/bin/env python3
import argparse,time,json,socket,subprocess
from pathlib import Path
from Xlib import X, XK, display, protocol
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description='Exercise production desktop Runtime Options through its own X11 window and read-only diagnostics.')
parser.add_argument('--out',type=Path,required=True)
parser.add_argument('--level',type=Path,default=root/'wflevels/baseline/build/default-standalone.iff')
parser.add_argument('--port',type=int,default=7786)
a=parser.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
manifest=out/'menu.manifest';manifest.write_text('title Runtime Options test\nprompt Choose a game\n'+''.join('level '+str(a.level.resolve())+' | Baseline '+str(i)+'\n' for i in range(2)))
subprocess.run([str(root/'wftools/cdpack-rs/target/release/cdpack'),str(root/'wfsource/source/game/shell-menu.fth'),'--manifest',str(manifest),'-o',str(out/'cd.iff')],check=True)
d=display.Display();existing=set()
def windows(w):
 for c in w.query_tree().children:
  yield c
  yield from windows(c)
for w in windows(d.screen().root):
 if w.get_wm_name()=='World Foundry':existing.add(w.id)
log=(out/'wf.log').open('w');p=subprocess.Popen([str(root/'engine/wf_game'),'-width=960','-height=540','--debug-port',str(a.port),'--vram-width=5120','--vram-height=2048','--vram-slot-width=1024','--vram-slot-height=1024','--vram-perm-width=1024','--vram-perm-height=1024'],cwd=out,stdout=log,stderr=subprocess.STDOUT)
client=None;f=None;snaps=[]
try:
 deadline=time.monotonic()+15;win=None
 while not win:
  assert p.poll() is None, 'engine exited'
  for w in windows(d.screen().root):
   if w.get_wm_name()=='World Foundry' and w.id not in existing:win=w;break
  if time.monotonic()>deadline:raise RuntimeError('window timeout')
  time.sleep(.1)
 def key(name,duration=.15):
  code=d.keysym_to_keycode(XK.string_to_keysym(name))
  for pressed in [True,False]:
   typ=protocol.event.KeyPress if pressed else protocol.event.KeyRelease
   ev=typ(time=X.CurrentTime,root=d.screen().root,window=win,same_screen=1,child=X.NONE,root_x=0,root_y=0,event_x=0,event_y=0,state=0,detail=code)
   win.send_event(ev,event_mask=X.KeyPressMask if pressed else X.KeyReleaseMask);d.flush();time.sleep(duration if pressed else .18)
 time.sleep(1);client=socket.create_connection(('127.0.0.1',a.port),timeout=5);f=client.makefile('rb')
 def snap(label):
  client.sendall((json.dumps({'v':1,'op':'snapshot','request':len(snaps)+1,'draft':True})+'\n').encode());s=json.loads(f.readline());snaps.append(dict(label=label,snapshot=s));return s
 def wait(label,predicate):
  for _ in range(40):
   s=snap(label)
   if predicate(s):return s
   time.sleep(.1)
  raise RuntimeError(label+' timeout: '+repr(s))
 def values(s,draft=False):return {f['field']:f.get('draft' if draft else 'committed') for f in s['properties']['fields']}
 key('space');wait('loaded',lambda s:s['game']['mode']=='game' and s['game']['modal']=='none')
 key('space',1.4);wait('picker',lambda s:s['game']['modal']=='object-picker');key('space');wait('form',lambda s:s['game']['modal']=='form')
 # Left enters the section rail; Down chooses the single Runtime Options sheet.
 key('Left');key('Down');key('Right')
 key('Left');s=snap('draft-fps-off');assert values(s,True)[1000]=='0',s
 assert values(s)[1000]=='1';key('Down');key('Right');s=snap('draft-fixed');assert values(s,True)[1001]=='1'
 key('Down');key('Right');s=snap('draft-rate');assert values(s,True)[1002]=='21'
 key('BackSpace');s=wait('applied',lambda s:s['game']['modal']=='none');assert values(s)[1000]=='0' and values(s)[1001]=='1' and values(s)[1002]=='21'
 key('space',1.4);wait('second-picker',lambda s:s['game']['modal']=='object-picker');key('Down');key('space');s=wait('second-owner',lambda s:s['game']['modal']=='form');assert values(s)[1000]=='0' and values(s)[1002]=='21'
 key('Left');key('Down');key('Right');key('Right');key('Down');key('Left');key('Down');key('Down');key('Right');key('Down');key('Right');key('BackSpace')
 s=wait('profilers-applied',lambda s:s['game']['modal']=='none');assert values(s)[1000]=='1' and values(s)[1001]=='0' and values(s)[1003]=='1' and values(s)[1004]=='1';time.sleep(7)
 print('Production runtime Apply, FPS state, fixed/real-time clock selection, two-owner readback and profiler output passed')
finally:
 if f:f.close()
 if client:client.close()
 p.terminate()
 try:p.wait(timeout=10)
 except subprocess.TimeoutExpired:p.kill();p.wait()
 log.close();d.close();(out/'snapshots.json').write_text(json.dumps(snaps,indent=2)+'\n')

text=(out/'wf.log').read_text()
assert 'RUNTIME-OPTIONS applied=3 fps=0 fixed_delta=0.047619' in text
assert 'frame-profile: total' in text and 'script-profile: actor' in text
