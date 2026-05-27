// wf-relay — real-time co-editing relay server for wf-edit.
//
// Protocol (wire envelope: [1-byte channel][payload]):
//   0x01 SYNC     — Yrs v1 update bytes; relay applies to room doc + fans out
//   0x02 PRESENCE — ephemeral peer state (passthrough, not persisted)
//   0x03 CHAT     — text chat message (passthrough)
//   0x04 CONTROL  — first message after WS handshake: [0x04][room_id\0peer_id]
//
// On join:   relay sends full room state as SYNC.
// On SYNC:   relay applies update to authoritative doc, fans out to other peers.
// On PRESENCE/CHAT: relay forwards to all other peers unchanged.
//
// Usage: wf-relay [--port <PORT>] [--snapshot-dir <PATH>]   (port default: 9900)
//   --snapshot-dir: enable debounced room snapshots (N=3 rotating .ydoc files).
//
// Plan: docs/plans/2026-05-21-realtime-coediting.md Phase 1 + Phase 7

use std::collections::HashMap;
use std::net::SocketAddr;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use futures_util::{SinkExt, StreamExt};
use tokio::net::{TcpListener, TcpStream};
use tokio::sync::mpsc::{self, UnboundedSender};
use tokio_tungstenite::{accept_async, tungstenite::Message};
// yrs ≥0.10: Transact provides transact()/transact_mut(); ReadTxn provides
// encode_state_as_update_v1() (moved off Doc onto the transaction).
use yrs::{Doc, StateVector, Update, Transact, ReadTxn};
use yrs::updates::decoder::Decode;

// ── Wire protocol constants ───────────────────────────────────────────────────
//   0x01 SYNC     — Yrs v1 update bytes; relay applies + fans out
//   0x02 PRESENCE — ephemeral peer state (passthrough)
//   0x03 CHAT     — text chat (passthrough)
//   0x04 CONTROL  — first message: [0x04][room_id\0peer_id]
//   0x05 SIGNAL   — WebRTC SDP/ICE: [0x05][to_peer_id\0 json_payload]
//                   relay unicasts to `to` if non-empty, else fanout (excluding sender)

const CH_SYNC: u8     = 0x01;
const CH_PRESENCE: u8 = 0x02;
const CH_CHAT: u8     = 0x03;
const CH_CONTROL: u8  = 0x04;
const CH_SIGNAL: u8   = 0x05;

// ── Snapshot helpers ──────────────────────────────────────────────────────────

fn snapshot_path(dir: &Path, room_id: &str, epoch: u32) -> PathBuf {
    dir.join(format!("{}-{}.ydoc", room_id, epoch % 3))
}

fn load_snapshot(dir: &Path, room_id: &str) -> Option<Doc> {
    // Try all 3 slots; return the one with the newest mtime.
    let mut best: Option<(std::time::SystemTime, Vec<u8>)> = None;
    for slot in 0u32..3 {
        let path = snapshot_path(dir, room_id, slot);
        if let Ok(bytes) = std::fs::read(&path) {
            if let Ok(meta) = std::fs::metadata(&path) {
                if let Ok(mtime) = meta.modified() {
                    let newer = best.as_ref().map_or(true, |(bt, _)| mtime > *bt);
                    if newer { best = Some((mtime, bytes)); }
                }
            }
        }
    }
    let bytes = best?.1;
    let doc = Doc::new();
    if let Ok(upd) = Update::decode_v1(&bytes) {
        let mut txn = doc.transact_mut();
        let _ = txn.apply_update(upd);
    }
    eprintln!("[relay] loaded snapshot for room {room_id} ({} bytes)", bytes.len());
    Some(doc)
}

fn encode_state(doc: &Doc) -> Vec<u8> {
    doc.transact().encode_state_as_update_v1(&StateVector::default())
}

// ── Room state ────────────────────────────────────────────────────────────────

type PeerId = String;
type RoomId = String;
type PeerSender = UnboundedSender<Vec<u8>>;

struct RoomState {
    doc: Doc,
    peers: HashMap<PeerId, PeerSender>,
    // Phase 7 persistence bookkeeping.
    dirty:             bool,
    save_epoch:        u32,
    last_save:         Option<Instant>,
    peers_empty_since: Option<Instant>,
}

impl RoomState {
    fn new(doc: Doc) -> Self {
        Self {
            doc,
            peers: HashMap::new(),
            dirty: false,
            save_epoch: 0,
            last_save: None,
            peers_empty_since: None,
        }
    }

    fn full_state_sync(&self) -> Vec<u8> {
        let update = encode_state(&self.doc);
        let mut msg = vec![CH_SYNC];
        msg.extend_from_slice(&update);
        msg
    }

