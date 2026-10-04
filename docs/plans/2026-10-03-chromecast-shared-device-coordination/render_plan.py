"""Render the review plan with embedded local diagrams and a status mockup."""
from pathlib import Path
import base64
import re
import markdown

HERE=Path(__file__).resolve().parent
PLAN=HERE.parent/(HERE.name+'.md')
HTML=PLAN.with_suffix('.html')
css=(HERE/'plan.css').read_text()
body=markdown.markdown(PLAN.read_text(),extensions=['tables','fenced_code','toc'])
def embed(match):
    path=PLAN.parent/match.group(1)
    mime='image/svg+xml' if path.suffix=='.svg' else 'image/png'
    return 'src="data:'+mime+';base64,'+base64.b64encode(path.read_bytes()).decode()+'"'
body=re.sub(r'src="([^"]+)"',embed,body)
mock='''<div class="mock"><div class="label">PROPOSED MULTI-DEVICE DASHBOARD · ILLUSTRATIVE, NOT LIVE OR INSTALLED</div><p><code>task chromecast:queue</code> · <code>task chromecast:queue DEVICE=chromecast-test-01 WATCH=true</code></p><div class="status"><div><h3>chromecast-test-01 <span class="pill">OWNED</span></h3><p><b>Owner:</b> Jellyfish render check</p><p><b>Phase:</b> Capture after warmup</p><p><b>Waiting:</b> Condo check, eligible pool requests</p></div><div><h3>chromecast-test-02 <span class="pill">OWNED</span></h3><p><b>Owner:</b> Planted-tank profile</p><p><b>Phase:</b> Variant measurement</p><p>Independent lease; both devices run concurrently.</p></div></div><table><thead><tr><th>Waiting job</th><th>Selector / eligible devices</th><th>Reason</th></tr></thead><tbody><tr><td>Condo check</td><td>Fixed: test-01</td><td>Owner of 01 is capturing</td></tr><tr><td>School recording</td><td>Pool: test-01 or test-02</td><td>Both eligible devices busy; exact pool position is conditional</td></tr></tbody></table><div class="messages"><b>Coordination messages / events</b><p>Condo agent → owner of 01: “My capture is queued behind yours.”</p><p>Owner of 01 → waiters: “Capture finished; restoration takes two minutes.”</p><p>Service → next eligible job: “Device 01 released. Your job is starting.”</p><p><small>This is a mockup. A live view will show snapshot time/revision and label stale or disconnected data.</small></p></div></div>'''
body=body.replace('<h2 id="visibility-mockup-and-evidence">',mock+'<h2 id="visibility-mockup-and-evidence">')
HTML.write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Chromecast coordination service and enforcement plan</title><style>'+css+'</style><main><nav><a href="'+PLAN.name+'">Markdown source</a><span>Revised plan · Task interface + multi-device service + enforcement</span></nav>'+body+'</main></html>')
print(HTML.resolve())
