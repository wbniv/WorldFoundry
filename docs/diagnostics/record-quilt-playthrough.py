import asyncio,json,subprocess
from pathlib import Path
from playwright.async_api import async_playwright

OUT=Path('/home/will/WorldFoundry-wbniv/docs/diagnostics/patchwork-browser-playthrough-video')

async def main():
    OUT.mkdir(parents=True,exist_ok=True)
    messages=[];errors=[]
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
        context=await browser.new_context(viewport={'width':1920,'height':1080},record_video_dir=str(OUT/'raw'),record_video_size={'width':1920,'height':1080})
        page=await context.new_page()
        page.on('console',lambda msg:messages.append(msg.text))
        page.on('pageerror',lambda error:errors.append(str(error)))
        await page.goto('http://127.0.0.1:8096/receiver?display=android-tv&deviceCheck=1&visualCheck=1')
        await page.wait_for_function("document.querySelector('[data-phase=FINISHED]') !== null",timeout=240000)
        while 'PD_DEVICE_CHECK_COMPLETE' not in messages:
            await page.wait_for_timeout(200)
        await page.wait_for_timeout(4000)
        assert not errors,errors
        overviews={m for m in messages if m.startswith('PD_AUTOPLAY_BOARDS ')}
        assert len(overviews)==18,overviews
        assert await page.locator('.standings li').count()==6
        await page.screenshot(path=str(OUT/'final-standings.png'))
        video=page.video
        await context.close()
        await video.save_as(str(OUT/'playthrough.webm'))
        await browser.close()
    (OUT/'report.json').write_text(json.dumps({'source':'local browser receiver','players':6,'turn_overviews':18,'completed':True,'errors':errors,'console':messages},indent=2)+'\n')
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-i',str(OUT/'playthrough.webm'),'-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart','-y',str(OUT/'quilt-night-playthrough.mp4')],check=True)
    print('PASS: complete six-player game, all 18 overviews and final ceremony. '+str(OUT/'quilt-night-playthrough.mp4'),flush=True)

asyncio.run(main())
