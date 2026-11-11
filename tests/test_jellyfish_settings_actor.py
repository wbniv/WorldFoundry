"""Jellyfish script reads each live setting from its actor's OAD fields."""
import importlib.util
from pathlib import Path
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]
OAD = ROOT/'wfsource/source/oas/jellyfishsettings.oad'

def test_each_setting_changes_the_running_forth(tmp_path):
    raw = OAD.read_bytes()
    names = {}
    for index in range((len(raw)-80)//1491):
        entry = raw[80+1491*index:80+1491*(index+1)]
        name = entry[1:65].split(b'\0',1)[0].decode()
        if name in ('Pulse tempo','Stroke strength','Companions','Jellyfish size'):
            names[name] = index
    assert len(names) == 4
    spec = importlib.util.spec_from_file_location('jelly_zf', ROOT/'docs/reference/swarming-poster/zfhost.py')
    zf = importlib.util.module_from_spec(spec); spec.loader.exec_module(zf)
    src = ROOT/'engine/vendor/zforth-41db72d1/src/zforth'
    zf.BIN = tmp_path/'zf_host'
    subprocess.run(['cc','-O1',f'-I{ROOT}/engine/stubs',f'-I{src}',
                    str(ROOT/'docs/reference/swarming-poster/zf_host.c'),str(src/'zforth.c'),
                    '-lm','-o',str(zf.BIN)],check=True)
    script = (ROOT/'wflevels/aquarium_tanks/jelly_motion.fth').read_text()
    script = script[script.index(': j-setting'):script.index(': j-ease')]
    definitions = ''.join(f': j-{word}-field {names[key]} ;\n' for word,key in (
        ('tempo','Pulse tempo'),('strength','Stroke strength'),('companions','Companions'),('size','Jellyfish size')))
    definitions += ': j-settings-owner 1 ;\n: property@ swap drop dup 7000 + read-mailbox swap 7050 + read-mailbox ;\n'
    path=tmp_path/'jelly.fth';path.write_text(definitions+script)
    host=zf.Host()
    try:
        assert host.load(path)=='ok'
        for key,value in zip(names,(4,2,12,2)):
            host.write(7000+names[key],value);host.write(7050+names[key],1)
        for word, expected in [('j-tempo',1.5),('j-strength',1.3),('j-companions',12),('j-size',1.25)]:
            assert host.eval(f'{word} 7300 write-mailbox')=='ok'
            assert host.read(7300)==pytest.approx(expected)
        host.write(7000+names['Companions'],3)
        assert host.eval('j-companions 7300 write-mailbox')=='ok'
        assert host.read(7300)==3
    finally:
        host.close()
