"""Durable queue, per-device generations, ownership and authenticated sessions."""
import contextlib
import hashlib
import json
import secrets
import sqlite3
import time
from pathlib import Path

TERMINAL = {'completed', 'failed', 'cancelled', 'recovery-required', 'needs-local-setup', 'superseded'}


def selection(value):
    """Normalize a Task DEVICE value; resolve 'all' only at the service."""
    if isinstance(value, str):
        values = value.split(',')
    elif isinstance(value, list):
        values = value
    else:
        raise ValueError('DEVICE must contain device IDs or all')
    if not values or any(not isinstance(v, str) or not v.strip() for v in values):
        raise ValueError('Empty DEVICE entry')
    values = list(dict.fromkeys(v.strip() for v in values))
    if 'all' in values and values != ['all']:
        raise ValueError('Cannot combine all with device IDs')
    return values

class Store:
    def __init__(self, root, registry=None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        for name in ('inputs', 'evidence', 'locks'):
            (self.root/name).mkdir(exist_ok=True)
        with self.db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS devices(id TEXT PRIMARY KEY, data TEXT NOT NULL,
              health TEXT NOT NULL, generation INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, uid INTEGER NOT NULL,
              token_hash TEXT NOT NULL, label TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS reservations(device TEXT PRIMARY KEY REFERENCES devices(id),
              owner TEXT NOT NULL REFERENCES sessions(id), reason TEXT NOT NULL, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, owner TEXT NOT NULL,
              accepted REAL NOT NULL, state TEXT NOT NULL, phase TEXT NOT NULL,
              request TEXT NOT NULL, device TEXT, generation INTEGER, cancel INTEGER DEFAULT 0,
              error TEXT, started REAL, finished REAL, worker_pid INTEGER, recovery_resolved INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT,
              time REAL NOT NULL, job TEXT, kind TEXT NOT NULL, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY, sender TEXT NOT NULL,
              recipient TEXT NOT NULL, job TEXT NOT NULL, text TEXT NOT NULL,
              created REAL NOT NULL, acknowledged REAL);
            CREATE TABLE IF NOT EXISTS maintenance(id INTEGER PRIMARY KEY CHECK(id=1),
              reason TEXT NOT NULL, started REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS batches(id TEXT PRIMARY KEY, owner TEXT NOT NULL,
              token TEXT NOT NULL, request TEXT NOT NULL, targets TEXT NOT NULL, created REAL NOT NULL,
              UNIQUE(owner,token));
            CREATE TABLE IF NOT EXISTS batch_jobs(batch TEXT NOT NULL REFERENCES batches(id),
              job TEXT NOT NULL REFERENCES jobs(id), device TEXT NOT NULL, PRIMARY KEY(batch,device));
            ''')
            if 'recovery_resolved' not in {row[1] for row in db.execute('PRAGMA table_info(jobs)')}:
                db.execute('ALTER TABLE jobs ADD COLUMN recovery_resolved INTEGER DEFAULT 0')
            if 'installation' not in {row[1] for row in db.execute('PRAGMA table_info(jobs)')}:
                db.execute('ALTER TABLE jobs ADD COLUMN installation TEXT')
            for device in registry or []:
                db.execute('INSERT OR IGNORE INTO devices(id,data,health) VALUES(?,?,?)',
                           (device['id'], json.dumps(device), device.get('health', 'offline')))

    @contextlib.contextmanager
    def db(self):
        db = sqlite3.connect(self.root/'coordinator.sqlite3', timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA busy_timeout=10000')
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def event(db, job, kind, data):
        db.execute('INSERT INTO events(time,job,kind,data) VALUES(?,?,?,?)',
                   (time.time(), job, kind, json.dumps(data)))

    def register(self, uid, label):
        if not isinstance(label, str) or not 1 <= len(label) <= 120:
            raise ValueError('Session label must contain 1..120 characters')
        sid, token = secrets.token_hex(12), secrets.token_urlsafe(32)
        with self.db() as db:
            db.execute('INSERT INTO sessions VALUES(?,?,?,?)',
                       (sid, uid, hashlib.sha256(token.encode()).hexdigest(), label))
        return {'session': sid, 'token': token}

    def authenticate(self, uid, credentials):
        with self.db() as db:
            row = db.execute('SELECT * FROM sessions WHERE id=?',
                             (credentials.get('session'),)).fetchone()
        supplied = hashlib.sha256(str(credentials.get('token', '')).encode()).hexdigest()
        if not row or row['uid'] != uid or not secrets.compare_digest(row['token_hash'], supplied):
            raise PermissionError('Invalid session credentials')
        return row['id']

    def devices(self):
        with self.db() as db:
            rows = db.execute('SELECT * FROM devices ORDER BY id').fetchall()
            reservations = {r['device']: dict(r) for r in db.execute('''
              SELECT r.*,s.label,CASE WHEN EXISTS(SELECT 1 FROM jobs j
                WHERE j.device=r.device AND j.state='running') THEN 'waiting-for-cleanup'
                ELSE 'reserved' END AS state
              FROM reservations r JOIN sessions s ON s.id=r.owner''')}
        return [dict(json.loads(r['data']), health=r['health'], generation=r['generation'],
                     reservation=reservations.get(r['id'])) for r in rows]

    def reserve(self, owner, device, reason='Personal use'):
        if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 200:
            raise ValueError('Reservation reason must contain 1..200 characters')
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM devices WHERE id=?', (device,)).fetchone():
                raise ValueError('Unknown device')
            current = db.execute('SELECT * FROM reservations WHERE device=?', (device,)).fetchone()
            if current and current['owner'] != owner:
                raise PermissionError('Device is already reserved by another authenticated owner')
            db.execute('''INSERT INTO reservations VALUES(?,?,?,?)
              ON CONFLICT(device) DO UPDATE SET reason=excluded.reason''',
                       (device, owner, reason.strip(), time.time()))
            self.event(db, None, 'device-reserved', {'device': device, 'reason': reason.strip()})
        return next(d['reservation'] for d in self.devices() if d['id'] == device)

    def release(self, owner, device):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM devices WHERE id=?', (device,)).fetchone():
                raise ValueError('Unknown device')
            current = db.execute('SELECT * FROM reservations WHERE device=?', (device,)).fetchone()
            if current and current['owner'] != owner:
                raise PermissionError('Only the authenticated reservation owner can release it')
            if current:
                db.execute('DELETE FROM reservations WHERE device=?', (device,))
                self.event(db, None, 'device-released', {'device': device})
        return {'device': device, 'released': bool(current)}

    @staticmethod
    def eligible(request, device):
        if request.get('device') and request['device'] != device['id']:
            return False
        if request.get('pool') and request['pool'] not in device.get('pools', []):
            return False
        if request.get('require_abi') and request['require_abi'] not in device.get('abis', []):
            return False
        return device.get('enrolled', True)

    def submit(self, owner, request):
        if not any(self.eligible(request, d) for d in self.devices()):
            raise ValueError('No compatible enrolled device matches this selector')
        jid = 'J-' + secrets.token_hex(6)
        with self.db() as db:
            db.execute('INSERT INTO jobs(id,owner,accepted,state,phase,request) VALUES(?,?,?,?,?,?)',
                       (jid, owner, time.time(), 'queued', 'queued', json.dumps(request)))
            self.event(db, jid, 'accepted', request)
        return self.job(jid)

    @staticmethod
    def resolve_targets(db, value):
        targets = selection(value)
        known = [r[0] for r in db.execute('SELECT id FROM devices ORDER BY id')]
        if targets == ['all']:
            targets = known
        if not targets or any(d not in known for d in targets):
            raise ValueError('Unknown or empty device selection')
        return targets

    def submit_batch(self, owner, targets, request, token):
        if not isinstance(token, str) or not 1 <= len(token) <= 128:
            raise ValueError('Batch requires a request token')
        canonical = json.dumps({'targets': selection(targets), 'request': request}, sort_keys=True)
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT * FROM batches WHERE owner=? AND token=?', (owner, token)).fetchone()
            if old:
                if old['request'] != canonical:
                    raise ValueError('Batch token reused with a different request')
                bid = old['id']
            else:
                resolved = self.resolve_targets(db, targets)
                requests = []
                for did in resolved:
                    req = dict(request, device=did)
                    data = json.loads(db.execute('SELECT data FROM devices WHERE id=?', (did,)).fetchone()[0])
                    if not self.eligible(req, data):
                        raise ValueError('No compatible enrolled device: ' + did)
                    requests.append(req)
                bid = 'B-' + secrets.token_hex(6)
                db.execute('INSERT INTO batches VALUES(?,?,?,?,?,?)',
                           (bid, owner, token, canonical, json.dumps(resolved), time.time()))
                for did, req in zip(resolved, requests):
                    jid = 'J-' + secrets.token_hex(6)
                    health = db.execute('SELECT health FROM devices WHERE id=?', (did,)).fetchone()[0]
                    state = 'needs-local-setup' if health!='ready' and req['workflow']!='readd' else 'queued'
                    db.execute('INSERT INTO jobs(id,owner,accepted,state,phase,request) VALUES(?,?,?,?,?,?)',
                               (jid, owner, time.time(), state, state, json.dumps(req)))
                    if state!='queued':
                        db.execute('UPDATE jobs SET error=?,finished=? WHERE id=?',
                                   ('Device '+did+' is '+health+'; run readd before retrying', time.time(), jid))
                    db.execute('INSERT INTO batch_jobs VALUES(?,?,?)', (bid, jid, did))
                    self.event(db, jid, 'accepted', dict(req, batch=bid))
                self.event(db, None, 'batch-accepted', {'batch': bid, 'targets': resolved})
        return self.batch(bid)

    def batch(self, bid):
        with self.db() as db:
            row = db.execute('SELECT * FROM batches WHERE id=?', (bid,)).fetchone()
            if not row:
                raise ValueError('Unknown batch')
            children = list(db.execute('SELECT job,device FROM batch_jobs WHERE batch=? ORDER BY rowid', (bid,)))
        jobs = [dict(self.job(r['job']), target=r['device']) for r in children]
        terminal = all(j['state'] in TERMINAL for j in jobs)
        return {'id': bid, 'owner': row['owner'], 'targets': json.loads(row['targets']),
                'created': row['created'], 'jobs': jobs,
                'state': ('completed' if all(j['state'] == 'completed' for j in jobs) else 'failed') if terminal else 'pending'}

    def reserve_many(self, owner, targets, reason=None):
        if reason is not None and (not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 200):
            raise ValueError('Reservation reason must contain 1..200 characters')
        results = []
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            resolved = self.resolve_targets(db, targets)
            for did in resolved:
                current = db.execute('SELECT * FROM reservations WHERE device=?', (did,)).fetchone()
                if current and current['owner'] != owner:
                    raise PermissionError('Reservation belongs to another owner: ' + did)
            for did in resolved:
                current = db.execute('SELECT * FROM reservations WHERE device=?', (did,)).fetchone()
                if reason is None:
                    db.execute('DELETE FROM reservations WHERE device=?', (did,))
                    results.append({'device': did, 'released': bool(current)})
                    self.event(db, None, 'device-released', {'device': did})
                else:
                    db.execute('INSERT INTO reservations VALUES(?,?,?,?) ON CONFLICT(device) DO UPDATE SET reason=excluded.reason',
                               (did, owner, reason.strip(), time.time()))
                    running = db.execute("SELECT 1 FROM jobs WHERE device=? AND state='running'", (did,)).fetchone()
                    results.append({'device': did, 'reason': reason.strip(), 'state': 'waiting-for-cleanup' if running else 'reserved'})
                    self.event(db, None, 'device-reserved', {'device': did, 'reason': reason.strip()})
        return results

    def cancel_batch(self, owner, bid):
        batch = self.batch(bid)
        if batch['owner'] != owner:
            raise PermissionError('Only the authenticated batch owner can cancel it')
        for job in batch['jobs']:
            self.cancel(owner, job['id'])
        return self.batch(bid)

    def installed(self, jid, apk):
        with self.db() as db:
            db.execute('UPDATE jobs SET installation=? WHERE id=?', (apk, jid))
            self.event(db, jid, 'apk-installed', {'apk': apk, 'launcher': 'pending'})

    def defer_launcher(self, jid):
        with self.db() as db:
            row = db.execute('SELECT * FROM jobs WHERE id=?', (jid,)).fetchone()
            req = dict(json.loads(row['request']), device=row['device'])
            req.pop('pool', None)
            if row['cancel']:
                db.execute("UPDATE jobs SET state='cancelled',phase='cancelled',error='APK installed; launcher unverified',finished=? WHERE id=?", (time.time(), jid))
            else:
                db.execute("UPDATE jobs SET state='queued',phase='launcher-verification-pending',request=?,worker_pid=NULL WHERE id=?", (json.dumps(req), jid))
                self.event(db, jid, 'launcher-verification-pending', {'device': row['device'], 'apk': row['installation']})

    def job(self, jid):
        with self.db() as db:
            row = db.execute('SELECT * FROM jobs WHERE id=?', (jid,)).fetchone()
        if not row:
            raise ValueError('Unknown job')
        result = dict(row)
        result['request'] = json.loads(result['request'])
        return result

    def claim(self, exclude=()):
        grants = []
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM maintenance WHERE id=1').fetchone():
                return []
            busy = {r[0] for r in db.execute("SELECT device FROM jobs WHERE state='running'")}
            reserved = {r[0] for r in db.execute('SELECT device FROM reservations')}
            waiting = list(db.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY rowid"))
            devices = list(db.execute('SELECT * FROM devices ORDER BY id'))
            for row in waiting:
                if row['id'] in exclude:
                    continue
                req = json.loads(row['request'])
                candidates = [d for d in devices if d['id'] not in busy
                              and (d['id'] not in reserved or (req['workflow'] == 'install' and not row['installation']))
                              and self.eligible(req, json.loads(d['data']))
                              and (d['health'] == 'ready' or req['workflow'] == 'readd')]
                if not candidates:
                    continue
                d = candidates[0]
                generation = d['generation'] + 1
                db.execute('UPDATE devices SET generation=? WHERE id=?', (generation, d['id']))
                db.execute("UPDATE jobs SET state='running',phase='granted',device=?,generation=?,started=? WHERE id=?",
                           (d['id'], generation, time.time(), row['id']))
                self.event(db, row['id'], 'granted', {'device': d['id'], 'generation': generation})
                busy.add(d['id'])
                grants.append(row['id'])
        return grants

    def validate_lease(self, jid, device, generation):
        job = self.job(jid)
        if job['state'] != 'running' or job['device'] != device or job['generation'] != generation:
            raise PermissionError('Stale or cross-device lease')
        with self.db() as db:
            current = db.execute('SELECT generation FROM devices WHERE id=?', (device,)).fetchone()
        if not current or current[0] != generation:
            raise PermissionError('Generation no longer owns this device')
        return job

    def phase(self, jid, phase):
        with self.db() as db:
            db.execute('UPDATE jobs SET phase=? WHERE id=?', (phase, jid))
            self.event(db, jid, 'phase', {'phase': phase})

    def finish(self, jid, state, error=None, health='ready'):
        with self.db() as db:
            row = db.execute('SELECT device FROM jobs WHERE id=?', (jid,)).fetchone()
            db.execute('UPDATE jobs SET state=?,phase=?,error=?,finished=? WHERE id=?',
                       (state, state, error, time.time(), jid))
            if row and row['device']:
                db.execute('UPDATE devices SET health=? WHERE id=?', (health, row['device']))
            self.event(db, jid, state, {'error': error, 'health': health})

    def update_device(self, did, data):
        with self.db() as db:
            db.execute('UPDATE devices SET data=? WHERE id=?', (json.dumps(data), did))

    def cancel(self, owner, jid):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM jobs WHERE id=?', (jid,)).fetchone()
            if not row or row['owner'] != owner:
                raise PermissionError('Only this job\'s authenticated owner can cancel it')
            if row['state'] == 'queued':
                db.execute("UPDATE jobs SET cancel=1,state='cancelled',phase='cancelled',finished=? WHERE id=?",
                           (time.time(), jid))
                if row['installation']:
                    db.execute("UPDATE jobs SET error='APK installed; launcher unverified' WHERE id=?", (jid,))
                self.event(db, jid, 'cancelled', {'before_grant': True})
            elif row['state'] == 'running':
                db.execute('UPDATE jobs SET cancel=1 WHERE id=?', (jid,))
                self.event(db, jid, 'cancel-requested', {})
        return self.job(jid)

    def snapshot(self, device=None, pool=None):
        devices = [d for d in self.devices() if (not device or d['id'] == device)
                   and (not pool or pool in d.get('pools', []))]
        with self.db() as db:
            rows = db.execute("SELECT j.*,s.label FROM jobs j JOIN sessions s ON s.id=j.owner WHERE state IN ('queued','running') ORDER BY j.rowid").fetchall()
            revision = db.execute('SELECT COALESCE(MAX(seq),0) FROM events').fetchone()[0]
        jobs = []
        for row in rows:
            r = dict(row); r['request'] = json.loads(r['request'])
            r['eligible'] = [d['id'] for d in devices if self.eligible(r['request'], d)]
            if r['eligible'] or r['device'] in {d['id'] for d in devices}:
                jobs.append(r)
        with self.db() as db:
            maintenance = db.execute('SELECT reason,started FROM maintenance WHERE id=1').fetchone()
            batch_rows = list(db.execute('SELECT DISTINCT b.id FROM batches b JOIN batch_jobs bj ON bj.batch=b.id JOIN jobs j ON j.id=bj.job WHERE j.state NOT IN (?,?,?,?,?,?)', tuple(sorted(TERMINAL))))
        return {'time': time.time(), 'revision': revision, 'devices': devices, 'jobs': jobs,
                'maintenance': dict(maintenance) if maintenance else None,
                'batches': [self.batch(r[0]) for r in batch_rows]}

    def events(self, cursor=0, jid=None):
        with self.db() as db:
            rows = db.execute('SELECT * FROM events WHERE seq>? AND (? IS NULL OR job=?) ORDER BY seq LIMIT 500',
                              (cursor, jid, jid)).fetchall()
        return [dict(dict(r), data=json.loads(r['data'])) for r in rows]

    def message(self, owner, jid, text):
        job = self.job(jid)
        if not isinstance(text, str) or not 1 <= len(text) <= 2000:
            raise ValueError('Message must contain 1..2000 characters')
        mid = 'MSG-' + secrets.token_hex(6)
        with self.db() as db:
            db.execute('INSERT INTO messages VALUES(?,?,?,?,?,?,NULL)',
                       (mid, owner, job['owner'], jid, text, time.time()))
            self.event(db, jid, 'message-accepted', {'id': mid})
        return {'id': mid, 'delivery': 'pending-acknowledgement'}

    def inbox(self, owner):
        with self.db() as db:
            return [dict(r) for r in db.execute('SELECT m.*,s.label AS sender_label FROM messages m JOIN sessions s ON s.id=m.sender WHERE recipient=? AND acknowledged IS NULL ORDER BY created', (owner,))]

    def acknowledge(self, owner, ids):
        with self.db() as db:
            for mid in ids:
                row = db.execute('SELECT * FROM messages WHERE id=? AND recipient=?', (mid, owner)).fetchone()
                if row and row['acknowledged'] is None:
                    db.execute('UPDATE messages SET acknowledged=? WHERE id=?', (time.time(), mid))
                    self.event(db, row['job'], 'message-delivered', {'id': mid})
        return {'acknowledged': ids}
