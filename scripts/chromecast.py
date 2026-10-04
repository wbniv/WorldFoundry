#!/usr/bin/env python3
"""Task client and protected Chromecast service entry point."""
import argparse
import json
import sys
from pathlib import Path

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['serve','worker','task','hook'])
    parser.add_argument('operation',nargs='?')
    parser.add_argument('--config')
    parser.add_argument('--job')
    parser.add_argument('--setup-stdin',action='store_true')
    args=parser.parse_args()
    if args.command in {'serve','worker'}:
        if not args.config:
            parser.error('--config is required')
        config=json.loads(Path(args.config).read_text())
        config['_path']=str(Path(args.config).resolve())
        if args.command=='serve':
            from wf_device.service import serve
            serve(config)
        else:
            from wf_device.workflows import execute
            setup=json.loads(sys.stdin.readline()) if args.setup_stdin else {}
            execute(config['state'],args.job,config,setup)
        return 0
    if args.command=='task':
        from wf_device.client import task_command
        return task_command(args.operation)
    if args.command=='hook':
        from wf_device.integration import hook
        return hook()

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print('Detached; submitted jobs retain their ownership and cleanup policy.',file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print('chromecast: '+str(exc),file=sys.stderr)
        raise SystemExit(1)
