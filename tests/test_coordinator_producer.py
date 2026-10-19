"""App producers require capabilities and never upgrade the shared host service."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from coordinator_producer import require_capabilities


@pytest.mark.parametrize('caps',[
    {'workflows':['install']},
    {'protocol_version':2,'workflows':['install']},
    {'protocol_version':1,'workflows':['check']},
])
def test_incompatible_service_requires_standalone_upgrade(caps):
    with pytest.raises(RuntimeError,match='Standalone Chromecast coordinator upgrade required'):
        require_capabilities(SimpleNamespace(call=lambda _:caps),'install')


def test_validator_capability_required():
    client=SimpleNamespace(call=lambda _:{'protocol_version':1,'workflows':['check'],'validators':[]})
    with pytest.raises(RuntimeError,match='upgrade required'):
        require_capabilities(client,'check','prime-study')


def test_compatible_service_admits_producer():
    caps={'protocol_version':1,'workflows':['install','check'],'validators':['prime-study']}
    assert require_capabilities(SimpleNamespace(call=lambda _:caps),'check','prime-study')==caps


def test_prime_installer_does_not_read_app_deploy_review_or_run_sudo(tmp_path,monkeypatch):
    spec=importlib.util.spec_from_file_location('prime_producer',ROOT/'android/prime-numbers/install.py')
    installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)
    app=tmp_path/'app';(app/'build').mkdir(parents=True)
    apk=app/'frozen.apk';apk.write_bytes(b'frozen producer input')
    (app/'build/build-receipt.json').write_text(json.dumps({'apk':str(apk),'sha256':hashlib.sha256(apk.read_bytes()).hexdigest()}))
    monkeypatch.setattr(installer,'APP',app);monkeypatch.setattr(installer,'OUT',tmp_path/'evidence')
    monkeypatch.setattr(installer,'Client',lambda:SimpleNamespace(call=lambda _:{'workflows':['install']}))
    monkeypatch.setattr(installer,'run',lambda *args:pytest.fail('No host commands before capability admission'))
    assert installer.main([])==1
    assert 'Standalone Chromecast coordinator' in (installer.OUT/'installation.log').read_text()


@pytest.mark.parametrize('cause',[FileNotFoundError('socket missing'),ConnectionRefusedError('stopped')])
def test_bomberman_stops_without_service_deployment(tmp_path,monkeypatch,cause):
    spec=importlib.util.spec_from_file_location('bomberman_producer',ROOT/'android/bomberman/install.py')
    installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)
    monkeypatch.setattr(installer,'OUT',tmp_path)
    def client():
        raise RuntimeError('Coordinator connection failed; deploy its standalone release') from cause
    monkeypatch.setattr(installer,'Client',client)
    assert installer.main()==1
    assert 'standalone release' in (tmp_path/'installation.log').read_text()
