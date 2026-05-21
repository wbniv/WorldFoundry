// Smoke test: two clients connect to a localhost relay, one sends a message,
// the other receives it.  A minimal inline relay runs in a background task.
//
// Plan: docs/plans/2026-05-21-realtime-coediting.md Phase 1

use std::sync::{Arc, Mutex};
use std::time::Duration;

use futures_util::{SinkExt, StreamExt};
use tokio::net::TcpListener;
use tokio::sync::mpsc;
use tokio::time::timeout;
use tokio_tungstenite::{accept_async, connect_async, tungstenite::Message};
use yrs::{Doc, StateVector, Update};
use yrs::updates::decoder::Decode;

const CH_SYNC: u8 = 0x01;
const CH_PRESENCE: u8 = 0x02;
const CH_CONTROL: u8 = 0x04;

fn control_msg(room: &str, peer: &str) -> Vec<u8> {
    let mut v = vec![CH_CONTROL];
    v.extend_from_slice(room.as_bytes());
    v.push(0);
    v.extend_from_slice(peer.as_bytes());
    v
}

async fn next_binary(ws: &mut (impl StreamExt<Item = Result<Message, tokio_tungstenite::tungstenite::Error>> + Unpin)) -> Vec<u8> {
    loop {
        match timeout(Duration::from_secs(5), ws.next()).await
            .expect("timeout").expect("stream ended").expect("WS error")
        {
            Message::Binary(b) => return b,
            _ => continue,
        }
    }
}

// Minimal inline relay — mirrors the real relay's logic for testing.
struct Room { doc: Doc, peers: std::collections::HashMap<String, mpsc::UnboundedSender<Vec<u8>>> }
type Rooms = Arc<Mutex<std::collections::HashMap<String, Room>>>;

async fn run_relay(listener: TcpListener, rooms: Rooms) {
    loop {
        let Ok((stream, _)) = listener.accept().await else { break };
        let rooms = rooms.clone();
        tokio::spawn(async move {
            let ws = accept_async(stream).await.unwrap();
            let (mut tx, mut rx) = ws.split();
            let (room_id, peer_id) = loop {
                match rx.next().await {
                    Some(Ok(Message::Binary(b))) if b.first() == Some(&CH_CONTROL) => {
                        let p = &b[1..];
                        let mid = p.iter().position(|&x| x == 0).unwrap_or(p.len());
                        break (
                            String::from_utf8_lossy(&p[..mid]).into_owned(),
                            String::from_utf8_lossy(if mid+1 < p.len() { &p[mid+1..] } else { b"anon" }).into_owned(),
                        );
                    }
                    _ => return,
                }
            };
            let (send_tx, mut send_rx) = mpsc::unbounded_channel::<Vec<u8>>();
            let full_state = {
                let mut lock = rooms.lock().unwrap();
                let room = lock.entry(room_id.clone()).or_insert_with(|| Room { doc: Doc::new(), peers: Default::default() });
                room.peers.insert(peer_id.clone(), send_tx);
                let sv = StateVector::default();
                let update = room.doc.encode_state_as_update_v1(&sv);
                let mut msg = vec![CH_SYNC]; msg.extend_from_slice(&update); msg
            };
            let _ = tx.send(Message::Binary(full_state)).await;
            let out = tokio::spawn(async move {
                while let Some(m) = send_rx.recv().await {
                    if tx.send(Message::Binary(m)).await.is_err() { break; }
                }
            });
            while let Some(Ok(Message::Binary(b))) = rx.next().await {
                if b.is_empty() { continue; }
                match b[0] {
                    CH_SYNC => {
                        let mut lock = rooms.lock().unwrap();
                        if let Some(r) = lock.get_mut(&room_id) {
                            if !b[1..].is_empty() {
                                let upd = Update::decode_v1(&b[1..]);
                                r.doc.transact().apply_update(upd);
                            }
                            for (id, s) in &r.peers { if id != &peer_id { let _ = s.send(b.clone()); } }
                        }
                    }
                    CH_PRESENCE => {
                        let lock = rooms.lock().unwrap();
                        if let Some(r) = lock.get(&room_id) {
                            for (id, s) in &r.peers { if id != &peer_id { let _ = s.send(b.clone()); } }
                        }
                    }
                    _ => {}
                }
            }
            { let mut lock = rooms.lock().unwrap(); if let Some(r) = lock.get_mut(&room_id) { r.peers.remove(&peer_id); } }
            out.abort();
        });
    }
}

