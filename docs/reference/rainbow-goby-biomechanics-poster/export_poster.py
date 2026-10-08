#!/usr/bin/env python3
"""Export and check the single-page A3 artifact with Chromium."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1200, 'height': 1700}, device_scale_factor=1.5)
    page.goto((HERE/'poster.html').as_uri())
    page.evaluate('document.fonts.ready')
    review = page.evaluate('''() => {
      const sheet=document.querySelector('.page'), box=sheet.getBoundingClientRect();
      const footer=document.querySelector('footer').getBoundingClientRect();
      return {width:box.width,height:box.height,footerBottom:footer.bottom-box.top,
        overflowing:sheet.scrollHeight>sheet.clientHeight+1};
    }''')
    (HERE/'layout-review.json').write_text(json.dumps(review, indent=2)+'\n')
    assert not review['overflowing'], review
    assert review['footerBottom'] <= review['height'], review
    page.locator('.page').screenshot(path=str(HERE/'poster.png'))
    page.pdf(path=str(HERE/'rainbow-goby-biomechanics-a3.pdf'), prefer_css_page_size=True,
             print_background=True, display_header_footer=False)
    browser.close()
    print(review)
