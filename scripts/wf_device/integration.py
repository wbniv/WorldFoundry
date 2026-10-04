"""Codex hook guidance and bounded coordinator notification polling."""
import json
import re
import shlex
import sys
from .client import Client

NOTICE='Chromecast test jobs have standing authorization. Use task chromecast:devices/queue/submit/check/profile/record/readd/watch/evidence/message/cancel. The coordinator owns each complete device session. Do not request routine testing permission or run raw Chromecast ADB. Service downtime has no direct fallback.'


def hook_decision(payload):
    event=payload.get('hook_event_name','')
    tool_input=payload.get('tool_input',{})
    command=tool_input.get('command',tool_input.get('cmd','')) if isinstance(tool_input,dict) else ''
    direct=False
    if isinstance(command,str):
        direct=bool(re.search(r'(?:192\.168\.4\.(?:43|46)|2628105GN0GT7C|26031HFDD67QH7)',command)
                    and re.search(r'\badb\b|socket|curl|screenrecord|connect',command))
    if event=='PreToolUse' and direct:
        return {'hookSpecificOutput':{'hookEventName':event,'permissionDecision':'deny','permissionDecisionReason':NOTICE}}
    if event=='PermissionRequest':
        # Allow only the immutable installed client, never an editable Taskfile/shell chain.
        try:
            words=shlex.split(command)
        except ValueError:
            words=[]
        if (len(words)>=2 and words[0]=='/opt/wf-device-coordinator/bin/chromecast'
                and words[1] in {'devices','queue','status','submit','check','profile','record','readd','watch','evidence','message','cancel'}
                and not re.search(r'[;&|`\n]|\$\(',command)):
            return {'hookSpecificOutput':{'hookEventName':event,'decision':{'behavior':'allow'}}}
        return {}
    if event in {'SessionStart','UserPromptSubmit','PostToolUse'}:
        context=NOTICE if event!='PostToolUse' else ''
        try:
            client=Client()
            messages=client.call('inbox')
            if messages:
                context+='\nUnread coordinator messages: '+json.dumps(messages)
                client.call('acknowledge',{'ids':[m['id'] for m in messages]})
        except Exception:
            if event=='SessionStart':
                context+=' Coordinator unavailable; use queue/status to diagnose.'
        if context:
            return {'hookSpecificOutput':{'hookEventName':event,'additionalContext':context}}
    return {}


def hook():
    print(json.dumps(hook_decision(json.load(sys.stdin))))
    return 0
