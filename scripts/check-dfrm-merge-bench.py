#!/usr/bin/env python3
"""Smoke-test both DFRM bench levels with a desktop debug-bridge build."""
import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from debug_bridge_client import BridgeClient


def run(binary, out, merged):
    name = 'dfrm_bench_merged' if merged else 'dfrm_bench_single'
    directory = ROOT / 'wflevels' / name
    level = ROOT / 'wflevels' / (name + '-standalone.iff')
    actor = json.loads((directory / 'bench-manifest.json').read_text())['indices']['Director']
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]
    env = dict(os.environ, WF_REST_PORT='0', LD_LIBRARY_PATH=str(ROOT / 'engine/libs'))
    with (out / (name + '.log')).open('w') as log:
        process = subprocess.Popen([str(binary), '-L' + str(level), '--windowed', '--debug-port', str(port),
                                    '--debug-bind', '127.0.0.1'], cwd=ROOT, env=env,
                                   stdout=log, stderr=subprocess.STDOUT)
        client = None
        try:
            client = BridgeClient(port=port, timeout=15)
            cells = [99, 200, 247] if merged else [99, 100]
            for cell in cells:
                client.watch(actor, cell)
            samples = []
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f'{name} exited {process.returncode}')
                values = [client.mailbox_values.get((actor, cell)) for cell in cells]
                if all(value is not None for value in values):
                    samples.append(values)
                    if len(samples) >= 15:
                        break
                time.sleep(.1)
            if len(samples) < 15 or any(row[0] != 0 for row in samples):
                raise RuntimeError(f'{name}: missing samples or nonzero deformation status: {samples}')
            if max(row[1] for row in samples) - min(row[1] for row in samples) < 1:
                raise RuntimeError(f'{name}: flex did not animate: {samples}')
            # Both values are updated in the same Director tick; the watch stream
            # is asynchronous, so compare their observed ranges rather than pairs.
            if merged and max(row[2] for row in samples) - min(row[2] for row in samples) < 1:
                raise RuntimeError(f'{name}: second curve flex did not animate: {samples}')
            path = str((out / (name + '.png')).resolve())
            client.send({'op': 'screenshot', 'filename': path})
            if not client.wait_for(lambda m: m.get('op') == 'screenshot_done' and m.get('filename') == path, 8):
                raise RuntimeError(f'{name}: screenshot failed')
            (out / (name + '-samples.json')).write_text(json.dumps(samples, indent=2) + '\n')
        finally:
            if client:
                client.close()
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--binary', type=Path, default=ROOT / 'engine/wf_game')
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for merged in (False, True):
        run(args.binary.resolve(), args.out.resolve(), merged)


if __name__ == '__main__':
    main()
