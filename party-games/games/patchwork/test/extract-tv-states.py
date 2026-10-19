"""Extract TV screenshots from coordinator-owned recording using game state timestamps."""
import argparse,bisect,json,subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('evidence',type=Path);args=parser.parse_args();root=args.evidence
receipt=json.loads((root/'receipt.json').read_text());assert receipt['result']=='completed' and receipt['cleanup_verified']
record=next(c for c in receipt['commands'] if any('screenrecord --time-limit' in a for a in c['args']))
start=(record['start']+record['end'])/2
video=root/'capture.mp4';duration=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(video)]).decode().split('"duration": "')[1].split('"')[0])
samples=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','frame=best_effort_timestamp_time','-of','json',str(video)]))['frames']
timestamps=[float(sample['best_effort_timestamp_time']) for sample in samples]
log=(root/'logcat.txt').read_text();assert 'PD_DEVICE_CHECK_COMPLETE' in log
chunks=[]
for line in log.splitlines():
 if 'PD_VISUAL_FRAME ' not in line:continue
 frame=json.loads(line.split('PD_VISUAL_FRAME ',1)[1]);frame['time']/=1000
 key='-'.join(str(frame[k]) for k in ['phase','round','turn','ready','ceremony','players'])
 if chunks and chunks[-1]['key']==key:chunks[-1]['last']=frame['time'];continue
 chunks.append({**frame,'key':key,'last':frame['time']})
frames=root/'frames';frames.mkdir(exist_ok=True);entries=[]
for i,chunk in enumerate(chunks):
 end=chunks[i+1]['time'] if i+1<len(chunks) else start+duration
 # Choose a settled frame before the next state, rather than its transition.
 at=(max(start,chunk['last'])+end)/2-start
 if end<=start or at>duration:continue
 at=max(0,min(duration-.1,at))
 # Android screenrecord emits frames only on changes. Seeking directly to a
 # midpoint returns the NEXT change, which can mislabel a state or hit EOF.
 # Select the sample already displayed at that midpoint instead.
 sample=timestamps[max(0,bisect.bisect_right(timestamps,at)-1)]
 entries.append({**chunk,'video_seconds':round(at,3),'sample_seconds':sample,'image':chunk['key']+'.png'})
def extract(entry):
 subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-ss',str(max(0,entry['sample_seconds']-.0001)),'-i',str(video),'-frames:v','1','-y',str(frames/entry['image'])],check=True)
 assert (frames/entry['image']).exists(),entry
with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(extract,entries))
assert {'LOBBY','STARTING','PLACING','SCORING','ROUND_RESULTS','FINISHED'}<={e['phase'] for e in entries}
assert {e['ceremony'] for e in entries if e['phase']=='FINISHED'}==set(range(37))
(frames/'manifest.json').write_text(json.dumps({'job':receipt['job']['id'],'physical_device':receipt['device']['id'],'duration':duration,'recording_start_epoch':start,'frames':entries},indent=2)+'\n')
print(f'{len(entries)} physical TV screenshots; all phases and 37 ceremony frames -> {frames}')
