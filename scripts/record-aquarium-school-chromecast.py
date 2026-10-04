#!/usr/bin/env python3
"""School recording through the coordinator; annotation runs locally after release."""
import argparse,json,subprocess,tempfile
from pathlib import Path
from wf_device.client import Client
from wf_device.legacy import device_id, ROOT
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--serial',required=True);ap.add_argument('--out',default=str(ROOT/'tests/recordings/aquarium_school_demo.mp4'))
a=ap.parse_args();c=Client()
job=c.submit({'workflow':'record','device':device_id(c,a.serial),'app':'aquarium','scene':'clownfish','apk':str(ROOT/'android/app/build/outputs/apk/aquarium/release/worldfoundry-aquarium-release.apk'),'trace':'school','duration':50,'warmup':0})
result=c.watch(job['id']);work=Path(tempfile.mkdtemp(prefix='aqschool-coordinated-'));c.evidence(job['id'],work)
if result:raise SystemExit(result)
segments=json.loads((work/'segments.json').read_text())
out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
draw=','.join(f"drawtext=text='{label}':enable='between(t,{start:.2f},{end:.2f})':x=24:y=h-52:fontsize=26:fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=8" for start,end,label in segments)
subprocess.run(['ffmpeg','-y','-loglevel','error','-i',str(work/'capture.mp4'),'-vf',draw,'-c:v','libx264','-crf','27','-preset','slow','-pix_fmt','yuv420p','-an',str(out)],check=True)
out.with_suffix('.txt').write_text(''.join(f'{start:6.1f} s to {end:6.1f} s  {label}\n' for start,end,label in segments))
print('Wrote',out)
