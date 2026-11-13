import sys,time,subprocess,json
from pathlib import Path
root=Path('/src');sys.path.insert(0,str(root/'tests'))
from debug_bridge_client import BridgeClient
out=root/'docs/diagnostics/snowgoons-one-acre-2026-11-13'
with (out/'baseline.log').open('w') as log:
 p=subprocess.Popen(['/build/wf-game/src/engine/wf_game','-L/src/wflevels/snowgoons-standalone.iff','-rate20','--debug-port','17913','--debug-bind','127.0.0.1','-width=1280','-height=720'],cwd=root/'wfsource/source/game',stdout=log,stderr=subprocess.STDOUT)
 c=None
 try:
  c=BridgeClient(port=17913,timeout=45)
  for mb in [3009,3010,3011,1906]: c.watch(33,mb)
  rows=[]
  for i in range(11):
   time.sleep(1)
   with c._lock: row=dict(seconds=i,values={str(k):v for k,v in c.mailbox_values.items()},errors=[m for m in c._inbox if m.get('op')=='error'])
   rows.append(row)
  c.send({'op':'screenshot','filename':str(out/'before.png')});time.sleep(1)
  (out/'baseline-positions.json').write_text(json.dumps(rows,indent=2)+'\n')
  print(json.dumps(rows[-1]))
 finally:
  if c:c.close()
  p.terminate()
  try:p.wait(timeout=10)
  except subprocess.TimeoutExpired:p.kill();p.wait()