    fn apply_sync(&mut self, payload: &[u8]) {
        if payload.is_empty() {
            return;
        }
        let Ok(upd) = Update::decode_v1(payload) else { return; };
        let mut txn = self.doc.transact_mut();
        let _ = txn.apply_update(upd);
        self.dirty = true;
    }

    fn fanout(&self, msg: &[u8], exclude: &str) {
        for (id, tx) in &self.peers {
            if id != exclude {
                let _ = tx.send(msg.to_vec());
            }
        }
    }
}

type Rooms = Arc<Mutex<HashMap<RoomId, RoomState>>>;

// ── Snapshot saver task (Phase 7) ────────────────────────────────────────────

// Runs every 2 s; saves dirty rooms (quiet ≥ 2 s since last save, or forced
// every 10 s); evicts rooms with no peers for ≥ 60 s.
async fn snapshot_task(rooms: Rooms, dir: PathBuf) {
    let mut interval = tokio::time::interval(Duration::from_secs(2));
    loop {
        interval.tick().await;
        let now = Instant::now();

        // Collect what to save (while holding lock) then write without lock.
        let to_save: Vec<(String, Vec<u8>, u32)>;
        let to_evict: Vec<String>;
        {
            let mut lock = rooms.lock().unwrap();
            to_evict = lock
                .iter()
                .filter(|(_, r)| {
                    r.peers.is_empty()
                        && r.peers_empty_since
                            .map_or(false, |t| now.duration_since(t) >= Duration::from_secs(60))
                })
                .map(|(id, _)| id.clone())
                .collect();

            to_save = lock
                .iter_mut()
                .filter_map(|(id, room)| {
                    if !room.dirty { return None; }
                    let since_save = room.last_save
                        .map(|t| now.duration_since(t))
                        .unwrap_or(Duration::MAX);
                    if since_save < Duration::from_secs(2) { return None; }
                    let bytes = encode_state(&room.doc);
                    let epoch = room.save_epoch;
                    room.dirty = false;
                    room.save_epoch += 1;
                    room.last_save = Some(now);
                    Some((id.clone(), bytes, epoch))
                })
                .collect();

            for id in &to_evict {
                lock.remove(id);
            }
        }

        // Write snapshots without holding the lock.
        for (id, bytes, epoch) in &to_save {
            let path = snapshot_path(&dir, id, *epoch);
            match std::fs::write(&path, bytes) {
                Ok(()) => eprintln!("[relay] saved snapshot {}", path.display()),
                Err(e) => eprintln!("[relay] snapshot write error {}: {e}", path.display()),
            }
        }
        for id in &to_evict {
            eprintln!("[relay] evicted idle room {id}");
        }
    }
}

// ── Connection handler ────────────────────────────────────────────────────────

