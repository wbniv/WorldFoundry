import os,re,subprocess,time
from pathlib import Path
repo=Path('/home/will/WorldFoundry-wbniv/.worktrees/teleport-audit')
path=Path('/tmp/t4-autonomous-smoke.log')
with path.open('w') as log:
    p=subprocess.Popen(['stdbuf','-oL','-eL',str(repo/'engine/wf_game'),'-L/tmp/t4-autonomous-level/teleport_regression-standalone.iff','--windowed'],
        cwd='/tmp/t4-autonomous-level',env={**os.environ,'DISPLAY':':0','WF_REST_PORT':'0'},stdout=log,stderr=subprocess.STDOUT)
    try:
        deadline=time.monotonic()+25
        while time.monotonic()<deadline:
            assert p.poll() is None,f'engine exited {p.returncode}'
            text=path.read_text(errors='replace')
            rows=re.findall(r'T4_ARRIVAL ([^\n]+)',text)
            if len(rows)>=28:break
            time.sleep(.2)
        assert len(rows)>=28,'missing autonomous evidence'
        expected={1:300,2:100,3:200,4:0,5:200}
        for row in rows:
            step,command,x,camera,scale,ok=map(float,row.split())
            assert abs(x-expected[int(command)])<.01 and abs(camera-x)<.01 and scale==.25 and ok!=0,row
        assert not any(s in text for s in ['runtime error:','ValidPtr( (nil) ) failed','zforth compile error','zforth eval error','ASSERTION FAILED'])
        print(f'PASS: {len(rows)} autonomous desktop arrivals; camera and scale checks pass')
    finally:
        p.terminate()
        try:p.wait(timeout=5)
        except subprocess.TimeoutExpired:p.kill();p.wait()
