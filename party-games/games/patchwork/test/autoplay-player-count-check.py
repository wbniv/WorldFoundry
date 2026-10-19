"""Play full TV games at every supported count plus one random count."""
import asyncio
import json
import os
from pathlib import Path
from playwright.async_api import async_playwright

OUT=Path(__file__).resolve().parents[4]/'docs/diagnostics/patchwork-autoplay-player-counts'
ORIGIN=os.environ.get('WF_PD_ORIGIN','http://127.0.0.1:8096')

async def check(browser, requested):
    page=await browser.new_page(viewport={'width':960,'height':540})
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    # Accelerate the driver's presentation delays, retaining actual server
    # commands, WebSockets, placement, committed boards and scoring.
    await page.add_init_script('''
        const later=window.setTimeout.bind(window);
        window.setTimeout=(fn,ms,...args)=>later(fn,ms/10,...args);
        window.checkMessages=[];
        const info=console.info.bind(console);
        console.info=(...args)=>{window.checkMessages.push(args.join(' '));info(...args);};
    ''')
    suffix='' if requested is None else '&players='+str(requested)
    await page.goto(ORIGIN+'/receiver?display=android-tv&deviceCheck=1'+suffix)
    await page.wait_for_function("checkMessages.some(m=>m.startsWith('PD_AUTOPLAY_PLAYERS '))")
    count=await page.evaluate("Number(checkMessages.find(m=>m.startsWith('PD_AUTOPLAY_PLAYERS ')).split(' ')[1])")
    assert 2<=count<=6 and (requested is None or count==requested)
    seen=set()
    while not await page.evaluate("checkMessages.includes('PD_DEVICE_CHECK_COMPLETE')"):
        state=await page.evaluate('''() => {
            const tv=document.querySelector('[data-phase="TURN_RESULTS"]');
            if(!tv)return null;
            const quilts=[...tv.querySelectorAll('.autoplay-quilts .quilt')];
            const footer=tv.querySelector('.development').getBoundingClientRect();
            return {key:tv.dataset.round+':'+tv.dataset.turn,count:quilts.length,
              fits:quilts.every(q=>{const r=q.getBoundingClientRect();
                return r.left>=0&&r.right<=innerWidth+1&&r.bottom<=footer.top+1;}),
              scroll:document.documentElement.scrollHeight<=innerHeight+2};
        }''')
        if state:
            assert state['count']==count,state
            assert state['fits'] and state['scroll'],state
            seen.add(state['key'])
        await page.wait_for_timeout(20)
    messages=await page.evaluate('checkMessages')
    overviews={m for m in messages if m.startswith('PD_AUTOPLAY_BOARDS ')}
    assert len(overviews)==18 and len(seen)==18,(requested,seen,overviews)
    assert await page.locator('.standings li').count()==count
    assert not errors,errors
    assert not any('PD_DEVICE_CHECK_FAILED' in m for m in messages),messages
    label='random' if requested is None else str(requested)
    await page.screenshot(path=str(OUT/(label+'-standings.png')))
    await page.close()
    return {'requested':requested,'players':count,'overviews':len(seen),'passed':True}

async def main():
    OUT.mkdir(parents=True,exist_ok=True)
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
        try:
            results=await asyncio.wait_for(asyncio.gather(*(check(browser,n) for n in [2,3,4,5,6,None])),timeout=90)
            (OUT/'report.json').write_text(json.dumps(results,indent=2)+'\n')
            print('PASS: full games with 2–6 players and random selection; 18 fitting overviews per game. '+str(OUT))
        finally:
            await browser.close()

asyncio.run(main())
