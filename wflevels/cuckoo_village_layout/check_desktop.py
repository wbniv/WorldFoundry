#!/usr/bin/env python3
"""Capture the standalone layout in the World Foundry desktop renderer."""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tests'))
from debug_bridge_client import BridgeClient

with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
env = dict(os.environ, LD_LIBRARY_PATH=str(ROOT / 'engine/libs'), WF_REST_PORT='0', ASAN_OPTIONS='detect_leaks=0')
args = [str(ROOT / 'engine/wf_game'), '-L' + str(ROOT / 'wflevels/cuckoo_village_layout-standalone.iff'), '--windowed', '--vram-width=4096', '--vram-height=2048', '--vram-slot-width=2048', '--vram-slot-height=2048', '--vram-perm-width=1024', '--vram-perm-height=1024', '--debug-port', str(port), '--debug-bind', '127.0.0.1']
with (OUT / 'engine.log').open('w') as log:
    p = subprocess.Popen(args, cwd=OUT, env=env, stdout=log, stderr=subprocess.STDOUT)
    client = None
    try:
        client = BridgeClient(port=port, timeout=25)
        time.sleep(4)
        path = str(OUT / 'engine.png')
        client.send({'op': 'screenshot', 'filename': path})
        result = client.wait_for(lambda m: m.get('op') in ('screenshot_done', 'error'), timeout=15)
        if not result or result.get('op') != 'screenshot_done':
            raise RuntimeError(f'capture failed: {result}')
        print('World Foundry capture:', path)
    finally:
        if client:
            client.close()
        if p.poll() is None:
            p.terminate()
        p.wait(timeout=5)
