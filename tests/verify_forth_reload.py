#!/usr/bin/env python3
"""Check commented script hot reload in the built engine, then restore its actor."""
from pathlib import Path
import verify_condo_unit_teleport as h
h.PORT=7801
h.WORK=Path('/tmp/forth-comments-runtime')
with h.game('reload-comments') as (cli,player):
    cli.watch(1,150)
    # Initial loading already compiled the unstripped camera script.
    cli.watch(1,110)
    assert h.wait(lambda:h.value(cli,1,110)==1)
    h.check('initial commented camera source loads',h.value(cli,1,110)==1)
    cases=[
        '\\ wf\n: answer ( ; is not code ) 41 ; answer 1 + 150 write-mailbox \\ tail ;',
        ': answer 42 ; answer 150 write-mailbox \\',
        '\\ a normal comment ;\n43 150 write-mailbox',
        '\\ wf\r\n\\\r\n44 150 write-mailbox',
    ]
    for i,source in enumerate(cases):
        cli.send({'op':'reload_script','idx':player,'source':source})
        assert cli.wait_for(lambda m:m.get('op')=='script_reloaded',timeout=5),f'case {i} did not compile'
        expected=42 if i<2 else 41+i
        h.check(f'reload case {i}',h.wait(lambda:h.value(cli,1,150)==expected))
    cli.revert_all()
    assert h.wait(lambda:h.value(cli,1,110)==1)
    h.switch(cli,640)
    h.check('original actor script restored',h.value(cli,1,81)==640)
print('RESULT:', 'PASS' if not h.failures else h.failures)
raise SystemExit(bool(h.failures))
