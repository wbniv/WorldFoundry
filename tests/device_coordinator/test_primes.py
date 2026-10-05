"""Admit only the fixed Primes identity and its reviewed remote validator."""
import hashlib
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'scripts'))
from wf_device.service import validate_request
from wf_device.workflows import Adapter


def test_primes_registration_and_validator():
    request = {'workflow':'check', 'device':'d1', 'app':'primes', 'validator':'prime-study'}
    validate_request(request, [])
    for overrides in ({'app':'bomberman'}, {'workflow':'record'}):
        with pytest.raises(ValueError, match='Primes check'):
            validate_request({**request, **overrides}, [])
    adapter = Adapter.__new__(Adapter)
    adapter.req = {'app':'primes'}
    adapter.package = 'org.worldfoundry.wf_game.primes'
    assert adapter.activity() == 'org.worldfoundry.wf_game.primes/.TvActivity'


@pytest.mark.parametrize('app,package,allowed', [
    ('primes','org.worldfoundry.wf_game.primes',True),
    ('primes','org.worldfoundry.wf_game.bomberman',False),
    ('aquarium','org.worldfoundry.wf_game.aquarium',False),
])
def test_java_apk_admission_retains_package_and_abi_checks(tmp_path, monkeypatch, app, package, allowed):
    source = tmp_path/'sample.apk'
    with zipfile.ZipFile(source, 'w') as apk:
        apk.writestr('classes.dex', b'fixture')
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    inputs = tmp_path/'inputs'; inputs.mkdir(); source.rename(inputs/(digest+'.apk'))
    adapter = Adapter.__new__(Adapter)
    adapter.store = SimpleNamespace(root=tmp_path, phase=lambda *_: None)
    adapter.job = {'id':'job'}; adapter.req = {'app':app}; adapter.device = {'abis':['armeabi-v7a']}
    adapter.package = 'org.worldfoundry.wf_game.'+app; adapter.config = {'aapt':'aapt'}
    monkeypatch.setattr('subprocess.check_output', lambda *a, **kw: "package: name='"+package+"'")
    installs = []
    adapter.adb = lambda *a, **kw: installs.append(a) or 'Success'
    adapter.shell = lambda *a, **kw: 'package:/data/app/base.apk' if a[0] == 'pm' else digest+' /data/app/base.apk'
    if allowed:
        adapter.install(digest+'.apk'); assert len(installs) == 1
    else:
        with pytest.raises(ValueError): adapter.install(digest+'.apk')
        assert not installs
