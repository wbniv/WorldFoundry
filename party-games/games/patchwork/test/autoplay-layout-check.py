"""Stress the actual autoplay overview markup with six long player names in every skin."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).parent;out=root/'evidence';report=[]
fixtures=json.loads((out/'tv-states-fixed/report.json').read_text())['states']
players=next(r['snapshot']['state']['players'] for r in fixtures if r['phase']=='FINISHED')
audit=(root/'tv-state-check.py').read_text().split("audit=r'''",1)[1].split("'''",1)[0]
with sync_playwright() as pw:
 browser=pw.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
 page=browser.new_page(viewport={'width':960,'height':540},user_agent='Mozilla/5.0 Android TV QuiltNightTV')
 page.goto('http://127.0.0.1:8096/receiver?display=android-tv&deviceCheck=1&players=2')
 page.get_by_role('heading',name='Round 1 · turn 1 quilts',exact=True).wait_for(timeout=20000)
 template=page.locator('.television').evaluate('(el)=>el.outerHTML')
 assert page.locator('.autoplay-quilts .quilt').count()==2
 await_stop="""async () => { const mod=await import('/game/client/receiver.js?g=patchwork');mod.unmount(); }"""
 page.evaluate(await_stop)
 for skin in ['linen','night','paper']:
  page.evaluate('''({template,skin}) => {
   document.getElementById('game-root').innerHTML=template;
   const tv=document.querySelector('.television');tv.dataset.theme=skin;tv.dataset.playerCount='6';
   const grid=tv.querySelector('.autoplay-quilts'),article=grid.firstElementChild.cloneNode(true);grid.innerHTML='';
   for(const name of ['W'.repeat(32),'Christopher Wellington Longname','Madeleine Summerfield Longname','Sebastian Winterbottom Longname','Genevieve Featherstone Longname','Maximilian Butterworth Longname']){const clone=article.cloneNode(true);clone.querySelector('h2').textContent=name;grid.appendChild(clone);}
  }''',{'template':template,'skin':skin})
  assert page.locator('.autoplay-quilts .quilt').count()==6
  result=page.evaluate(audit);result['skin']=skin;report.append(result)
  # Review images use six real committed boards from the archived full game.
  # The separate fit assertion above includes an unbroken maximum-length name.
  page.evaluate('''async players => {
   const ui=await import('/game/client/ui.js'),grid=document.querySelector('.autoplay-quilts');
   document.querySelector('.television h1').textContent='Round 3 · turn 6 quilts';
   grid.innerHTML=players.map(p=>'<article><h2>'+ui.escape(p.name)+'</h2>'+ui.board(p.board)+'</article>').join('');
  }''',players)
  result=page.evaluate(audit);result['skin']=skin;report.append(result)
  page.screenshot(path=str(out/f'tv-autoplay-six-boards-{skin}.png'))
 browser.close()
(out/'autoplay-six-board-fit.json').write_text(json.dumps(report,indent=2)+'\n')
assert all(not r['issues'] for r in report),report
print('PASS: actual autoplay overview markup fits six boards, long/unbroken names and all three skins at 960×540')
