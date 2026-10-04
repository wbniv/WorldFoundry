"""Generate editable SVG diagrams of the proposed coordinator mechanics."""
from pathlib import Path
from html import escape

HERE=Path(__file__).resolve().parent
INK='#183642'; TEAL='#197c79'; BLUE='#4265a5'; PALE='#d9e6ed'; AMBER='#f4e6c8'; RED='#a04440'

class Diagram:
    def __init__(self,title,subtitle,height):
        self.height=height
        self.parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="1040" height="{height}" viewBox="0 0 1040 {height}"><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10Z" fill="#367b82"/></marker></defs><rect width="1040" height="{height}" rx="12" fill="#eff5f7"/>']
        self.text(24,34,title,22,bold=True)
        self.text(24,61,subtitle,15)
    def text(self,x,y,text,size=16,color=INK,bold=False,anchor='start'):
        self.parts.append(f'<text x="{x}" y="{y}" font-family="system-ui,sans-serif" font-size="{size}" font-weight="{700 if bold else 400}" fill="{color}" text-anchor="{anchor}">{escape(text)}</text>')
    def box(self,x,y,w,h,title,lines=(),fill=PALE):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill}"/>')
        color='white' if fill in (TEAL,BLUE) else INK
        self.text(x+16,y+29,title,18,color,True)
        for i,line in enumerate(lines):self.text(x+16,y+55+i*23,line,15,color)
    def arrow(self,points,label=None,lx=None,ly=None):
        d='M'+' L'.join(f'{x} {y}' for x,y in points)
        self.parts.append(f'<path d="{d}" fill="none" stroke="#367b82" stroke-width="2" marker-end="url(#arrow)"/>')
        if label:self.text(lx,ly,label,15)
    def line(self,x1,y1,x2,y2):
        self.parts.append(f'<path d="M{x1} {y1}L{x2} {y2}" stroke="#a7bcc7" stroke-dasharray="5 5"/>')
    def save(self,name):
        (HERE/name).write_text(''.join(self.parts)+'</svg>')

# Sequence: second caller queues while the first holds all device work.
d=Diagram('Job submission and handoff','Proposed sequence · every device command belongs to one complete owned job.',670)
for x,title,fill in [(35,'Agent A',PALE),(285,'Coordinator',TEAL),(535,'Device worker',BLUE),(785,'Agent B',PALE)]:
    d.box(x,85,210,52,title,fill=fill);d.line(x+105,138,x+105,600)
d.arrow([(140,175),(390,175)],'Submit frozen test',165,164)
d.arrow([(390,223),(640,223)],'Grant lease + generation',402,211)
d.arrow([(890,270),(390,270)],'Submit second job → FIFO queue',523,258)
d.arrow([(390,315),(890,315)],'Queued: owner A; phase / messages',481,303)
d.box(525,350,230,94,'Owned device work',['Install → warmup → capture','Then cleanup / restoration'],BLUE)
d.arrow([(640,474),(390,474)],'Result + cleanup finished',418,462)
d.arrow([(390,515),(140,515)],'Receipt; job complete',167,503)
d.arrow([(390,559),(640,559)],'Now grant next queued job',410,547)
d.arrow([(390,596),(890,596)],'Agent B: your job started',538,584)
d.text(24,642,'Client polling, agent pauses and messages never release an active worker session.',16,bold=True)
d.save('job-handoff-sequence.svg')

# Message path: identity-bound recipients plus event acknowledgements.
d=Diagram('Agent messages and service events','Proposed delivery · coordination messages do not change ownership or priority.',535)
d.box(24,101,250,130,'Waiting agent',['Registered caller/session','Sends task-scoped message','Continues independent work'])
d.box(387,101,280,154,'Service mailbox',['Authenticate sender + recipient','Store event ID and job/resource','Cursor + acknowledgement'],TEAL)
d.box(780,101,236,130,'Current owner',['Receives waiting request','Replies with phase / estimate','Keeps lease until cleanup'])
d.arrow([(275,165),(385,165)],'Send',304,152)
d.arrow([(668,165),(778,165)],'Deliver',691,152)
d.arrow([(895,232),(895,279),(529,279),(529,256)],'Reply / ack',677,269)
d.box(24,338,295,115,'Verified notification bridge',['Deliver into supported harness','Or expose watch / polling'])
d.box(387,338,280,115,'Events and status',['Queued → started → released','Durable reconnect cursor'],TEAL)
d.box(780,338,236,115,'Dashboard / CLI',['Owner + FIFO queue','Messages + recent handoffs'])
d.arrow([(529,280),(529,336)])
d.arrow([(386,390),(321,390)])
d.arrow([(668,390),(778,390)])
d.text(24,493,'At-least-once delivery + event IDs prevent duplicate logical messages after reconnect.',16)
d.text(24,518,'No claim of waking a paused model until the harness integration is demonstrated.',15)
d.save('agent-message-delivery.svg')

