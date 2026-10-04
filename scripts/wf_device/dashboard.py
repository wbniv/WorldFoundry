"""Read-only loopback status view; it never performs device commands."""
import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading

PAGE='''<!doctype html><html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Chromecast queue</title><style>body{font:17px system-ui;background:#101923;color:#eef5ff;max-width:1100px;margin:40px auto;padding:20px}table{width:100%;border-collapse:collapse;margin:20px 0}td,th{padding:12px;border-bottom:1px solid #456;text-align:left}code{color:#9ed6ff}.note{color:#bdd}</style><h1>Chromecast queue</h1><p class="note">Read-only coordinator status. Refreshes every two seconds.</p><div id="status">Loading…</div><script>async function refresh(){try{let r=await fetch('/snapshot');if(!r.ok)throw Error(r.status);let x=await r.json();let escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));let row=a=>'<tr>'+a.map(s=>'<td>'+escape(s)+'</td>').join('')+'</tr>';document.getElementById('status').innerHTML='<p>Connected · '+new Date(x.time*1000).toLocaleString()+' · revision '+x.revision+'</p><p>Enforcement: '+escape(x.enforcement)+'</p><table>'+row(['Device','Health','Owner / job / phase'])+x.devices.map(d=>row([d.id,d.health,x.jobs.filter(j=>j.device===d.id&&j.state==='running').map(j=>j.label+' / '+j.id+' / '+j.phase).join(', ')||'unowned'])).join('')+'</table><table>'+row(['Waiting job','Owner','Selector','Eligible devices'])+x.jobs.filter(j=>j.state==='queued').map(j=>row([j.id,j.label,j.request.device||'pool:'+j.request.pool,j.eligible.join(', ')])).join('')+'</table><p>Pool positions depend on eligible devices and release order.</p>'}catch(e){document.getElementById('status').insertAdjacentHTML('afterbegin','<p>Disconnected: displayed data may be stale.</p>')}}refresh();setInterval(refresh,2000)</script></html>'''

def start(store,port,enforcement):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path=='/':
                data=PAGE.encode();kind='text/html; charset=utf-8'
            elif self.path=='/snapshot':
                data=json.dumps(dict(store.snapshot(),enforcement=enforcement)).encode();kind='application/json'
            else:
                self.send_error(404);return
            self.send_response(200)
            self.send_header('Content-Type',kind)
            self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.end_headers();self.wfile.write(data)
        def log_message(self,*_):pass
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    return server
