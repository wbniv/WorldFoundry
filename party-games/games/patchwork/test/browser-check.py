"""Play a complete game through two phone UIs and the shared TV display."""
import argparse
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--origin',default='http://localhost:8096')
parser.add_argument('--out',type=Path,default=Path(__file__).parent/'evidence')
parser.add_argument('--headed',action='store_true')
parser.add_argument('--slow-ms',type=int,default=0)
parser.add_argument('--browser',default='/usr/bin/google-chrome')
args=parser.parse_args()
out=args.out;out.mkdir(parents=True,exist_ok=True)
base=args.origin.rstrip('/')
with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path=args.browser,headless=not args.headed,slow_mo=args.slow_ms,args=['--no-sandbox'])
    errors=[]
    contexts=[]
    def page(width,height):
        context=browser.new_context(viewport={'width':width,'height':height})
        # Cast SDK needs a registered application and actual device. Browser test
        # exercises the same game UI + server without contacting device APIs.
        context.route('https://www.gstatic.com/**',lambda route:route.abort())
        contexts.append(context)
        p=context.new_page()
        p.on('pageerror',lambda err:errors.append(str(err)))
        return p
    tv=page(1280,720)
    a=page(390,844)
    b=page(844,390)
    a.goto(base+'/controller?name=Alice')
    a.get_by_role('button',name='Create game',exact=True).click()
    a.wait_for_url('**/*room=*')
    room=parse_qs(urlparse(a.url).query)['room'][0]
    tv.goto(base+'/receiver?room='+room)
    b.goto(base+'/controller?room='+room+'&name=Bob')
    a.get_by_role('button',name='Start game',exact=True).wait_for()
    tv.locator('.tv-roster').get_by_text('Alice',exact=False).wait_for()
    assert tv.locator('.join-qr').evaluate('(i)=>i.complete&&i.naturalWidth>0')
    tv.screenshot(path=str(out/'tv-lobby.png'))
    a.get_by_role('button',name='Start game',exact=True).click()
    for phone in (a,b):
        phone.locator('[data-card]').first.wait_for()
        phone.locator('[data-card]').first.click()
        phone.locator('[data-action="ready"]').click()
    a.locator('[data-action="advance"]:enabled').wait_for()
    a.locator('[data-action="advance"]').click()
    a.get_by_role('heading',name='Round 1 · turn 1 of 6',exact=True).wait_for()
    for phone in (a,b):
        phone.locator('[data-card]').first.click()
        assert phone.evaluate('document.documentElement.scrollWidth <= innerWidth')
    # Pointer dragging must survive re-rendering the grid at each anchor.
    start=a.locator('[data-cell="10"]').bounding_box()
    end=a.locator('[data-cell="20"]').bounding_box()
    a.mouse.move(start['x']+start['width']/2,start['y']+start['height']/2)
    a.mouse.down()
    a.mouse.move(end['x']+end['width']/2,end['y']+end['height']/2,steps=4)
    a.mouse.up()
    ghost=a.locator('.ghost').evaluate_all('(cells)=>cells.map(c=>Number(c.dataset.cell))')
    assert min(i%9 for i in ghost)==2 and min(i//9 for i in ghost)==2, ghost
    a.locator('[data-card]').first.click()
    a.screenshot(path=str(out/'phone-portrait.png'))
    assert b.locator('.quilt').bounding_box()['y']>=0
    ready=b.locator('[data-action="ready"]').bounding_box()
    assert ready['y']+ready['height']<=390, ready
    b.screenshot(path=str(out/'phone-landscape.png'))
    assert tv.evaluate('document.documentElement.scrollHeight <= innerHeight + 2'), 'TV cards overflow vertically'
    tv.screenshot(path=str(out/'tv-cards.png'))
    # Refresh a controller during a live turn and retain identity + quilt.
    b.reload()
    b.get_by_role('heading',name='Round 1 · turn 1 of 6',exact=True).wait_for()
    b.locator('[data-card]').first.wait_for()
    # Exercise a single-cell special, then undo it before committing.
    a.locator('[data-special="single"]').click()
    a.locator('[data-cell="80"]').click()
    a.locator('[data-action="reset"]').click()
    a.locator('[data-card]').first.click()
    a.locator('[data-action="ready"]').click()
    a.locator('[data-action="edit"]').wait_for()
    assert a.locator('[data-action="rotate"]').is_disabled()
    a.locator('[data-action="edit"]').click()
    a.locator('[data-action="ready"]:enabled').wait_for()
    for round_no in range(1,4):
        for turn in range(1,7):
            title='Final turn · choose any remaining patch' if round_no==3 and turn==6 else f'Round {round_no} · turn {turn} of 6'
            for phone in (a,b):
                phone.get_by_role('heading',name=title,exact=True).wait_for()
                phone.locator('[data-card]').first.click()
                if phone.locator('.ghost.invalid').count():
                    phone.locator('[data-action="pass"]').click()
                phone.locator('[data-action="ready"]').click()
            a.locator('[data-action="advance"]:enabled').wait_for()
            a.locator('[data-action="advance"]').click()
            overview=f'Round {round_no} · turn {turn} quilts'
            tv.get_by_role('heading',name=overview,exact=True).wait_for()
            for phone in (a,b):phone.get_by_role('heading',name=overview,exact=True).wait_for()
            assert tv.locator('.autoplay-quilts .quilt').count()==2
            assert b.locator('[data-action="advance"]').count()==0
            assert a.locator('[data-action="ready"]').count()==0
            assert tv.evaluate('document.documentElement.scrollHeight <= innerHeight + 2')
            tv.screenshot(path=str(out/f'tv-turn-results-{round_no}-{turn}.png'))
            if round_no==1 and turn==1:
                tv.screenshot(path=str(out/'tv-turn-results.png'))
                a.screenshot(path=str(out/'phone-turn-results.png'))
                a.set_viewport_size({'width':844,'height':390})
                button=a.get_by_role('button',name='Continue',exact=True).bounding_box()
                assert button['y']+button['height']<=390,button
                a.screenshot(path=str(out/'phone-turn-results-landscape.png'))
                a.set_viewport_size({'width':390,'height':844})
                # Both displays restore the same committed turn, without
                # skipping it or revealing the next card on refresh.
                tv.reload();b.reload()
                tv.get_by_role('heading',name=overview,exact=True).wait_for()
                b.get_by_role('heading',name=overview,exact=True).wait_for()
                assert tv.locator('.autoplay-quilts .quilt').count()==2
            a.get_by_role('button',name='Continue',exact=True).click()
        for phone in (a,b):
            phone.get_by_role('heading',name=f'Round {round_no} · prepare to score',exact=True).wait_for()
            phone.locator('[data-action="ready"]').click()
        a.locator('[data-action="advance"]:enabled').wait_for()
        a.locator('[data-action="advance"]').click()
        if round_no<3:
            a.get_by_role('heading',name=f'Round {round_no} scores',exact=True).wait_for()
            if round_no==1:tv.screenshot(path=str(out/'tv-round-score.png'))
            a.locator('[data-action="advance"]:enabled').wait_for()
            a.locator('[data-action="advance"]').click()
    a.get_by_role('heading',name='The final stitch',exact=True).wait_for()
    tv.get_by_role('heading',name='Round 1 rectangle',exact=True).wait_for()
    assert tv.evaluate('document.documentElement.scrollHeight <= innerHeight + 2'), 'TV ceremony overflow vertically'
    tv.screenshot(path=str(out/'tv-score-counting.png'))
    # Receiver refresh restores the ceremony cursor and running game's snapshot.
    tv.reload()
    tv.get_by_role('heading',name='Round 1 rectangle',exact=True).wait_for()
    for _ in range(4):a.locator('[data-action="next"]').click()
    tv.get_by_role('heading',name='Deduct the empty cells',exact=True).wait_for()
    tv.screenshot(path=str(out/'tv-empty-deduction.png'))
    a.locator('[data-action="back"]').click()
    tv.get_by_role('heading',name='Add the three round scores',exact=True).wait_for()
    a.locator('[data-action="all"]').click()
    tv.get_by_role('heading',name='Every stitch counted.',exact=True).wait_for()
    tv.screenshot(path=str(out/'tv-standings.png'))
    assert tv.locator('.standings li').count()==2
    assert a.locator('.error').count()==0
    assert b.locator('.error').count()==0
    assert not errors,errors
    for context in contexts:context.close()
    browser.close()
    print('PASS: two players, 18 turns, three scorings, portrait/landscape, controller/receiver reloads, final TV ceremony. Evidence: '+str(out))