async fn handle_tcp(
    rooms: Rooms,
    snapshot_dir: Option<Arc<PathBuf>>,
    stream: TcpStream,
    addr: SocketAddr,
) {
    let ws = match accept_async(stream).await {
        Ok(ws) => ws,
        Err(e) => {
            eprintln!("[relay] WS handshake error from {addr}: {e}");
            return;
        }
    };

    let (mut ws_tx, mut ws_rx) = ws.split();

    // First message must be CONTROL: [0x04][room_id NUL peer_id]
    let (room_id, peer_id) = loop {
        match ws_rx.next().await {
            Some(Ok(Message::Binary(b))) if b.first() == Some(&CH_CONTROL) => {
                let payload = &b[1..];
                let mid = payload.iter().position(|&x| x == 0).unwrap_or(payload.len());
                let room = String::from_utf8_lossy(&payload[..mid]).into_owned();
                let peer = String::from_utf8_lossy(
                    if mid + 1 < payload.len() { &payload[mid + 1..] } else { b"anon" },
                ).into_owned();
                break (room, peer);
            }
            Some(Ok(Message::Close(_))) | None | Some(Err(_)) => return,
            _ => continue,
        }
    };

    eprintln!("[relay] {peer_id} joined room {room_id} from {addr}");

    let (send_tx, mut send_rx) = mpsc::unbounded_channel::<Vec<u8>>();

    // Register peer; create room (loading snapshot if available) if not present.
    let full_state = {
        let mut rooms_lock = rooms.lock().unwrap();
        let room = rooms_lock.entry(room_id.clone()).or_insert_with(|| {
            let doc = snapshot_dir
                .as_ref()
                .and_then(|d| load_snapshot(d, &room_id))
                .unwrap_or_else(Doc::new);
            RoomState::new(doc)
        });
        room.peers.insert(peer_id.clone(), send_tx);
        room.peers_empty_since = None;
        room.full_state_sync()
    };

    if let Err(e) = ws_tx.send(Message::Binary(full_state)).await {
        eprintln!("[relay] failed to send full state to {peer_id}: {e}");
    }

    // Outbound pump: drain send_rx → ws_tx.
    let out_task = tokio::spawn(async move {
        while let Some(msg) = send_rx.recv().await {
            if ws_tx.send(Message::Binary(msg)).await.is_err() {
                break;
            }
        }
    });

    // Inbound loop: ws_rx → relay logic.
    while let Some(msg_result) = ws_rx.next().await {
        let bytes = match msg_result {
            Ok(Message::Binary(b)) => b,
            Ok(Message::Close(_)) | Err(_) => break,
            Ok(_) => continue,
        };

        if bytes.is_empty() {
            continue;
        }

        match bytes[0] {
            CH_SYNC => {
                let mut rooms_lock = rooms.lock().unwrap();
                if let Some(room) = rooms_lock.get_mut(&room_id) {
                    room.apply_sync(&bytes[1..]);
                    room.fanout(&bytes, &peer_id);
                }
            }
            CH_PRESENCE | CH_CHAT => {
                let rooms_lock = rooms.lock().unwrap();
                if let Some(room) = rooms_lock.get(&room_id) {
                    room.fanout(&bytes, &peer_id);
                }
            }
            CH_SIGNAL => {
                // Targeted SDP/ICE signaling: payload = [to_peer_id NUL json].
                // Unicast to named peer if `to` non-empty; fanout (excl. sender) otherwise.
                let payload = &bytes[1..];
                let mid = payload.iter().position(|&x| x == 0).unwrap_or(payload.len());
                let to = String::from_utf8_lossy(&payload[..mid]).into_owned();
                let rooms_lock = rooms.lock().unwrap();
                if let Some(room) = rooms_lock.get(&room_id) {
                    if to.is_empty() {
                        room.fanout(&bytes, &peer_id);
                    } else if let Some(tx) = room.peers.get(&to) {
                        let _ = tx.send(bytes.to_vec());
                    }
                }
            }
            other => {
                eprintln!("[relay] unknown channel 0x{other:02x} from {peer_id}");
            }
        }
    }

    // Cleanup: remove peer; mark room empty if no peers remain.
    {
        let mut rooms_lock = rooms.lock().unwrap();
        if let Some(room) = rooms_lock.get_mut(&room_id) {
            room.peers.remove(&peer_id);
            if room.peers.is_empty() {
                room.peers_empty_since = Some(Instant::now());
                // Immediately mark dirty so the saver task saves soon.
                if snapshot_dir.is_some() {
                    room.dirty = true;
                }
            }
        }
    }
    out_task.abort();
    eprintln!("[relay] {peer_id} left room {room_id}");
}

// ── main ─────────────────────────────────────────────────────────────────────

#[tokio::main]
async fn main() {
    let mut port = 9900u16;
    let mut snapshot_dir: Option<PathBuf> = None;
    let mut args = std::env::args().skip(1);
    while let Some(arg) = args.next() {
        if arg == "--port" {
            port = args.next().expect("missing port").parse().expect("invalid port");
        } else if let Some(s) = arg.strip_prefix("--port=") {
            port = s.parse().expect("invalid port");
        } else if arg == "--snapshot-dir" {
            snapshot_dir = Some(PathBuf::from(args.next().expect("missing snapshot-dir")));
        } else if let Some(s) = arg.strip_prefix("--snapshot-dir=") {
            snapshot_dir = Some(PathBuf::from(s));
        }
    }

    if let Some(dir) = &snapshot_dir {
        std::fs::create_dir_all(dir).expect("cannot create snapshot-dir");
        eprintln!("[relay] snapshots → {}", dir.display());
    }

    let addr = format!("0.0.0.0:{port}");
    let listener = TcpListener::bind(&addr).await.expect("bind failed");
    eprintln!("[relay] listening on {addr}");

    let rooms: Rooms = Arc::new(Mutex::new(HashMap::new()));
    let snap_arc = snapshot_dir.map(Arc::new);

    // Spawn snapshot saver if persistence is enabled.
    if let Some(dir) = snap_arc.clone() {
        let rooms_clone = rooms.clone();
        tokio::spawn(snapshot_task(rooms_clone, (*dir).clone()));
    }

    loop {
        match listener.accept().await {
            Ok((stream, addr)) => {
                let rooms = rooms.clone();
                let snap = snap_arc.clone();
                tokio::spawn(async move {
                    handle_tcp(rooms, snap, stream, addr).await;
                });
            }
            Err(e) => eprintln!("[relay] accept error: {e}"),
        }
    }
}
