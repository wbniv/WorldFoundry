"""Background installation must preserve reservations and avoid foreground control."""
import json
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from wf_device.service import validate_request
from wf_device.store import Store
from wf_device.workflows import Adapter, DeferredLauncher

def test_reserved_install_keeps_reservation_and_excludes_other_jobs(tmp_path):
    store = Store(tmp_path/'state', [{'id':'d1','serial':'s1','health':'ready','abis':['armeabi-v7a'],'enrolled':True}])
    owner = store.register(1000, 'test')['session']
    store.reserve(owner, 'd1', 'Watching TV')
    foreground = store.submit(owner, {'workflow':'check','app':'bomberman','device':'d1'})
    install = store.submit(owner, {'workflow':'install','app':'bomberman','device':'d1'})
    second = store.submit(owner, {'workflow':'install','app':'bomberman','device':'d1'})
    assert store.claim() == [install['id']]
    assert store.claim() == []
    assert store.job(foreground['id'])['state'] == 'queued'
    assert store.job(second['id'])['state'] == 'queued'
    assert store.devices()[0]['reservation']['reason'] == 'Watching TV'

def test_install_rejects_foreground_options():
    request = {'workflow':'install','device':'d1','app':'bomberman','apk':'frozen.apk'}
    validate_request(request, [])
    for field, value in [('scene','jellyfish'),('validator','poke-resume'),('trace','swarm')]:
        with pytest.raises(ValueError):
            validate_request({**request, field:value}, [])

def test_install_stage_never_launches_or_controls_display(tmp_path):
    adapter = object.__new__(Adapter)
    adapter.req = {'workflow':'install','apk':'frozen.apk'}
    adapter.package = 'org.worldfoundry.wf_game.bomberman'
    adapter.out = tmp_path
    adapter.store = Store(tmp_path/'state', [{'id':'d1','serial':'s1','health':'ready','abis':['arm32']}])
    owner = adapter.store.register(1000,'test')['session']
    adapter.job = adapter.store.submit(owner,dict(adapter.req,device='d1'))
    adapter.store.claim()
    adapter.connect = lambda: None
    adapter.foreground = lambda: ['topResumedActivity=com.video/.Player']
    installed = []
    adapter.install = installed.append
    with pytest.raises(DeferredLauncher):
        adapter.run()
    assert installed == ['frozen.apk']
    assert json.loads((tmp_path/'background-install.json').read_text())['foreground_unchanged']
    adapter.uncertain_install = False
    adapter.identity_verified = True
    adapter.capture_remote = []
    adapter.launcher_touched = False
    adapter.cleanup()
    assert adapter.restoration.startswith('unchanged:')

def test_install_rejects_updating_the_foreground_app(tmp_path):
    adapter = object.__new__(Adapter)
    adapter.req = {'workflow':'install','apk':'frozen.apk'}
    adapter.package = 'org.worldfoundry.wf_game.bomberman'
    adapter.out = tmp_path
    adapter.job = {'installation':None}
    adapter.connect = lambda: None
    adapter.foreground = lambda: [adapter.package+'/.TvActivity']
    adapter.install = lambda _: pytest.fail('must reject before installation')
    with pytest.raises(RuntimeError, match='foreground app'):
        adapter.run()
