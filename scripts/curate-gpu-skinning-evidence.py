#!/usr/bin/env python3
"""Curate downloaded coordinator sessions into committable GPU skinning evidence.

For each session folder, writes deterministic gzip copies of meminfo/thermal
snapshots and of the engine log scoped from its final level-load marker,
records original and scoped log hashes in device-evidence-scope.json, and
prints the allowlisted paths to stage. Raw cumulative engine logs, system
logcat, connection details, command/watch transcripts and coordinator
diagnostics are never listed. Refuses a listed file that contains a network
endpoint, URL or PIN.

Use --print-only to list the allowlisted paths of already-curated sessions
without writing anything.
"""
import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

MARKER = b'zforth: INDEXOF_CAMSHOT = 1921 (expect 1921)'
SCOPE = 'Final level-load marker through end of captured engine log; cumulative earlier sessions excluded.'
KEEP = {'receipt.json', 'apk-installations.json', 'cleanup-apk-installations.json', 'screenshot.png',
        'summary.json', 'idle.png', 'presents-ns.json', 'samples.json', 'segments.json',
        'selected-layer.txt', 'settling-samples.json', 'README.md'}
COMPRESS = {'meminfo.txt', 'thermal.txt'}
_spec = importlib.util.spec_from_file_location('panel', Path(__file__).with_name('audit-gpu-skinning-panel.py'))
panel = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(panel)
PRIVATE = re.compile(rb'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?\b|https?://|\bpin\b', re.I)


def deterministic_gzip(data):
    return gzip.compress(data, compresslevel=9, mtime=0)


def curate(root, session, scope_entries, write):
    staged = []
    folder = root / session
    if not folder.is_dir():
        raise ValueError(f'No session folder: {folder}')
    for path in sorted(folder.rglob('*')):
        if not path.is_file() or '.history' in path.parts:
            continue
        relative = path.relative_to(root).as_posix()
        if path.name in KEEP:
            if path.suffix in {'.json', '.txt', '.md'} and PRIVATE.search(path.read_bytes()):
                raise ValueError(f'Connection detail, URL or PIN in allowlisted file: {relative}')
            if path.suffix == '.png' and panel.capture_shows_panel(path):
                # The phone-controller panel prints the LAN endpoint and pairing PIN.
                raise ValueError(f'Capture shows the phone-controller panel (endpoint and PIN): {relative}')
            staged.append(relative)
        elif path.name in COMPRESS:
            if write:
                Path(str(path) + '.gz').write_bytes(deterministic_gzip(path.read_bytes()))
            staged.append(relative + '.gz')
        elif path.name == 'wf.log':
            raw = path.read_bytes()
            marker = raw.rfind(MARKER)
            if marker < 0:
                raise ValueError(f'No final level-load marker: {relative}')
            scoped = raw[marker:]
            if PRIVATE.search(scoped):
                raise ValueError(f'Connection detail, URL or PIN in scoped engine log: {relative}')
            if write:
                Path(str(path) + '.gz').write_bytes(deterministic_gzip(scoped))
                scope_entries[relative + '.gz'] = dict(
                    path=relative + '.gz', original_sha256=hashlib.sha256(raw).hexdigest(),
                    scoped_sha256=hashlib.sha256(scoped).hexdigest(), scope=SCOPE)
            staged.append(relative + '.gz')
    return staged


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--evidence', type=Path, required=True, help='Experiment evidence root')
    parser.add_argument('--print-only', action='store_true', help='List allowlisted paths; write nothing')
    parser.add_argument('sessions', nargs='+', help='Session folders relative to --evidence')
    args = parser.parse_args()
    scope_path = args.evidence / 'device-evidence-scope.json'
    scope = json.loads(scope_path.read_text())
    entries = {entry['path']: entry for entry in scope['logs']}
    staged = []
    for session in args.sessions:
        staged += curate(args.evidence, session, entries, not args.print_only)
    if not args.print_only:
        scope['logs'] = sorted(entries.values(), key=lambda entry: entry['path'])
        temporary = scope_path.with_suffix('.json.new')
        temporary.write_text(json.dumps(scope, indent=2) + '\n')
        temporary.replace(scope_path)
        staged.append(scope_path.name)
    sys.stdout.write(''.join(path + '\n' for path in staged))


if __name__ == '__main__':
    main()
