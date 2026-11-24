"""Exercise actual light mailboxes and directional rotation in the desktop engine."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

root = Path('/src')
sys.path.insert(0, str(root / 'tests'))
from debug_bridge_client import BridgeClient

indices = json.loads((root / 'wflevels/cuckoo_village/actor-map.json').read_text())['indices']
env = dict(os.environ, WF_WALL_CLOCK='2026-12-25T12:08:22Z@0', WF_REST_PORT='0')
out = root / 'build-docker/alpine-captures'
out.mkdir(parents=True, exist_ok=True)
with (out / 'light-controls.log').open('w') as log:
    proc = subprocess.Popen(['/src/engine/wf_game', '-L' + str(root / 'wflevels/cuckoo_village-standalone.iff'),
                             '--debug-port', '17801', '--debug-bind', '127.0.0.1', '-width=1280', '-height=720',
                             '--vram-width=4096', '--vram-height=4096', '--vram-slot-width=2048',
                             '--vram-slot-height=2048', '--vram-perm-width=1024', '--vram-perm-height=1024'],
                            env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        c = BridgeClient(port=17801, timeout=60)
        time.sleep(4)
        c.send({'op': 'reload_script', 'idx': indices['Director'], 'source': '\\ test\n0 drop\n'})
        time.sleep(1)
        for actor, mailbox, value in (('SunLight',3048,.37), ('SunLight',3049,.61), ('SunLight',3050,.84),
                                       ('AmbientLight',3048,.21)):
            index = indices[actor]
            c.watch(index, mailbox)
            c.set_mailbox(mailbox, value, idx=index)
            assert c.wait_for_mailbox(index, mailbox, round(value * 255) / 255 if mailbox >= 3048 else value, timeout=5), (actor, mailbox, c.mailbox_values)
        def shot(name):
            c.send({'op': 'screenshot', 'filename': str(out / name)})
            assert c.wait_for(lambda msg: msg.get('op') == 'screenshot_done', timeout=30)
        shot('light-orientation-before.png')
        for mailbox, value in ((3013,.25), (3014,.75)):
            c.watch(indices['SunLight'], mailbox)
            c.set_mailbox(mailbox, value, idx=indices['SunLight'])
            assert c.wait_for_mailbox(indices['SunLight'], mailbox, value, timeout=5)
        time.sleep(.5)
        shot('light-orientation-after.png')
        from PIL import Image, ImageChops, ImageStat
        difference = ImageChops.difference(Image.open(out / 'light-orientation-before.png').convert('RGB'),
                                           Image.open(out / 'light-orientation-after.png').convert('RGB'))
        assert sum(ImageStat.Stat(difference).mean) > 0.3, 'light rotated in mailboxes but did not change the rendered scene'
        print('PASS directional and ambient color read/write and directional rotation', flush=True)
        c.close()
    finally:
        if proc.poll() is None:
            proc.terminate()
        proc.wait(timeout=30)
