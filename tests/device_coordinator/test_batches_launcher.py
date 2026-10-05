"""Batch admission/recovery and artwork checks, without touching real TVs."""
import json
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'scripts'))
from wf_device.store import Store, selection
from wf_device.launcher import compare_tile, tile_boxes
from wf_device.client import task_command
from wf_device import launcher
from test_coordinator import service, wait


@pytest.mark.parametrize('value', ['', 'd1,', ',d1', 'd1,,d2', 'all,d1', []])
def test_invalid_selection(value):
    with pytest.raises(ValueError):
        selection(value)


def test_normalize_selection():
    assert selection(' d2, d1,d2 ') == ['d2','d1']
    assert selection('all') == ['all']


def test_batch_parallel_admission_retry_and_results(service, tmp_path):
    _,_,a,b=service
    args={'devices':['all'],'request':{'workflow':'check','app':'aquarium','duration':.3},'token':'same-admission'}
    batch=a.call('submit_batch',args)
    assert batch['targets']==['d1','d2']
    assert a.call('submit_batch',args)['id']==batch['id']
    with pytest.raises(RuntimeError,match='different request'):
        a.call('submit_batch',dict(args,request=dict(args['request'],duration=.4)))
    children=[wait(a,j['id']) for j in batch['jobs']]
    assert children[0]['started'] < children[1]['finished']
    assert children[1]['started'] < children[0]['finished']
    assert a.call('batch',{'batch':batch['id']})['state']=='completed'
    assert a.watch_batch(batch['id'])==0
    a.batch_evidence(batch['id'],tmp_path/'archive')
    manifest=json.loads((tmp_path/'archive/batch.json').read_text())
    assert manifest['targets']==['d1','d2']
    assert all((tmp_path/'archive'/j['target']/j['id']/'receipt.json').exists() for j in manifest['jobs'])
    with pytest.raises(RuntimeError,match='batch owner'):
        b.call('cancel_batch',{'batch':batch['id']})


def test_whole_batch_validation_and_atomic_reservation(service):
    _,_,a,b=service
    req={'workflow':'check','app':'aquarium'}
    with pytest.raises(RuntimeError,match='Unknown'):
        a.call('submit_batch',{'devices':['d1','absent'],'request':req,'token':'invalid'})
    assert not a.call('queue')['jobs']
    a.call('reserve',{'device':'d2','reason':'Watching TV'})
    with pytest.raises(RuntimeError,match='another owner'):
        b.call('reserve_many',{'devices':['all'],'reason':'other'})
    assert next(d for d in a.call('devices') if d['id']=='d1')['reservation'] is None
    assert len(a.call('devices',{'device':' d2,d1,d2 '}))==2
    assert [d['id'] for d in a.call('queue',{'device':'d2'})['devices']]==['d2']
    a.call('release_many',{'devices':['all']})


def test_reserved_child_does_not_block_other_and_cancel_partial(service):
    _,_,a,_=service
    a.call('reserve',{'device':'d2','reason':'TV'})
    batch=a.call('submit_batch',{'devices':['all'],'request':{'workflow':'check','app':'aquarium'},'token':'partial'})
    assert wait(a,batch['jobs'][0]['id'])['state']=='completed'
    assert a.call('batch',{'batch':batch['id']})['jobs'][1]['state']=='queued'
    cancelled=a.call('cancel_batch',{'batch':batch['id']})
    assert [j['state'] for j in cancelled['jobs']]==['completed','cancelled']
    assert a.watch_batch(batch['id'])==1


def test_batch_target_overrides_rejected_before_admission(service):
    _,_,a,_=service
    for extra in ({'pool':'test'},{'device':'d1'},{'address':'192.168.4.1'},{'_setup':{}}):
        with pytest.raises(RuntimeError,match='override'):
            a.call('submit_batch',{'devices':['all'],'request':dict(workflow='readd',**extra),'token':'bad'})
    assert not a.call('queue')['jobs']


def test_task_multiple_target_and_batch_follow(service, monkeypatch, capsys):
    cfg,_,a,_=service
    import wf_device.client as module
    monkeypatch.setattr(module,'Client',lambda:a)
    for name,value in {'DEVICE':'d1,d2','WORKFLOW':'capture','ASYNC':'true'}.items():
        monkeypatch.setenv('WF_CC_'+name,value)
    assert task_command('submit')==0
    output=capsys.readouterr().out
    assert 'BATCH=B-' in output and 'd1: J-' in output and 'd2: J-' in output


def test_install_continuation_survives_restart_and_reservation(tmp_path):
    root=tmp_path/'state'
    store=Store(root,[{'id':'d1','health':'ready','serial':'1','abis':['arm32']}])
    owner=store.register(1000,'test')['session']
    store.reserve(owner,'d1','TV')
    job=store.submit(owner,{'workflow':'install','device':'d1','app':'bomberman','apk':'old.apk'})
    assert store.claim()==[job['id']]
    store.installed(job['id'],'old.apk')
    store.defer_launcher(job['id'])
    assert store.job(job['id'])['phase']=='launcher-verification-pending'
    assert Store(root).claim()==[]
    store.release(owner,'d1')
    assert Store(root).claim()==[job['id']]
    assert Store(root).job(job['id'])['installation']=='old.apk'


