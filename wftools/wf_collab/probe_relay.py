#!/usr/bin/env python3
# Minimal raw-WebSocket probe for the wf-edit collab relay (stdlib only).
# Mirrors engine/wf_edit/ws_client.cc + wftools/wf_collab/src/bin/relay.rs.
#
# Connects to a relay (directly or via a Cloudflare quick tunnel), JOINs a room,
# announces a PRESENCE so live editors light up a "Claude probe" peer, then lists
# every other peer + frame channel it sees. Diagnoses "is anyone actually in this
# room?" independently of the editor — see
# docs/plans/2026-06-01-relay-connect-localhost-and-resilient-retry.md.
#
# Usage (all via env):
#   WF_PROBE_HOST=<host.trycloudflare.com|host>   WF_PROBE_PORT=443
#   WF_PROBE_ROOM=studio-NNNN   WF_PROBE_PEER=probe-claude   WF_PROBE_LISTEN=<s>
#   e.g.  WF_PROBE_HOST=foo.trycloudflare.com WF_PROBE_ROOM=studio-5664 \
#         WF_PROBE_LISTEN=20 python3 wftools/wf_collab/probe_relay.py
import socket, ssl, struct, os, base64, hashlib, json, sys, time, select

HOST = os.environ.get("WF_PROBE_HOST", "localhost")
PORT = int(os.environ.get("WF_PROBE_PORT", "443"))
ROOM = os.environ.get("WF_PROBE_ROOM", "studio-2781")
PEER = os.environ.get("WF_PROBE_PEER", "probe-claude")
LISTEN_SECS = float(os.environ.get("WF_PROBE_LISTEN", "9"))

CH = {0x01: "SYNC", 0x02: "PRESENCE", 0x03: "CHAT", 0x04: "CONTROL", 0x05: "SIGNAL"}

def ws_handshake(sock, host, path="/"):
    key = base64.b64encode(os.urandom(16)).decode()
    req = (f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\n"
           f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
           f"Sec-WebSocket-Version: 13\r\n\r\n")
    sock.sendall(req.encode())
    resp = b""
    while b"\r\n\r\n" not in resp:
        chunk = sock.recv(4096)
        if not chunk: raise RuntimeError("closed during handshake")
        resp += chunk
    line = resp.split(b"\r\n", 1)[0].decode(errors="replace")
    if b"101" not in resp.split(b"\r\n", 1)[0]:
        raise RuntimeError(f"upgrade rejected: {line}")
    return line

def send_frame(sock, payload):
    # client binary frame, masked
    hdr = bytearray([0x82])
    n = len(payload)
    if n <= 125: hdr.append(0x80 | n)
    elif n <= 65535: hdr += bytes([0x80 | 126]) + struct.pack(">H", n)
    else: hdr += bytes([0x80 | 127]) + struct.pack(">Q", n)
    mask = os.urandom(4)
    masked = bytes(b ^ mask[i & 3] for i, b in enumerate(payload))
    sock.sendall(bytes(hdr) + mask + masked)

def recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        c = sock.recv(n - len(buf))
        if not c: return None
        buf += c
    return buf

def recv_frame(sock):
    h = recv_exact(sock, 2)
    if not h: return None
    b0, b1 = h[0], h[1]
    ln = b1 & 0x7f
    if ln == 126: ln = struct.unpack(">H", recv_exact(sock, 2))[0]
    elif ln == 127: ln = struct.unpack(">Q", recv_exact(sock, 8))[0]
    if b1 & 0x80:  # masked (shouldn't be, from server)
        mask = recv_exact(sock, 4)
        pl = recv_exact(sock, ln)
        pl = bytes(c ^ mask[i & 3] for i, c in enumerate(pl))
    else:
        pl = recv_exact(sock, ln) if ln else b""
    return (b0 & 0x0f, pl)  # (opcode, payload)

def main():
    raw = socket.create_connection((HOST, PORT), timeout=10)
    ctx = ssl._create_unverified_context()
    sock = ctx.wrap_socket(raw, server_hostname=HOST)
    print(f"[probe] TLS connected to {HOST}:{PORT}")
    print("[probe] handshake:", ws_handshake(sock, HOST))

    # CONTROL join: [0x04][room\0peer]
    join = bytes([0x04]) + ROOM.encode() + b"\x00" + PEER.encode()
    send_frame(sock, join)
    print(f"[probe] JOIN room={ROOM} peer={PEER}")

    presence = bytes([0x02]) + json.dumps({
        "peer_id": PEER, "name": "Claude probe",
        "colour": [1.0, 0.4, 0.1], "selected_eid": ""
    }).encode()

    seen_peers = {}
    counts = {}
    last_pres = 0.0
    deadline = time.time() + LISTEN_SECS
    while time.time() < deadline:
        now = time.time()
        if now - last_pres > 1.5:
            send_frame(sock, presence)
            last_pres = now
        r, _, _ = select.select([sock], [], [], 0.3)
        if not r: continue
        fr = recv_frame(sock)
        if fr is None: print("[probe] relay closed connection"); break
        op, pl = fr
        if op == 0x08: print("[probe] CLOSE frame"); break
        if op in (0x09, 0x0a): continue  # ping/pong
        if not pl: continue
        ch = pl[0]
        name = CH.get(ch, f"0x{ch:02x}")
        counts[name] = counts.get(name, 0) + 1
        if ch in (0x02, 0x03):  # presence/chat carry JSON
            try:
                j = json.loads(pl[1:])
                pid = j.get("peer_id", "?")
                if pid != PEER:
                    seen_peers[pid] = j.get("name", "?")
                    print(f"[probe] {name} from peer_id={pid!r} name={j.get('name')!r}")
            except Exception as e:
                print(f"[probe] {name} (unparseable json, {len(pl)-1}B)")
        else:
            print(f"[probe] {name} ({len(pl)-1}B payload)")

    print("\n===== SUMMARY =====")
    print("frames by channel:", counts or "(none)")
    others = {p: n for p, n in seen_peers.items() if p != PEER}
    if others:
        print(f"OTHER peers in room {ROOM}: {others}")
    else:
        print(f"NO other peers detected in room {ROOM} during {LISTEN_SECS:.0f}s.")
    sock.close()

if __name__ == "__main__":
    main()
