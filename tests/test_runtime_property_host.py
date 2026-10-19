"""Real baseline catalogs through the shared host and actual phone transport."""
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import pytest
ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture(scope='module')
def builds(tmp_path_factory):
    out=tmp_path_factory.mktemp('generic-settings')
    spec=importlib.util.spec_from_file_location('catalog',ROOT/'scripts/build-object-properties.py')
    cooker=importlib.util.module_from_spec(spec);spec.loader.exec_module(cooker)
    bindings=json.loads((ROOT/'wflevels/baseline/settings-bindings.json').read_text())
    catalogs=[cooker.catalog(ROOT/'wflevels/baseline/settings.oad',bindings,actor) for actor in [11,22]]
    catalog=out/'baseline.rprp';catalog.write_bytes(b'RP01'+struct.pack('<I',2)+b''.join(c[8:] for c in catalogs))
    core=[str(ROOT/'engine'/name) for name in ['runtime_properties.cpp','runtime_property_form.cpp','runtime_property_host.cpp']]
    libraries=[str(ROOT/'wftools/wf_attr_edit/target/release/libwf_attr_edit.a'),'-ldl','-lpthread','-lm']
    for target,source,extra in [('check','runtime_property_host_test.cpp',[]),('phone','runtime_property_host_phone.cc',[str(ROOT/'wfsource/source/hal/phonepad/phonepad.cc')])]:
        subprocess.run(['c++','-std=c++17','-O1','-pthread','-I'+str(ROOT/'engine'),'-I'+str(ROOT/'wfsource/source'),str(ROOT/'tests'/source),*extra,*core,*libraries,'-o',str(out/target)],check=True)
    return out,catalog

def test_instance_selection_lifecycle_and_transactions(builds):
    out,catalog=builds;subprocess.run([out/'check',catalog],check=True)

def test_phone_picker_isolation_fractional_values_and_reconnect(builds,tmp_path):
    from playwright.sync_api import sync_playwright,expect
    out,catalog=builds
    process=subprocess.Popen([str(out/'phone'),str(catalog),str(ROOT/'wfsource/source/hal/phonepad/controller.html'),str(ROOT/'android/app/src/aquarium/assets/layout.json')],stdout=subprocess.PIPE,text=True)
    try:
        port=int(process.stdout.readline())
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            context=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
            page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(f'http://127.0.0.1:{port}/?k=123456');page.locator('#plant-open').click()
            expect(page.locator('#property-title')).to_have_text('Choose an object')
            page.locator('button[data-owner="22"]').click();expect(page.locator('#property-40')).to_have_value('-3')
            colour=page.locator('#property-201');colour.locator('.colour-open').click()
            expect(colour.locator('.colour-grid button')).to_have_count(16)
            colour.locator('button[data-colour="5810060"]').click()
            expect(colour.locator('output').first).to_have_text('#58A78C')
            colour.get_by_role('button',name='Cancel colour',exact=True).click()
            expect(page.locator('#plant-settings')).to_be_visible()
            expect(colour.locator('.colour-open')).to_have_text('Choose colour · #58878C')
            colour.locator('.colour-open').click();colour.get_by_role('button',name='Custom',exact=True).click()
            expect(colour.locator('.colour-plane')).to_be_visible()
            hue=colour.get_by_role('slider',name='Hue',exact=True).input_value()
            saturation=colour.get_by_role('slider',name='Saturation',exact=True).input_value()
            value=colour.get_by_role('slider',name='Value',exact=True)
            value.fill('0');value.dispatch_event('input')
            expect(colour.locator('output').first).to_have_text('#000000')
            expect(colour.get_by_role('slider',name='Hue',exact=True)).to_have_value(hue)
            expect(colour.get_by_role('slider',name='Saturation',exact=True)).to_have_value(saturation)
            value.fill('100');value.dispatch_event('input')
            plane=colour.locator('.colour-plane');bounds=plane.bounding_box()
            page.mouse.click(bounds['x']+bounds['width']/3,bounds['y']+1)
            expect(colour.get_by_role('slider',name='Hue',exact=True)).to_have_value('120')
            expect(colour.get_by_role('slider',name='Saturation',exact=True)).to_have_value('100')
            expect(value).to_have_value('100')
            colour.get_by_text('RGB / Hex details',exact=True).click()
            colour.get_by_role('textbox',name='Hex',exact=True).fill('#58A78C')
            expect(colour.locator('output').first).to_have_text('#58A78C')
            colour.get_by_role('textbox',name='Red',exact=True).fill('256')
            colour.get_by_role('button',name='Use colour',exact=True).click()
            expect(colour.locator('.colour-plane')).to_be_visible()
            colour.get_by_role('textbox',name='Red',exact=True).fill('88')
            colour.get_by_role('button',name='Use colour',exact=True).click()
            expect(colour.locator('.colour-open')).to_have_text('Choose colour · #58A78C')
            page.reload();expect(page.locator('#property-201 .colour-open')).to_have_text('Choose colour · #58A78C')
            page.locator('#property-201 .colour-open').click()
            page.screenshot(path=str(tmp_path/'colour-palette-phone.png'),full_page=True)
            page.locator('#property-201').get_by_role('button',name='Custom',exact=True).click()
            page.screenshot(path=str(tmp_path/'colour-custom-phone.png'),full_page=True)
            page.locator('#property-201').get_by_role('button',name='Cancel colour',exact=True).click()
            page.locator('#property-40').fill('8');fraction=page.locator('#property-64')
            expect(fraction).to_have_attribute('min','-2');expect(fraction).to_have_attribute('max','2')
            fraction.fill('0.5');fraction.dispatch_event('input');page.locator('#plant-back').click()
            page.locator('#plant-open').click();page.locator('button[data-owner="11"]').click();expect(page.locator('#property-40')).to_have_value('-3')
            page.locator('#property-40').fill('7');page.reload();expect(page.locator('#property-40')).to_have_value('7')
            page.locator('#plant-cancel').click();page.locator('#plant-open').click();page.locator('button[data-owner="22"]').click()
            expect(page.locator('#property-40')).to_have_value('8');expect(fraction).to_have_value('0.5')
            page.locator('#property-40').fill('13');page.locator('#plant-back').click()
            expect(page.locator('#plant-error')).not_to_be_empty();page.locator('#plant-cancel').click()
            page.locator('#plant-open').click();expect(page.locator('button[data-owner]')).to_have_count(2)
            page.screenshot(path=str(tmp_path/'baseline-phone-picker.png'),full_page=True)
            assert not errors;assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            browser.close()
    finally:
        process.terminate();process.wait(timeout=5)
