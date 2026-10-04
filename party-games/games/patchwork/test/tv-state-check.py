"""Capture every TV layout during a real six-player browser game and report fit errors."""
import argparse,json,time
from pathlib import Path
from playwright.sync_api import sync_playwright
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--origin',default='http://127.0.0.1:8096')
parser.add_argument('--out',default=str(Path(__file__).parent/'evidence'/'tv-states'))
args=parser.parse_args();out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
audit=r'''() => {
 const tv=document.querySelector('.television'); if(!tv)return null;
 const key=[tv.dataset.phase,tv.dataset.round,tv.dataset.turn,tv.dataset.ready,tv.dataset.ceremony,tv.dataset.playerCount].join('-');
 const footer=tv.querySelector('.development').getBoundingClientRect(),issues=[];
 for(const child of tv.children){if(child.classList.contains('development'))continue;const r=child.getBoundingClientRect();if(r.bottom>footer.top+2)issues.push({kind:'footer-overlap',element:child.className,bottom:r.bottom,footer:footer.top});}
 const walker=document.createTreeWalker(tv,NodeFilter.SHOW_TEXT);
 while(walker.nextNode()){
  const node=walker.currentNode;if(!node.textContent.trim()||node.parentElement.closest('option,svg'))continue;
  const range=document.createRange();range.selectNodeContents(node);
  for(const r of range.getClientRects()){
   const region=node.parentElement.closest('.lobby,.shared-table,.tv-readiness,.round-results,.ceremony,.standings,.heading,.score-prep,.autoplay-quilts');
   const bounds=region?.getBoundingClientRect();
   // Range rects include font ascent outside a line box, even when the text
   // is visibly unclipped. Allow six pixels for that; viewport/footer checks
   // remain strict and still catch the demonstrated overflowing layouts.
   if(r.left<0||r.right>innerWidth+2||r.top<0||r.bottom>innerHeight+2||(bounds&&(r.left<bounds.left-2||r.right>bounds.right+2||r.top<bounds.top-6||r.bottom>bounds.bottom+6)))issues.push({kind:'text-overflow',text:node.textContent.trim(),rect:{x:r.x,y:r.y,width:r.width,height:r.height},region:region?.className});
  }
 }
 return {key,phase:tv.dataset.phase,round:tv.dataset.round,turn:tv.dataset.turn,ready:tv.dataset.ready,ceremony:tv.dataset.ceremony,players:tv.dataset.playerCount,issues,snapshot:window.__pdVisual};
}'''
with sync_playwright() as pw:
 browser=pw.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
 page=browser.new_page(viewport={'width':960,'height':540},user_agent='Mozilla/5.0 Android TV QuiltNightTV')
 messages=[];errors=[];seen={}
 page.on('console',lambda m:messages.append(m.text));page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto(args.origin+'/receiver?display=android-tv&deviceCheck=1&visualCheck=1')
 deadline=time.monotonic()+240
 while time.monotonic()<deadline:
  entry=page.evaluate(audit)
  if entry and entry['key'] not in seen:
   entry['image']=entry['key']+'.png';page.screenshot(path=str(out/entry['image']));seen[entry['key']]=entry
   print(entry['key'],len(entry['issues']),'fit issues',flush=True)
   (out/'progress.json').write_text(json.dumps(list(seen.values()),indent=2)+'\n')
  if 'PD_DEVICE_CHECK_COMPLETE' in messages:break
  page.wait_for_timeout(120)
 complete='PD_DEVICE_CHECK_COMPLETE' in messages
 report={'viewport':[960,540],'complete':complete,'errors':errors,'states':list(seen.values())}
 (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
 (out/'console.txt').write_text('\n'.join(messages)+'\n')
 browser.close()
 assert complete,'Game did not complete'
 assert not errors,errors
 failures=[s for s in seen.values() if s['issues']]
 assert not failures, f'{len(failures)} states have fit issues; see {out}/report.json'
 print(f'PASS: {len(seen)} six-player TV states fit 960×540')
