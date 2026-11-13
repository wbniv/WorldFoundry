"""Sample the displayed engine FPS from recordings, rather than video frame rate.

OCR is approximate. Keep crops so values can be audited; stale historical FPS
CHECK rows in wf.log must not be used as current-session performance evidence.
"""
from pathlib import Path
import json,re,statistics,subprocess
root=Path(__file__).resolve().parent
results={}
for label in ['device-baseline','device-final']:
    video=root/label/'capture-001.mp4'
    if not video.exists():continue
    crops=root/(label+'-fps');crops.mkdir(exist_ok=True)
    subprocess.run(['ffmpeg','-v','error','-i',str(video),'-vf','fps=1/2,crop=74:32:1793:1017,scale=592:256','-y',str(crops/'%03d.png')],check=True)
    values=[]
    for i,p in enumerate(sorted(crops.glob('*.png'))):
        text=subprocess.check_output(['tesseract',str(p),'stdout','--psm','7','-c','tessedit_char_whitelist=0123456789.'],stderr=subprocess.DEVNULL,text=True).strip()
        m=re.fullmatch(r'\d{1,3}\.\d',text)
        values.append({'seconds':i*2,'text':text,'fps':float(text) if m and 1<float(text)<200 else None})
    measured=[v['fps'] for v in values if v['fps'] is not None and v['seconds']>=4]
    results[label]={'samples':values,'usable_after_4s':len(measured),'median':statistics.median(measured) if measured else None,'mean':statistics.mean(measured) if measured else None}
(root/'device-fps-ocr.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps({k:{a:v[a] for a in ['usable_after_4s','median','mean']} for k,v in results.items()},indent=2))
