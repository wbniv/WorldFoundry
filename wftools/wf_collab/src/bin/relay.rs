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
// Usage: wf-relay [--port <PORT>]   (default: 9900)
//
// Plan: docs/plans/2026-05-21-realtime-coediting.md Phase 1

use std::collections::HashMap;
use std::net::SocketAddr;
use std::sync::{Arc, Mutex};

use futures_util::{SinkExt, StreamExt};
use tokio::net::{TcpListener, TcpStream};
use tokio::sync::mpsc::{self, UnboundedSender};
use tokio_tungstenite::{accept_async, tungstenite::Message};
use yrs::{Doc, StateVector, Update};
use yrs::updates::decoder::Decode;

// ── Wire protocol constants ───────────────────────────────────────────────────

const CH_SYNC: u8 = 0x01;
const CH_PRESENCE: u8 = 0x02;
const CH_CHAT: u8 = 0x03;
const CH_CONTROL: u8 = 0x04;

// ── Room state ────────────────────────────────────────────────────────────────

type PeerId = String;
type RoomId = String;
type PeerSender = UnboundedSender<Vec<u8>>;

struct RoomState {
    doc: Doc,
    peers: HashMap<PeerId, PeerSender>,
}

impl RoomState {
    fn new() -> Self {
        Self { doc: Doc::new(), peers: HashMap::new() }
    }

    fn full_state_sync(&self) -> Vec<u8> {
        let sv = StateVector::default();
        let update = self.doc.encode_state_as_update_v1(&sv);
        let mut msg = vec![CH_SYNC];
        msg.extend_from_slice(&update);
        msg
    }

    fn apply_sync(&mut self, payload: &[u8]) {
        // Empty payload is a no-op (valid after initial join when doc is empty).
        if payload.is_empty() {
            return;
        }
        // Decode and apply — malformed payloads would panic; callers are
        // trusted (editor peers on the same LAN/localhost in v1).
        let upd = Update::decode_v1(payload);
        let mut txn = self.doc.transact();
        txn.apply_update(upd);
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

// ── Connection handler ────────────────────────────────────────────────────────

async fn handle_tcp(rooms: Rooms, stream: TcpStream, addr: SocketAddr) {
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

    // Register peer and get full state to send.
    let full_state = {
        let mut rooms_lock = rooms.lock().unwrap();
        let room = rooms_lock.entry(room_id.clone()).or_insert_with(RoomState::new);
        room.peers.insert(peer_id.clone(), send_tx);
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
            other => {
                eprintln!("[relay] unknown channel 0x{other:02x} from {peer_id}");
            }
        }
    }

    // Cleanup.
    {
        let mut rooms_lock = rooms.lock().unwrap();
        if let Some(room) = rooms_lock.get_mut(&room_id) {
            room.peers.remove(&peer_id);
        }
    }
    out_task.abort();
    eprintln!("[relay] {peer_id} left room {room_id}");
}

// ── main ─────────────────────────────────────────────────────────────────────

#[tokio::main]
async fn main() {
    let mut port = 9900u16;
    let mut args = std::env::args().skip(1);
    while let Some(arg) = args.next() {
        if arg == "--port" {
            port = args.next().expect("missing port").parse().expect("invalid port");
        } else if let Some(s) = arg.strip_prefix("--port=") {
            port = s.parse().expect("invalid port");
        }
    }

    let addr = format!("0.0.0.0:{port}");
    let listener = TcpListener::bind(&addr).await.expect("bind failed");
    eprintln!("[relay] listening on {addr}");

    let rooms: Rooms = Arc::new(Mutex::new(HashMap::new()));

    loop {
        match listener.accept().await {
            Ok((stream, addr)) => {
                let rooms = rooms.clone();
                tokio::spawn(async move {
                    handle_tcp(rooms, stream, addr).await;
                });
            }
            Err(e) => eprintln!("[relay] accept error: {e}"),
        }
    }
}
