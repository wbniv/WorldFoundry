"""Real browser → real portable phone server → plant settings state."""
from pathlib import Path
import subprocess
import pytest
ROOT=Path(__file__).resolve().parents[1]
@pytest.fixture(scope='module')
def executable(tmp_path_factory):
    exe=tmp_path_factory.mktemp('plant-phone')/'host'
    subprocess.run(['g++','-std=c++17','-O1','-pthread','-I'+str(ROOT/'wfsource/source'),str(ROOT/'tests/plant_phone_host.cc'),str(ROOT/'wfsource/source/hal/phonepad/phonepad.cc'),str(ROOT/'engine/runtime_properties.cpp'),str(ROOT/'engine/runtime_property_form.cpp'),str(ROOT/'engine/runtime_property_host.cpp'),str(ROOT/'wftools/wf_attr_edit/target/release/libwf_attr_edit.a'),'-ldl','-lpthread','-lm','-o',str(exe)],check=True)
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
            page.goto(url);page.locator('#plant-open').click();expect(page.locator('#plant-settings')).to_be_visible();expect(page.locator('#property-1')).to_have_value('713')
            page.locator('#property-2 button[value="1"]').click();page.locator('#property-1').fill('4294967295');page.locator('#property-3').fill('4');page.locator('#property-3').dispatch_event('input')
            assert page.locator('#plant-apply').count()==0
            expect(page.locator('#property-3')).to_have_attribute('type','range')
            expect(page.locator('#property-3')).to_have_attribute('min','0')
            expect(page.locator('#property-3')).to_have_attribute('max','6')
            assert page.locator('#property-2 button').count()==2
            assert page.locator('#property-2 input[type=radio]').count()==0
            page.locator("button:has-text('Regenerate')").click();expect(page.locator('#plant-settings')).to_be_hidden();page.locator('#plant-open').click();expect(page.locator('#property-2 button[value="1"]')).to_have_attribute('aria-pressed','true');expect(page.locator('#property-1')).to_have_value('4294967295');expect(page.locator('#property-3')).to_have_value('4')
            page.locator('#property-1').fill('42');page.locator('#property-3').fill('0');page.locator('#property-3').dispatch_event('input');page.wait_for_timeout(100)
            page.screenshot(path=str(tmp_path/'phone-settings.png'),full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            context.close()
            context=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True);page=context.new_page();page.goto(url)
            expect(page.locator('#plant-settings')).to_be_visible();expect(page.locator('#property-1')).to_have_value('42');expect(page.locator('#property-3')).to_have_value('0')
            page.locator('#plant-cancel').click();expect(page.locator('#plant-settings')).to_be_hidden();page.locator('#plant-open').click();expect(page.locator('#property-1')).to_have_value('4294967295')
            page.locator('#property-1').fill('4294967296');page.locator("button:has-text('Regenerate')").click();expect(page.locator('#plant-settings')).to_be_visible();page.locator('#property-1').fill('0');page.locator('#plant-back').click();expect(page.locator('#plant-settings')).to_be_hidden();page.locator('#plant-open').click();expect(page.locator('#property-1')).to_have_value('0')
            assert not errors
            browser.close()
    finally:process.terminate();process.wait(timeout=5)

def test_generic_colour_and_text_transactions(executable,tmp_path):
    """Packed RGB and UTF-8 travel through the actual native edit transaction."""
    from playwright.sync_api import sync_playwright,expect
    process=subprocess.Popen([str(executable),str(ROOT/'wfsource/source/hal/phonepad/controller.html'),str(ROOT/'android/app/src/aquarium/assets/layout.json'),'controls'],stdout=subprocess.PIPE,text=True)
    try:
        port=int(process.stdout.readline());url=f'http://127.0.0.1:{port}/?k=123456'
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            page=browser.new_page(viewport={'width':390,'height':844})
            page.goto(url);page.locator('#plant-open').click()
            colour=page.locator('#property-201');picker=colour.locator('.colour-open')
            def choose(value,edit_green=False):
                picker.click()
                details=colour.locator('.colour-details')
                if not details.evaluate('e=>e.open'):
                    colour.get_by_text('RGB / Hex details',exact=True).click()
                colour.get_by_role('textbox',name='Hex',exact=True).fill(value)
                if edit_green:
                    expect(colour.get_by_role('textbox',name='Red',exact=True)).to_have_value('18')
                    colour.get_by_role('textbox',name='Green',exact=True).fill('255')
                    expect(colour.locator('output').first).to_have_text('#12FF56')
                colour.get_by_role('button',name='Use colour',exact=True).click()
            expect(picker).to_have_text('Choose colour · #58878C')
            choose('#123456',edit_green=True)
            expect(picker).to_have_text('Choose colour · #12FF56')
            page.locator('#property-202').fill('Goby: 50% café!')
            expect(page.locator('textarea#property-205')).to_have_value('First line\nSecond line')
            page.locator('#property-205').fill('Notes: 50%\nKeep the plants!')
            expect(page.locator('#property-202')).to_have_attribute('inputmode','text')
            expect(page.locator('#property-203 .colour-open')).to_be_disabled()
            expect(page.locator('#property-204')).to_be_disabled()
            page.locator('#plant-back').click();expect(page.locator('#plant-settings')).to_be_hidden()
            page.locator('#plant-open').click();expect(picker).to_have_text('Choose colour · #12FF56')
            expect(page.locator('#property-202')).to_have_value('Goby: 50% café!')
            expect(page.locator('#property-205')).to_have_value('Notes: 50%\nKeep the plants!')
            choose('#000000')
            page.locator('#property-202').fill('Discard me');page.locator('#plant-cancel').click()
            page.locator('#plant-open').click();expect(picker).to_have_text('Choose colour · #12FF56')
            expect(page.locator('#property-202')).to_have_value('Goby: 50% café!')
            page.locator('#property-202').fill('é'*20)
            page.locator('#plant-back').click();expect(page.locator('#plant-settings')).to_be_visible()
            expect(page.locator('#plant-error')).not_to_be_empty()
            page.locator('#property-202').fill('White');choose('#ffffff')
            page.locator('#plant-back').click();page.locator('#plant-open').click()
            expect(picker).to_have_text('Choose colour · #FFFFFF')
            page.screenshot(path=str(tmp_path/'colour-text-phone.png'),full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.locator('#property-205').scroll_into_view_if_needed()
            page.screenshot(path=str(tmp_path/'notes-phone.png'),full_page=True)
            page.reload();expect(picker).to_have_text('Choose colour · #FFFFFF')
            expect(page.locator('#property-205')).to_have_value('Notes: 50%\nKeep the plants!')
            page.set_viewport_size({'width':1024,'height':768})
            assert page.locator('#plant-settings').evaluate('e=>e.scrollWidth<=e.clientWidth')
            browser.close()
    finally:process.terminate();process.wait(timeout=5)
