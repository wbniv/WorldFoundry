"""The phone as a gamepad: the portable server and protocol, on Linux (Phase E1 and the headless half of E5).

Plan: docs/plans/2026-09-30-aquarium-chromecast.md, Phase E, verification step 11.

Builds the same wfsource/source/hal/phonepad/phonepad.cc the Android app links, with ASan and UBSan, runs it
on 127.0.0.1 (tests/phonepad_harness.py) and drives it with a raw WebSocket client:

  * HTTP: the PIN form, the page and the layout behind the PIN, 403 for a wrong PIN, 429 after too many,
    431 for an oversized request, and the WebSocket handshake (RFC 6455's own example key);
  * the mask: "b:<hex>" sets exactly the EJ_BUTTONF_* bits the engine sees, "t:<ms>" is echoed;
  * safety: 1 s of silence releases every button, a heartbeat keeps it held, the newest phone wins and the
    old one is told why, and every malformed or oversized frame closes the connection with no stuck button;
  * listening only while resumed: pause stops the listener and releases the phone, resume keeps the PIN.

No device, no display. python3 -m pytest tests/test_phone_controller.py -v
"""

from __future__ import annotations

import socket
import time

import pytest

from phonepad_harness import (A, B, C, D, E, F, DOWN, LEFT, LAYOUTS, PAGE, PIN, RIGHT, UP, WS, Host, build_host,
                              http_get, ws_accept)

WRONG = "000000" if PIN != "000000" else "111111"


@pytest.fixture(scope="session")
def host_exe(tmp_path_factory):
    return build_host(tmp_path_factory.mktemp("phonepad"))


@pytest.fixture
def host(host_exe):
    h = Host(host_exe)
    yield h
    h.close()


def connect_phone(host, **kw) -> WS:
    ws = WS(host.port, **kw)
    assert ws.status == 101, (ws.status, ws.headers)
    host.expect(r"^EVENT connected$")
    return ws


def hold(host, ws, mask):
    ws.send_mask(mask)
    host.expect_mask(mask)


# ---- HTTP and the PIN ---------------------------------------------------------------------------

def test_bare_address_gets_the_pin_form_not_the_controller(host):
    status, hdrs, body = http_get(host.port, "/")
    assert status == 200 and hdrs["content-type"].startswith("text/html")
    assert b'name="k"' in body and b"Enter the PIN" in body
    assert body != PAGE.read_bytes() and b"WebSocket" not in body


def test_right_pin_serves_the_page_and_the_layout(host):
    status, hdrs, body = http_get(host.port, f"/?k={PIN}")
    assert status == 200 and body == PAGE.read_bytes()
    assert hdrs["cache-control"] == "no-store" and hdrs["referrer-policy"] == "no-referrer"
    status, hdrs, body = http_get(host.port, f"/layout.json?k={PIN}")
    assert status == 200 and hdrs["content-type"] == "application/json"
    assert body == LAYOUTS["condo"].read_bytes()


@pytest.mark.parametrize("target", [f"/?k={WRONG}", f"/layout.json?k={WRONG}", "/layout.json", f"/?k={PIN}0",
                                    f"/?k={PIN[:5]}"])
def test_wrong_or_missing_pin_is_refused(host, target):
    status, _, body = http_get(host.port, target)
    assert status == 403
    assert PAGE.read_bytes()[:200] not in body
    if target.startswith("/?"):
        assert b"Wrong code. Scan the TV again." in body


def test_websocket_with_wrong_pin_is_refused_and_no_input_accepted(host):
    ws = WS(host.port, pin=WRONG)
    assert ws.status == 403
    host.expect(r"^EVENT wrongpin$")
    assert host.state() == {"mask": 0, "phone": False, "running": True}


def test_wrong_pins_are_rate_limited(host):
    for _ in range(5):
        assert http_get(host.port, f"/layout.json?k={WRONG}")[0] == 403
    # The sixth guess inside the same second is not even checked, and neither is the right PIN.
    assert http_get(host.port, f"/layout.json?k={WRONG}")[0] == 429
    assert http_get(host.port, f"/layout.json?k={PIN}")[0] == 429
    time.sleep(1.1)
    assert http_get(host.port, f"/layout.json?k={PIN}")[0] == 200


def test_oversized_request_is_refused(host):
    raw = (f"GET /?k={PIN} HTTP/1.1\r\nHost: x\r\nX-Pad: " + "a" * 5000 + "\r\n\r\n").encode()
    assert http_get(host.port, "", raw=raw)[0] == 431


def test_other_methods_and_paths(host):
    assert http_get(host.port, "", raw=f"POST /?k={PIN} HTTP/1.1\r\nHost: x\r\n\r\n".encode())[0] == 405
    assert http_get(host.port, f"/etc/passwd?k={PIN}")[0] == 404
    assert http_get(host.port, "/favicon.ico")[0] == 404


