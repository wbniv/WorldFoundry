"""Check the Android-TV display path and its in-app device test in desktop Chrome."""
from pathlib import Path
from playwright.sync_api import sync_playwright
out=Path(__file__).parent/'evidence'
with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':960,'height':540},user_agent='Mozilla/5.0 Android TV QuiltNightTV')
    sdk_requests=[]
    def block_sdk(route):
        sdk_requests.append(route.request.url)
        route.abort()
    page.route('https://www.gstatic.com/**',block_sdk)
    messages=[];errors=[]
    page.on('console',lambda message:messages.append(message.text))
    page.on('pageerror',lambda error:errors.append(str(error)))
    # Use the longer hosted join URL even when exercising the local route.
    page.goto('http://192.168.4.21:8096/receiver?display=android-tv')
    page.get_by_role('heading',name='Your next quilt starts here.',exact=True).wait_for()
    assert page.evaluate('document.querySelector(".lobby>div").getBoundingClientRect().bottom <= document.querySelector(".development").getBoundingClientRect().top'), 'Lobby overlaps development footer at the HD TV CSS viewport'
    page.screenshot(path=str(out/'tv-launcher-lobby.png'))
    page.goto('http://192.168.4.21:8096/receiver?display=android-tv&deviceCheck=1&players=2')
    page.get_by_role('heading',name='Round 1 · turn 1 of 6',exact=True).wait_for(timeout=15000)
    page.screenshot(path=str(out/'tv-launcher-cards.png'))
    page.get_by_role('heading',name='Round 1 · turn 1 quilts',exact=True).wait_for(timeout=20000)
    assert page.locator('.autoplay-quilts .quilt').count()==2
    assert page.locator('.autoplay-quilts .filled').count()>14, 'Overview must include the committed first turn, not just starting patches'
    page.screenshot(path=str(out/'tv-launcher-turn-quilts.png'))
    page.get_by_role('heading',name='Round 1 rectangle',exact=True).wait_for(timeout=150000)
    page.screenshot(path=str(out/'tv-launcher-scoring.png'))
    page.get_by_role('heading',name='Every stitch counted.',exact=True).wait_for(timeout=20000)
    page.wait_for_timeout(400)
    assert 'PD_DEVICE_CHECK_COMPLETE' in messages,messages[-10:]
    overviews={line for line in messages if line.startswith('PD_AUTOPLAY_BOARDS ')}
    assert len(overviews)==18,overviews
    assert not any('PD_DEVICE_CHECK_FAILED' in line for line in messages)
    assert not errors,errors
    assert not sdk_requests, 'Android TV must boot without requesting CAF: '+str(sdk_requests)
    page.screenshot(path=str(out/'tv-launcher-standings.png'))
    assert page.locator('.standings li').count()==2
    assert page.evaluate('document.documentElement.scrollHeight <= innerHeight+2')
    (out/'tv-launcher-browser-check.txt').write_text('\n'.join(messages)+'\nPASS: TV display path and owned in-app automated game.\n')
    browser.close()
    print('PASS: Android-TV path, LAN origin, two simulated phones inside display, 18 turns and final score ceremony. Physical device test remains separate.')