#[tokio::test]
async fn presence_fanout() {
    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let port = listener.local_addr().unwrap().port();
    let url = format!("ws://127.0.0.1:{port}");
    let rooms: Rooms = Arc::new(Mutex::new(Default::default()));
    tokio::spawn(run_relay(listener, rooms));
    tokio::time::sleep(Duration::from_millis(20)).await;

    let (mut ws_a, _) = connect_async(url.as_str()).await.unwrap();
    ws_a.send(Message::Binary(control_msg("room1", "peer-a"))).await.unwrap();
    let _ = next_binary(&mut ws_a).await; // discard initial full-state SYNC

    let (mut ws_b, _) = connect_async(url.as_str()).await.unwrap();
    ws_b.send(Message::Binary(control_msg("room1", "peer-b"))).await.unwrap();
    let _ = next_binary(&mut ws_b).await; // discard initial full-state SYNC

    // A sends a PRESENCE message.
    let payload = b"cursor:ndc:0.5,0.3";
    let mut msg = vec![CH_PRESENCE];
    msg.extend_from_slice(payload);
    ws_a.send(Message::Binary(msg.clone())).await.unwrap();

    // B should receive it.
    let received = next_binary(&mut ws_b).await;
    assert_eq!(received[0], CH_PRESENCE, "expected PRESENCE channel");
    assert_eq!(&received[1..], payload);
}

#[tokio::test]
async fn sync_fanout_with_valid_update() {
    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let port = listener.local_addr().unwrap().port();
    let url = format!("ws://127.0.0.1:{port}");
    let rooms: Rooms = Arc::new(Mutex::new(Default::default()));
    tokio::spawn(run_relay(listener, rooms));
    tokio::time::sleep(Duration::from_millis(20)).await;

    // Generate a valid Yrs v1 update using the local doc.
    let doc = Doc::new();
    let sv_empty = StateVector::default();
    let update_bytes = doc.encode_state_as_update_v1(&sv_empty);
    // This is a valid (empty) update — no new blocks, no deletes.

    let (mut ws_a, _) = connect_async(url.as_str()).await.unwrap();
    ws_a.send(Message::Binary(control_msg("room2", "peer-a"))).await.unwrap();
    let _ = next_binary(&mut ws_a).await;

    let (mut ws_b, _) = connect_async(url.as_str()).await.unwrap();
    ws_b.send(Message::Binary(control_msg("room2", "peer-b"))).await.unwrap();
    let _ = next_binary(&mut ws_b).await;

    // A sends a valid (empty) SYNC update.
    let mut msg = vec![CH_SYNC];
    msg.extend_from_slice(&update_bytes);
    ws_a.send(Message::Binary(msg)).await.unwrap();

    // B should receive the SYNC fanout.
    let received = next_binary(&mut ws_b).await;
    assert_eq!(received[0], CH_SYNC, "expected SYNC channel");
    assert_eq!(&received[1..], &update_bytes[..]);
}

#[tokio::test]
async fn late_joiner_gets_full_state() {
    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let port = listener.local_addr().unwrap().port();
    let url = format!("ws://127.0.0.1:{port}");
    let rooms: Rooms = Arc::new(Mutex::new(Default::default()));
    tokio::spawn(run_relay(listener, rooms));
    tokio::time::sleep(Duration::from_millis(20)).await;

    // A connects and sends an empty SYNC (seeds the room).
    let (mut ws_a, _) = connect_async(url.as_str()).await.unwrap();
    ws_a.send(Message::Binary(control_msg("room3", "peer-a"))).await.unwrap();
    let _ = next_binary(&mut ws_a).await;

    let doc = Doc::new();
    let update_bytes = doc.encode_state_as_update_v1(&StateVector::default());
    let mut msg = vec![CH_SYNC];
    msg.extend_from_slice(&update_bytes);
    ws_a.send(Message::Binary(msg)).await.unwrap();

    // B joins late — should receive a SYNC full-state message.
    let (mut ws_b, _) = connect_async(url.as_str()).await.unwrap();
    ws_b.send(Message::Binary(control_msg("room3", "peer-b"))).await.unwrap();
    let full_state = next_binary(&mut ws_b).await;
    assert_eq!(full_state[0], CH_SYNC, "late joiner should get SYNC full state");
}