def test_websocket_handshake_matches_rfc6455(host):
    key = "dGhlIHNhbXBsZSBub25jZQ=="
    ws = connect_phone(host, key=key)
    assert ws.headers["sec-websocket-accept"] == "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=" == ws_accept(key)
    assert ws.headers["upgrade"].lower() == "websocket"


def test_upgrade_without_websocket_headers_is_a_bad_request(host):
    assert http_get(host.port, f"/ws?k={PIN}")[0] == 400


# ---- the mask -------------------------------------------------------------------------------------

def test_mask_frames_set_exactly_the_engine_bits(host):
    ws = connect_phone(host)
    for m in (RIGHT, RIGHT | A, UP | LEFT | C, D | E | F | DOWN, B, 0):
        hold(host, ws, m)
    ws.send_text("b:FFFF")
    host.expect_mask(0xFFFF)
    ws.send_text("b:0")
    host.expect_mask(0)


def test_timestamp_is_echoed(host):
    ws = connect_phone(host)
    ws.send_text("t:1727771234567")
    assert ws.recv() == (1, b"t:1727771234567")


def test_unknown_frame_type_is_ignored_and_keeps_the_phone(host):
    ws = connect_phone(host)
    hold(host, ws, RIGHT)
    ws.send_text("z:something-new")
    ws.send_text("t:1")
    assert ws.recv() == (1, b"t:1")
    assert host.state()["mask"] == RIGHT


def test_ping_gets_a_pong(host):
    ws = connect_phone(host)
    ws.send_raw(ws.frame(9, b"hi"))
    assert ws.recv() == (10, b"hi")


# ---- safety: nothing stays held -------------------------------------------------------------------

def test_silence_for_one_second_releases_every_button(host):
    ws = connect_phone(host)
    ws.send_mask(RIGHT | A)
    host.expect_mask(RIGHT | A)
    t_last = host.last_time
    host.expect(r"^EVENT lost$", timeout=3)
    host.expect_mask(0, timeout=1)
    held_for = host.last_time - t_last
    assert 0.95 <= held_for <= 1.4, held_for
    assert ws.recv_close() == 4002
    assert host.state() == {"mask": 0, "phone": False, "running": True}


def test_50ms_keepalive_holds_the_button_without_flooding_the_log(host):
    """The page sends its mask every 50 ms (controller.html KEEPALIVE_MS). 2.5 s of that: the button stays held,
    the host sees ONE mask change (the engine glue logs per change, not per frame) and the server logs nothing."""
    ws = connect_phone(host)
    hold(host, ws, RIGHT)
    n_log = len(host.log)
    for _ in range(50):
        time.sleep(0.05)
        ws.send_mask(RIGHT)
    assert host.state() == {"mask": RIGHT, "phone": True, "running": True}
    after = host.log[n_log:]
    assert not [line for line in after if line.startswith(("MASK", "LOG", "EVENT"))], after


def test_a_burst_of_frames_cannot_overflow_anything(host):
    """Two seconds' worth of 20 Hz frames, and 50 times that, sent back to back (a phone catching up after
    a stall): no protocol error, no release, one mask change, and the connection still answers."""
    ws = connect_phone(host)
    ws.send_raw(b"".join(ws.frame(1, b"b:2000") for _ in range(2000)))
    host.expect_mask(RIGHT)
    ws.send_text("t:42")
    assert ws.recv() == (1, b"t:42")
    assert host.state() == {"mask": RIGHT, "phone": True, "running": True}
    assert "EVENT lost" not in host.log and "EVENT wrongpin" not in host.log


def test_frames_a_throttled_tab_sends_do_not_keep_a_button_held(host):
    """A backgrounded tab's timers drop to about 1 Hz or stop (a locked phone). The page closes the socket on
    'hidden' itself (test_phone_controller_page.py); if it cannot run at all, gaps over 1 s release here."""
    ws = connect_phone(host)
    hold(host, ws, RIGHT)
    time.sleep(1.2)
    ws.send_mask(RIGHT)
    host.expect(r"^EVENT lost$", timeout=1)
    host.expect_mask(0)


def test_newest_phone_wins_and_the_first_is_told(host):
    first = connect_phone(host)
    hold(host, first, RIGHT | A)
    second = connect_phone(host)
    host.expect_mask(0)                       # the first phone's buttons are released at once
    assert first.recv_close() == 4001
    hold(host, second, LEFT)
    try:
        first.send_mask(UP)                    # the old phone is gone: nothing it sends counts
    except OSError:
        pass
    time.sleep(0.1)
    assert host.state() == {"mask": LEFT, "phone": True, "running": True}
    assert "EVENT replaced" in host.log


def test_close_frame_releases(host):
    ws = connect_phone(host)
    hold(host, ws, DOWN | B)
    ws.send_raw(ws.frame(8, b"\x03\xe8"))
    host.expect_mask(0)
    assert ws.recv_close() == 1000


def test_dropped_tcp_connection_releases(host):
    ws = connect_phone(host)
    hold(host, ws, RIGHT)
    ws.sock.shutdown(socket.SHUT_RDWR)
    ws.close()
    host.expect(r"^EVENT lost$", timeout=0.5)   # the host prints the event, then the mask
    host.expect_mask(0)


