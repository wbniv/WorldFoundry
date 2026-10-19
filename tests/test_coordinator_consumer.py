"""Producer build defaults stay local while device operations use the installed client."""
import hashlib
import importlib.util
import json
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def producer(tmp_path,monkeypatch):
    spec=importlib.util.spec_from_file_location('chromecast_producer',ROOT/'scripts/chromecast.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setattr(module,'ROOT',tmp_path)
    for key in ('WF_CC_WORKFLOW','WF_CC_APP','WF_CC_APK','WF_CC_RECIPE'):
        monkeypatch.delenv(key,raising=False)
    return module


def test_aquarium_default_stays_in_producer(producer,monkeypatch):
    producer.prepare_task_defaults('check')
    assert producer.os.environ['WF_CC_APK']==str(producer.ROOT/'android/app/build/outputs/apk/aquarium/release/worldfoundry-aquarium-release.apk')


def test_explicit_apk_and_recipe_preserved(producer,monkeypatch):
    monkeypatch.setenv('WF_CC_APK','literal build with spaces.apk')
    producer.prepare_task_defaults('check')
    assert producer.os.environ['WF_CC_APK']=='literal build with spaces.apk'
    monkeypatch.delenv('WF_CC_APK')
    recipe=producer.ROOT/'recipe.json';recipe.write_text(json.dumps({'workflow':'install','app':'bomberman','apk':'explicit frozen.apk'}))
    monkeypatch.setenv('WF_CC_RECIPE',str(recipe))
    producer.prepare_task_defaults('submit')
    assert 'WF_CC_APK' not in producer.os.environ


def test_receipt_verified_before_submission(producer,monkeypatch):
    build=producer.ROOT/'android/prime-numbers/build';build.mkdir(parents=True)
    apk=build/'frozen.apk';apk.write_bytes(b'frozen')
    receipt=build/'build-receipt.json'
    receipt.write_text(json.dumps({'apk':str(apk),'sha256':hashlib.sha256(apk.read_bytes()).hexdigest()}))
    monkeypatch.setenv('WF_CC_APP','primes')
    producer.prepare_task_defaults('check')
    assert producer.os.environ['WF_CC_APK']==str(apk)
    apk.write_bytes(b'changed');monkeypatch.delenv('WF_CC_APK')
    with pytest.raises(ValueError,match='receipt does not match'):producer.prepare_task_defaults('check')


def test_no_build_default_for_capture_or_readd(producer,monkeypatch):
    for workflow in ('capture','readd'):
        monkeypatch.setenv('WF_CC_WORKFLOW',workflow)
        producer.prepare_task_defaults('submit')
    producer.prepare_task_defaults('queue')
    assert 'WF_CC_APK' not in producer.os.environ


def test_producer_cannot_start_service(producer):
    with pytest.raises(ValueError,match='service administration'):producer.main(['serve'])