# Commands are actually executed only on the protected side, including indirect clients.
d=Diagram('Access enforcement: two paths, one allowed route','Proposed boundary · a missed instruction must not grant direct device access.',580)
d.box(24,104,285,134,'Task / agent tool call',['Shell / Python / API / scripts','Agent may miss AGENTS.md','Service request or direct client'])
d.box(400,104,268,134,'Runtime hooks / policies',['Allow scoped coordinator calls','Deny known direct ADB routes','Do not wait inside a hook'],AMBER)
d.arrow([(310,169),(398,169)])
d.box(760,104,256,134,'Coordinator API',['Authenticate + validate job','FIFO queue / active generation','Reviewed device adapter'],TEAL)
d.arrow([(670,169),(758,169)])
d.box(760,316,256,134,'Protected device access',['Service identity + private ADB','Credentials / network boundary','Then Chromecast'],BLUE)
d.arrow([(888,239),(888,314)],'Owned command only',699,280)
d.box(24,316,390,134,'Attempted bypass',['Alternate adb / indirect subprocess / raw TCP','Hooks may not recognize every route','OS / sandbox policy blocks device access'],AMBER)
d.arrow([(141,239),(141,314)])
d.parts.append('<path d="M416 386H734" stroke="#a04440" stroke-width="2" stroke-dasharray="6 4"/><path d="M726 374L746 396M746 374L726 396" stroke="#a04440" stroke-width="4"/>')
d.text(446,371,'DENIED outside service identity',16,RED,True)
d.text(24,507,'Verify sandboxed and escalated paths. Protect the private ADB server and service files too.',16)
d.text(24,539,'Broken hooks cannot enable a bypass; an unavailable service never falls back to raw ADB.',16,bold=True)
d.save('device-access-enforcement.svg')

# Lifecycle and crash gate: no new job while old commands might continue.
d=Diagram('Job lifecycle and crash recovery','Proposed state flow · timeout or old heartbeat never transfers ownership.',595)
d.box(24,103,172,70,'Queued',['No device access'])
d.box(251,103,172,70,'Starting',['Grant generation'])
d.box(478,103,172,70,'Running',['Owned commands'],TEAL)
d.box(705,103,172,70,'Cleaning',['Drain + restore'],BLUE)
for a,b in [(196,251),(423,478),(650,705)]:d.arrow([(a,138),(b-2,138)])
d.box(705,236,285,90,'Terminal result',['Completed / failed / cancelled','Only after safe cleanup'])
d.arrow([(791,174),(791,234)])
d.box(24,278,260,140,'Recovery gate',['Coordinator / worker lost','Fence old-generation requests','Reconcile journal + processes','Retain device exclusion'],AMBER)
d.arrow([(565,174),(565,247),(154,247),(154,276)],'Unexpected interruption',277,234)
d.box(382,319,264,99,'Reconcile and drain',['Prove old commands have ended','Check device-side operations'],TEAL)
d.arrow([(285,367),(380,367)])
d.box(751,369,264,106,'Safe handoff',['Finalize interrupted receipt','Then grant next FIFO job','Or stay blocked if uncertain'],BLUE)
d.arrow([(648,369),(696,369),(696,422),(749,422)])
d.arrow([(849,328),(849,367)])
d.text(24,502,'A free host lock alone is insufficient if a recording or other device-side operation survives.',16)
d.text(24,540,'Cancel a waiter: remove it. Cancel an owner: stop/drain, clean up, then hand off.',16,bold=True)
d.text(24,570,'Never unlink a busy lock or kill unrelated ADB servers to force a grant.',16)
d.save('job-lifecycle-recovery.svg')

# Independent physical devices receive separate owned sessions.
d=Diagram('Multiple Chromecasts: parallel jobs, exclusive access per device','Proposed registry and scheduler · an occupied Chromecast does not stop work on another.',535)
d.box(24,111,244,145,'Task / agent requests',['Fixed device: test-01','Pool: compatible Chromecast','Frozen inputs + capabilities'])
d.box(376,111,281,145,'One coordinator service',['Atomic compatible assignment','FIFO among eligible requests','No global device-test mutex'],TEAL)
d.arrow([(270,177),(374,177)])
d.box(775,90,241,120,'chromecast-test-01',['Owner: Jellyfish capture','Condo request waits for 01'],BLUE)
d.box(775,248,241,120,'chromecast-test-02',['Owner: Planted-tank profile','Runs concurrently with 01'],TEAL)
d.arrow([(658,160),(723,160),(723,149),(773,149)])
d.arrow([(658,213),(723,213),(723,309),(773,309)])
d.box(24,346,244,110,'Per-device identity',['Model / ABI / OS / pool tags','Endpoint aliases → one ID'])
d.box(376,346,281,110,'Per-device ownership',['Lease + generation + lock','Health / recovery / evidence'])
d.text(24,494,'Fixed-device and pool jobs arbitrate together; incompatible or offline hardware is not silently selected.',15)
d.text(24,520,'A lease for 01 cannot control 02. Recovery of 01 does not cancel a valid job on 02.',16,bold=True)
d.save('multi-device-scheduling.svg')