def test_cancel_pending_launcher_preserves_install_outcome(tmp_path):
    store=Store(tmp_path,[{'id':'d1','health':'ready','serial':'1'}])
    owner=store.register(1000,'test')['session']
    job=store.submit(owner,{'workflow':'install','device':'d1','app':'bomberman'})
    store.claim();store.installed(job['id'],'some.apk');store.defer_launcher(job['id'])
    cancelled=store.cancel(owner,job['id'])
    assert cancelled['state']=='cancelled' and 'installed; launcher unverified' in cancelled['error']


def artwork(colors=('red','blue')):
    image=Image.new('RGB',(160,90),colors[0])
    draw=ImageDraw.Draw(image)
    draw.rectangle((45,10,100,85),fill=colors[1])
    draw.ellipse((70,20,150,70),fill='white')
    return image


def test_visible_art_matches_and_stale_art_fails():
    wanted=artwork()
    screen=Image.new('RGB',(640,360),'black');screen.paste(wanted,(30,50))
    refs=[{'image':wanted,'file':'expected.png','resource':'res/banner.png','kind':'banner'}]
    assert compare_tile(screen,[(30,50,190,140)],refs)['verified']
    stale=artwork(('green','yellow'));screen.paste(stale,(30,50))
    assert not compare_tile(screen,[(30,50,190,140)],refs)['verified']
    assert not compare_tile(screen,[],refs)['verified']


def test_brightness_mismatch_is_stale_art_not_missing_geometry():
    wanted=artwork()
    screen=Image.new('RGB',(640,360),'black')
    screen.paste(wanted.point(lambda value:round(value*.3)),(30,50))
    refs=[{'image':wanted,'file':'expected.png','resource':'res/banner.png','kind':'banner'}]
    result=compare_tile(screen,[(30,50,190,140)],refs)
    assert not result['verified']
    assert result['brightness_gain']<.65
    assert 'mean_absolute_error' in result  # Identified mismatch triggers reset.


def test_tile_identification_excludes_other_apps_and_page_bounds():
    xml='<hierarchy><node bounds="[0,0][640,360]"><node bounds="[30,50][190,165]"><node text="Cat-Boom!" bounds="[30,145][190,165]"/></node><node content-desc="Other" bounds="[200,50][360,140]"/></node></hierarchy>'
    assert tile_boxes(xml,'Cat-Boom!',(640,360))==[(30,50,190,165)]
    assert tile_boxes(xml,'Absent',(640,360))==[]


@pytest.mark.parametrize('missing', [False,True])
@pytest.mark.parametrize('black_capture', [False,True])
def test_stale_launcher_reset_rechecks_art_and_never_resets_missing_tile(tmp_path,monkeypatch,missing,black_capture):
    import io
    from types import SimpleNamespace
    wanted=artwork();stale=artwork(('green','yellow'))
    refs=[{'image':wanted,'file':'expected.png','resource':'res/banner.png','kind':'banner'}]
    monkeypatch.setattr(launcher,'apk_references',lambda *args:({'package':'org.test','label':'Test App'},refs))
    commands=[];reset=[False]
    def shell(*args,**kwargs):
        commands.append(args)
        if args[:2]==('pm','path'):return 'package:/installed.apk'
        if args[0]=='sha256sum':return 'expected /installed.apk'
        if args[:3]==('cmd','package','resolve-activity'):return 'com.google.android.apps.tv.launcherx/.Home'
        if args[:2]==('pm','clear'):reset[0]=True;return 'Success'
        if args[0]=='cat':
            name='Other' if missing else 'Test App'
            return '<hierarchy><node content-desc="'+name+'" bounds="[30,50][190,140]"/></hierarchy>'
        return ''
    def adb(*args,**kwargs):
        image=Image.new('RGB',(640,360),'black')
        if not black_capture:image.paste(wanted if reset[0] else stale,(30,50))
        stream=io.BytesIO();image.save(stream,format='PNG');return stream.getvalue()
    if black_capture:
        from wf_device import capture
        def fallback(adapter):
            image=Image.new('RGB',(640,360),'black');image.paste(wanted if reset[0] else stale,(30,50))
            image.save(adapter.out/'uiautomation.png')
        monkeypatch.setattr(capture,'capture_current',fallback)
    adapter=SimpleNamespace(out=tmp_path,store=SimpleNamespace(root=tmp_path,phase=lambda *args:None),
                            job={'id':'J-test','installation':'expected.apk'},package='org.test',config={'aapt':'unused'},
                            shell=shell,adb=adb,wait=lambda _:None,key=lambda _:None,capture_remote=[],launcher_touched=False,
                            foreground=lambda:['com.google.android.apps.tv.launcherx/.Home'],req={'workflow':'install'})
    result=launcher.verify(adapter)
    assert result['status']==('failed' if missing else 'verified')
    assert reset[0] is (not missing)
    assert not any(args[:2]==('pm','clear') and args[2]=='org.test' for args in commands)
    if not missing:
        assert (tmp_path/'launcher/verified-tile.png').exists()
        assert result['refreshes'][-1]['operation']=='launcher-data-reset-and-home'


def test_newer_apk_supersedes_pending_icon_verification(tmp_path):
    from types import SimpleNamespace
    commands=[]
    def shell(*args):
        commands.append(args)
        return 'package:/installed.apk' if args[0]=='pm' else 'newer /installed.apk'
    adapter=SimpleNamespace(out=tmp_path,store=SimpleNamespace(root=tmp_path),package='org.test',
                            job={'installation':'older.apk'},shell=shell)
    assert launcher.verify(adapter)['status']=='superseded'
    assert len(commands)==2  # No HOME, reset or reinstall.