MALFORMED = {
    "bad hex": (lambda ws: ws.frame(1, b"b:zz"), 1007),
    "five hex digits": (lambda ws: ws.frame(1, b"b:12345"), 1007),
    "empty mask": (lambda ws: ws.frame(1, b"b:"), 1007),
    "no type": (lambda ws: ws.frame(1, b"hello"), 1007),
    "upper-case type": (lambda ws: ws.frame(1, b"B:1"), 1007),
    "bad timestamp": (lambda ws: ws.frame(1, b"t:12ab"), 1007),
    "non-printable": (lambda ws: ws.frame(1, b"b:1\x00"), 1007),
    "binary frame": (lambda ws: ws.frame(2, b"\x00\x20"), 1003),
    "unmasked frame": (lambda ws: ws.frame(1, b"b:1", masked=False), 1002),
    "fragment": (lambda ws: ws.frame(1, b"b:1", fin=False), 1002),
    "continuation": (lambda ws: ws.frame(0, b"b:1"), 1002),
    "reserved bits": (lambda ws: ws.frame(1, b"b:1", rsv=4), 1002),
    "unknown opcode": (lambda ws: ws.frame(3, b"b:1"), 1002),
    "oversized property payload": (lambda ws: ws.frame(1, b"r:" + b"x" * 4095), 1009),
    "invalid extended button payload": (lambda ws: ws.frame(1, b"b:1" + b" " * 200), 1007),
    "64-bit length": (lambda ws: ws.frame(1, b"b:1", length=1 << 40), 1009),
}


@pytest.mark.parametrize("name", list(MALFORMED))
def test_malformed_or_oversized_frame_closes_and_releases(host, name):
    build, code = MALFORMED[name]
    ws = connect_phone(host)
    hold(host, ws, RIGHT | A)
    ws.send_raw(build(ws))
    host.expect(r"^EVENT lost$", timeout=1)
    host.expect_mask(0)
    assert ws.recv_close() == code
    assert host.state() == {"mask": 0, "phone": False, "running": True}
    # and the server is still healthy for the next phone
    again = connect_phone(host)
    hold(host, again, LEFT)


def test_idle_sockets_cannot_lock_the_phone_out(host):
    idle = [socket.create_connection(("127.0.0.1", host.port)) for _ in range(12)]
    time.sleep(0.1)
    ws = connect_phone(host)
    hold(host, ws, UP)
    for s in idle:
        s.close()


# ---- listening only while resumed -----------------------------------------------------------------

def test_pause_stops_listening_and_releases_resume_keeps_the_pin(host):
    ws = connect_phone(host)
    hold(host, ws, RIGHT)
    host.command("pause")
    host.expect(r"^PAUSED$")
    host.expect_mask(0)
    assert ws.recv(timeout=1) is None          # dropped with the listener
    with pytest.raises(OSError):
        socket.create_connection(("127.0.0.1", host.port), timeout=1)
    host.command("resume")
    port = int(host.expect(r"^LISTEN (\d+)$").group(1))
    host.port = port
    again = connect_phone(host)                 # the same PIN still works after resume
    hold(host, again, LEFT)


# ---- helpers --------------------------------------------------------------------------------------

def test_pins_are_six_random_digits(host):
    pins = []
    for _ in range(20):
        host.command("pin")
        pins.append(host.expect(r"^PIN (\S*)$").group(1))
    assert all(len(p) == 6 and p.isdigit() for p in pins), pins
    assert len(set(pins)) >= 18, pins


@pytest.mark.parametrize("addr,private", [("192.168.4.38", 1), ("10.1.2.3", 1), ("172.16.0.1", 1), ("172.31.255.1", 1),
                                          ("172.32.0.1", 0), ("169.254.9.9", 1), ("127.0.0.1", 1), ("8.8.8.8", 0),
                                          ("100.64.0.1", 0), ("192.169.0.1", 0)])
def test_only_private_lan_peers(host, addr, private):
    host.command(f"private {addr}")
    assert host.expect(r"^PRIVATE (\d)$").group(1) == str(private)


# ---- diagnosis: a connection that never completes a request still leaves a log line -----------------

def test_accept_and_request_less_close_are_logged(host):
    """2026-10-01: a phone on another network showed a page that never loaded and the TV logged nothing, because
    only completed requests were logged. Every accepted connection, and one closed before a complete request,
    now leaves a line, so the next tester can tell "never reached the TV" from "reached it and gave up"."""
    s = socket.create_connection(("127.0.0.1", host.port))
    port = s.getsockname()[1]
    host.expect(rf"^LOG phonepad: connection from 127\.0\.0\.1:{port}$")
    s.sendall(b"GET /?k=")                          # half a request, then the browser gives up
    time.sleep(0.05)
    s.close()
    host.expect(rf"^LOG phonepad: 127\.0\.0\.1:{port} closed the connection before a complete request \(8 bytes received\)$")
