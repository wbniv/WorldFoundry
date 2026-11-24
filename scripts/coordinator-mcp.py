#!/usr/bin/env python3
"""World Foundry artifact preparation and installed coordinator MCP entry point."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'build/coordinator-artifacts'
LAUNCHER = Path('/opt/wf-device-coordinator/bin/chromecast-coordinator-mcp')


def freeze(source, artifacts=ARTIFACTS):
    source = source.resolve(strict=True)
    data = source.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
        raise ValueError('APK changed while freezing; finish the build first')
    artifacts.mkdir(parents=True, exist_ok=True)
    target = artifacts / (digest + '.apk')
    try:
        with target.open('xb') as output:
            output.write(data)
    except FileExistsError:
        if target.is_symlink() or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError('Existing frozen artifact differs; refusing overwrite')
    return {'apk': str(target), 'sha256': digest, 'size': len(data),
            'source': str(source), 'built_by_this_command': False}


def launch_command(host):
    if not LAUNCHER.is_file():
        raise RuntimeError('Install the shared coordinator; no device-control fallback')
    state = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state')))
    identity = state / 'worldfoundry/coordinator-mcp' / host
    identity.mkdir(parents=True, exist_ok=True, mode=0o700)
    if identity.stat().st_uid != os.getuid() or identity.stat().st_mode & 0o077:
        raise ValueError('MCP identity directory must be private (0700) and owned by you')
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    return [str(LAUNCHER), '--session-file', str(identity / 'session.json'),
            '--file-root', str(ARTIFACTS)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='operation', required=True)
    prepare = commands.add_parser('freeze')
    prepare.add_argument('apk', type=Path)
    serve = commands.add_parser('serve')
    serve.add_argument('--host', required=True, choices=['claude', 'codex', 'ci'])
    args = parser.parse_args()
    os.umask(0o077)
    if args.operation == 'freeze':
        print(json.dumps(freeze(args.apk), indent=2))
    else:
        command = launch_command(args.host)
        os.execv(command[0], command)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        print('coordinator-mcp: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
