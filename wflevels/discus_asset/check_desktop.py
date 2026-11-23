"""Capture the cooked discus review scene through the debug bridge."""
import os, socket, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tests'))
from debug_bridge_client import BridgeClient
with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
env=dict(os.environ,LD_LIBRARY_PATH=str(ROOT/'engine/libs'),WF_REST_PORT='0',ASAN_OPTIONS='detect_leaks=0')
with (OUT/'engine.log').open('w') as log:
 p=subprocess.Popen([str(ROOT/'engine/wf_game'),'-L'+str(ROOT/'wflevels/discus_asset-standalone.iff'),'--windowed','--vram-width=4096','--vram-height=2048','--vram-slot-width=2048','--vram-slot-height=2048','--vram-perm-width=2048','--vram-perm-height=2048','--debug-port',str(port),'--debug-bind','127.0.0.1'],cwd=OUT,env=env,stdout=log,stderr=subprocess.STDOUT)
 client=None
 try:
  client=BridgeClient(port=port,timeout=25);time.sleep(3)
  from PIL import Image, ImageChops
  frames=[]
  for i in range(12):
   path=OUT/('swim-%02d.png'%i)
   client.send({'op':'screenshot','filename':str(path)})
   result=client.wait_for(lambda m:m.get('op') in ('screenshot_done','error'),timeout=15)
   if not result or result.get('op')!='screenshot_done':raise RuntimeError(str(result))
   frames.append(Image.open(path).convert('RGB'));time.sleep(.12)
  # Exclude the FPS overlay and require visible changes in the fish region.
  a=frames[0].crop((120,80,460,430))
  changes=[sum(1 for pixel in ImageChops.difference(a,x.crop((120,80,460,430))).getdata() if max(pixel)>12) for x in frames[1:]]
  if max(changes)<100:raise RuntimeError('No meaningful fish motion detected: '+str(changes))
  print('Peak changed fish-region pixels:',max(changes))
  frames[0].save(OUT/'swim.gif',save_all=True,append_images=frames[1:],duration=120,loop=0)
  print('Captured motion frames and',OUT/'swim.gif')
 finally:
  if client:client.close()
  if p.poll() is None:p.terminate()
  p.wait(timeout=5)
