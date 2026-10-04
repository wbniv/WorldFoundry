"""Real browser → real portable phone server → plant settings state."""
from pathlib import Path
import subprocess
import pytest
ROOT=Path(__file__).resolve().parents[1]
@pytest.fixture(scope='module')
def executable(tmp_path_factory):
    exe=tmp_path_factory.mktemp('plant-phone')/'host'
    subprocess.run(['g++','-std=c++17','-O1','-pthread','-I'+str(ROOT/'wfsource/source'),str(ROOT/'tests/plant_phone_host.cc'),str(ROOT/'wfsource/source/hal/phonepad/phonepad.cc'),'-o',str(exe)],check=True)
    return exe

def test_complete_phone_settings_and_reconnection(executable,tmp_path):
    from playwright.sync_api import sync_playwright,expect
    process=subprocess.Popen([str(executable),str(ROOT/'wfsource/source/hal/phonepad/controller.html'),str(ROOT/'android/app/src/aquarium/assets/layout.json')],stdout=subprocess.PIPE,text=True)
    try:
        port=int(process.stdout.readline());url=f'http://127.0.0.1:{port}/?k=123456'
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            context=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
            page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(url);page.locator('#plant-open').click();expect(page.locator('#plant-settings')).to_be_visible();expect(page.locator('#plant-seed')).to_have_value('713')
            page.locator('[data-water="1"]').click();page.locator('#plant-seed').fill('4294967295');page.locator('#plant-speed').fill('4');page.locator('#plant-speed').dispatch_event('input')
            assert page.locator('#plant-apply').count()==0
            page.locator('#plant-regen').click();expect(page.locator('#plant-settings')).to_be_hidden();page.locator('#plant-open').click();expect(page.locator('#plant-detail')).to_contain_text('Saltwater · seed 4294967295');expect(page.locator('#plant-speed')).to_have_value('4')
            page.locator('#plant-seed').fill('42');page.locator('#plant-speed').fill('0');page.locator('#plant-speed').dispatch_event('input');page.wait_for_timeout(100)
            page.screenshot(path=str(tmp_path/'phone-settings.png'),full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            context.close()
            context=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True);page=context.new_page();page.goto(url)
            expect(page.locator('#plant-settings')).to_be_visible();expect(page.locator('#plant-seed')).to_have_value('42');expect(page.locator('#plant-speed')).to_have_value('0')
            page.locator('#plant-cancel').click();expect(page.locator('#plant-settings')).to_be_hidden();page.locator('#plant-open').click();expect(page.locator('#plant-seed')).to_have_value('4294967295')
            page.locator('#plant-seed').fill('4294967296');page.locator('#plant-regen').click();expect(page.locator('#plant-settings')).to_be_visible();page.locator('#plant-seed').fill('0');page.locator('#plant-back').click();expect(page.locator('#plant-settings')).to_be_hidden();page.locator('#plant-open').click();expect(page.locator('#plant-seed')).to_have_value('0')
            assert not errors
            browser.close()
    finally:process.terminate();process.wait(timeout=5)
