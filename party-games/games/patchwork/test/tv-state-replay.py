"""Replay recorded public game states in all skins, without waiting for another game."""
import argparse,json
from pathlib import Path
from playwright.sync_api import sync_playwright
from importlib.util import spec_from_file_location,module_from_spec
# Share the fit audit without importing the script's executable main loop.
source=(Path(__file__).parent/'tv-state-check.py').read_text()
audit=source.split("audit=r'''",1)[1].split("'''",1)[0]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--report',default=str(Path(__file__).parent/'evidence/tv-states-fixed/report.json'))
parser.add_argument('--out',default=str(Path(__file__).parent/'evidence/tv-states-reviewed'))
args=parser.parse_args();out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
fixtures=json.loads(Path(args.report).read_text())['states'];results=[]
with sync_playwright() as pw:
 browser=pw.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
 page=browser.new_page(viewport={'width':960,'height':540},user_agent='Mozilla/5.0 Android TV QuiltNightTV')
 page.goto('http://127.0.0.1:8096/receiver?display=android-tv&visualCheck=1')
 page.wait_for_selector('.television')
 for fixture in fixtures:
  for skin in ['linen','night','paper']:
   snapshot=fixture['snapshot'];snapshot['skin']=skin
   page.evaluate('''async snapshot => {
    const module=await import('/game/client/receiver.js?g=patchwork');module.unmount();
    localStorage.setItem('pd-tv-skin',snapshot.skin);
    const handlers={};module.mount({root:document.getElementById('game-root'),players:()=>snapshot.players,send:()=>{},on:(type,fn)=>{handlers[type]=fn;return ()=>{};}});
    handlers.PD_STATE(snapshot.state);
   }''',snapshot)
   entry=page.evaluate(audit);entry.pop('snapshot',None);entry['skin']=skin
   entry['image']=fixture['key']+'-'+skin+'.png';page.screenshot(path=str(out/entry['image']));results.append(entry)
 (out/'report.json').write_text(json.dumps({'viewport':[960,540],'states':results},indent=2)+'\n')
 browser.close()
 failures=[r for r in results if r['issues']]
 print(f'{len(results)} state/skin layouts checked; {len(failures)} failures. Report: {out}/report.json')
 for r in failures[:10]:print(r['key'],r['skin'],r['issues'])
 assert not failures
