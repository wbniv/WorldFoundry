#!/usr/bin/env python3
"""Exercise the bundled app's mathematics, hidden answers, remote input and layout."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
EXPECTED = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59,
            61, 67, 71, 73, 79, 83, 89, 97]


def verify(page, out, label):
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.clock.install()
    page.goto((ROOT/'build/assets/primes/index.html').as_uri())
    snapshot = lambda: page.evaluate('primeStudy.snapshot()')

    def key(key, kind='keydown', repeat=False):
        page.evaluate("([key,kind,repeat]) => document.dispatchEvent(new KeyboardEvent(kind,{key,repeat,bubbles:true,cancelable:true}))", [key, kind, repeat])

    def tap(value, count=1):
        for _ in range(count):
            key(value); key(value, 'keyup')

    assert page.locator('.number').count() == 100
    assert page.locator('.number .mark').count() == 0
    assert page.locator('.number').evaluate_all('(nodes) => nodes.map(n => Number(n.dataset.number))') == list(range(1, 101))
    assert page.locator('.number.prime').evaluate_all('(nodes) => nodes.map(n => Number(n.dataset.number))') == EXPECTED
    assert page.locator('#prime-values span').evaluate_all('(nodes) => nodes.map(n => Number(n.textContent))') == EXPECTED
    assert not page.locator('#details').is_visible()
    assert page.locator('#prime-list').bounding_box()['height'] >= page.locator('aside').bounding_box()['height'] - 1
    assert page.evaluate('Array.from({length:100},(_,i)=>i+1).filter(primeStudy.isPrime)') == EXPECTED
    # Verify safe-area bounds, no clipping, and minimum visible numeral size.
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth && document.documentElement.scrollHeight <= innerHeight')
    viewport = page.viewport_size
    for selector in ('.number', 'header', 'aside', 'footer', '#prime-list', '#prime-values span'):
        assert page.locator(selector).evaluate_all('nodes => nodes.every(n => {const b=n.getBoundingClientRect();return b.left>=0 && b.top>=0 && b.right<=innerWidth && b.bottom<=innerHeight && n.scrollHeight<=n.clientHeight+1})'), selector
    assert page.locator('.number').first.evaluate('n => parseFloat(getComputedStyle(n).fontSize)') >= 24
    page.screenshot(path=str(out/(label+'-study.png')))
    # Study stays a reference chart: no explanation or factors after OK.
    for n in (1, 2, 4):
        page.locator('[data-number="'+str(n)+'"]').click()
        tap('Enter'); key('Enter', repeat=True)
        assert snapshot()['panel'] == 'intro' and page.locator('#prime-list').is_visible()
        assert not page.locator('#details').is_visible()
    tap('ArrowLeft', 3); tap('ArrowLeft'); assert snapshot()['selected'] == 1
    tap('ArrowDown', 4); tap('ArrowRight', 4); assert snapshot()['selected'] == 45
    for direction, delta in [('ArrowUp', -10), ('ArrowDown', 10), ('ArrowLeft', -1), ('ArrowRight', 1)]:
        before = snapshot()['selected']; key(direction); page.clock.run_for(650); key(direction, 'keyup')
        after = snapshot()['selected']; assert (after-before)*delta > 0
        page.clock.run_for(700); assert snapshot()['selected'] == after
    # Losing focus cancels held movement; suspend models Activity.onPause.
    key('ArrowRight'); page.evaluate('window.dispatchEvent(new Event("blur"))')
    stopped = snapshot()['selected']; page.clock.run_for(700); assert snapshot()['selected'] == stopped
    key('ArrowLeft'); page.evaluate('primeTvSuspend()')
    stopped = snapshot()['selected']; page.clock.run_for(700); assert snapshot()['selected'] == stopped
    key('ArrowLeft', 'keyup')
    page.evaluate('primeStudy.restore({mode:"study",selected:100})')
    tap('ArrowRight'); tap('ArrowDown'); assert snapshot()['selected'] == 100
    page.evaluate('primeStudy.restore({mode:"study",selected:1})')
    tap('ArrowUp'); assert snapshot()['focus'] == 'tabs'
    tap('ArrowRight'); tap('ArrowDown'); assert snapshot()['focus'] == 'grid'
    tap('ArrowUp'); tap('ArrowRight'); tap('Enter')
    assert snapshot()['mode'] == 'recall'
    assert page.locator('.number.prime').count() == 0
    assert page.locator('.number .mark:visible').count() == 0
    assert not page.locator('#prime-list').is_visible()
    assert 'prime' not in page.locator('[data-number="2"]').get_attribute('aria-label')
    page.screenshot(path=str(out/(label+'-recall-hidden.png')))
    tap('Enter'); key('Enter', repeat=True)
    assert snapshot()['marked'] == {'1': True}
    assert snapshot()['panel'] == 'intro'  # No per-number question or feedback.
    tap('ArrowRight'); tap('Enter')
    assert snapshot()['marked'] == {'1': True, '2': True}
    assert snapshot()['panel'] == 'intro'
    assert page.locator('.number.prime').count() == 0
    assert page.locator('[data-number="3"]').get_attribute('aria-label') == '3, unmarked'
    assert 'prime' not in page.locator('[data-number="2"]').get_attribute('aria-label')
    page.screenshot(path=str(out/(label+'-recall-marked.png')))
    tap('ArrowUp'); tap('ArrowRight'); tap('Enter')  # Recall -> Check control.
    assert snapshot()['panel'] == 'review'
    assert '1 of 25 found' in page.locator('#panel-title').inner_text()
    assert '1 incorrect marks' in page.locator('#panel-body').inner_text()
    assert page.locator('.number.wrong').count() == 1
    assert page.locator('.number.missed').count() == 24
    page.screenshot(path=str(out/(label+'-recall-feedback.png')))
    tap('Escape'); assert not snapshot()['checked'] and snapshot()['marked'] == {'1': True, '2': True}
    tap('Enter'); assert snapshot()['marked'] == {'1': True}  # Unmark 2.
    page.evaluate('primeStudy.restore({mode:"recall",selected:1})')
    for n in EXPECTED:
        page.locator('[data-number="'+str(n)+'"]').click()
    page.locator('#check').click()
    assert '25 of 25 found' in page.locator('#panel-title').inner_text()
    assert page.locator('.number.wrong').count() == 0 and page.locator('.number.missed').count() == 0
    page.screenshot(path=str(out/(label+'-recall-perfect.png')))
    tap('Escape'); tap('Escape'); assert snapshot()['mode'] == 'study'
    assert page.evaluate('primeTvBack()') is False
    page.evaluate('primeStudy.restore({mode:"recall",selected:97})')
    assert snapshot()['mode'] == 'recall' and snapshot()['selected'] == 97
    assert snapshot()['panel'] == 'intro'
    # A new Recall session resets answers.
    tap('Escape'); tap('ArrowUp', 10); tap('ArrowRight'); tap('Enter')
    assert snapshot()['marked'] == {}
    assert not errors, errors
    return {'viewport': viewport, 'legacy_api_removal': label.endswith('legacy'), 'result': 'PASS'}


def main():
    out = ROOT/'build/verification'
    out.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for width, height, legacy in [(960, 540, False), (1920, 1080, False), (960, 540, True)]:
            page = browser.new_page(viewport={'width': width, 'height': height})
            if legacy:
                page.add_init_script('delete Array.prototype.at; delete Object.hasOwn; delete window.structuredClone;')
            label = str(width) + ('-legacy' if legacy else '')
            results.append(verify(page, out, label)); page.close()
            print('PASS', label, 'mathematics/layout/remote/hold/release/reference-only-study/recall/lifecycle')
        browser.close()
    (out/'results.json').write_text(json.dumps(results, indent=2) + '\n')


if __name__ == '__main__':
    main()
