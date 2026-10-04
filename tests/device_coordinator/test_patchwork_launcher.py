"""The new Java-only TV app must not weaken native APK checks for other apps."""
import hashlib
import subprocess
import zipfile
from types import SimpleNamespace
import pytest
from wf_device.service import validate_request
from wf_device.workflows import Adapter


def test_patchwork_is_a_registered_app_with_fixed_activity():
    validate_request({'workflow':'check','device':'chromecast-test-01','app':'patchwork','duration':5},[])
    adapter=Adapter.__new__(Adapter)
    adapter.req={'app':'patchwork'};adapter.package='org.worldfoundry.wf_game.patchwork'
    assert adapter.activity()=='org.worldfoundry.wf_game.patchwork/.TvActivity'
    adapter.req={'app':'aquarium'};adapter.package='org.worldfoundry.wf_game.aquarium'
    assert adapter.activity().endswith('/android.app.NativeActivity')


@pytest.mark.parametrize('app,abi,allowed',[
    ('patchwork',None,True),
    ('aquarium',None,False),
    ('patchwork','arm64-v8a',False),
    ('aquarium','armeabi-v7a',True),
])
def test_only_patchwork_may_omit_native_libraries(tmp_path,monkeypatch,app,abi,allowed):
    source=tmp_path/'sample.apk'
    with zipfile.ZipFile(source,'w') as apk:
        apk.writestr('classes.dex',b'fixture')
        if abi:apk.writestr('lib/'+abi+'/libfixture.so',b'fixture')
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    inputs=tmp_path/'inputs';inputs.mkdir();source.rename(inputs/(digest+'.apk'))
    adapter=Adapter.__new__(Adapter)
    adapter.store=SimpleNamespace(root=tmp_path,phase=lambda *_:None)
    adapter.job={'id':'job'};adapter.req={'app':app};adapter.device={'abis':['armeabi-v7a']}
    adapter.package='org.worldfoundry.wf_game.'+app;adapter.config={'aapt':'aapt'}
    monkeypatch.setattr(subprocess,'check_output',lambda *args,**kwargs:"package: name='"+adapter.package+"'")
    installs=[]
    adapter.adb=lambda *args,**kwargs:installs.append(args) or 'Success'
    adapter.shell=lambda *args,**kwargs:'package:/data/app/base.apk' if args[0]=='pm' else digest+' /data/app/base.apk'
    if allowed:
        adapter.install(digest+'.apk');assert len(installs)==1
    else:
        with pytest.raises(ValueError,match='native ABI'):adapter.install(digest+'.apk')
        assert not installs


@pytest.mark.parametrize('automated,log,error',[
    (False,'PD_RECEIVER_MOUNTED',None),
    (True,'PD_RECEIVER_MOUNTED','did not complete'),
    (True,'PD_RECEIVER_MOUNTED\nPD_DEVICE_CHECK_COMPLETE',None),
    (False,'TV_PAGE_LOADED','did not mount'),
])
def test_hardware_check_requires_the_expected_javascript_evidence(tmp_path,automated,log,error):
    import json
    inputs=tmp_path/'inputs';inputs.mkdir()
    with zipfile.ZipFile(inputs/'app.apk','w') as apk:
        apk.writestr('assets/connection.json',json.dumps({'automatedCheck':automated}))
    adapter=Adapter.__new__(Adapter)
    adapter.store=SimpleNamespace(root=tmp_path,phase=lambda *_:None)
    adapter.job={'id':'test'};adapter.req={'workflow':'check','app':'patchwork','apk':'app.apk','duration':0}
    adapter.connect=lambda:None
    adapter.foreground=lambda:['org.worldfoundry.wf_game.patchwork/.TvActivity']
    adapter.install=lambda *_:None;adapter.launch=lambda *_:None;adapter.wait=lambda *_:None
    adapter.out=tmp_path
    adapter.capture=lambda:(tmp_path/'logcat.txt').write_text(log)
    if error:
        with pytest.raises(RuntimeError,match=error):adapter.run()
    else:adapter.run()
