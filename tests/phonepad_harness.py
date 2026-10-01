"""Shared harness for the phone-controller tests (Phase E of docs/plans/2026-09-30-aquarium-chromecast.md).

Builds wfsource/source/hal/phonepad/host/phonepad_host.cc (the portable server plus a tiny main) with the
host C++ compiler, AddressSanitizer and UBSan, runs it on 127.0.0.1, and gives the tests a raw WebSocket client
that can also send the malformed frames a real browser never would. No device, no display, no third-party
Python packages.
"""

from __future__ import annotations

import base64
import os
import queue
import re
import shutil
import socket
import struct
import subprocess
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PHONEPAD = REPO / "wfsource" / "source" / "hal" / "phonepad"
PAGE = PHONEPAD / "controller.html"
SRC = REPO / "android" / "app" / "src"
LAYOUTS = {"aquarium": SRC / "aquarium" / "assets" / "layout.json", "condo": SRC / "condo" / "assets" / "layout.json"}
PIN = "482913"

# EJ_BUTTONF_* (wfsource/source/hal/sjoystic.h): A..F are bits 0..5, UP/DOWN/RIGHT/LEFT bits 11..14.
A, B, C, D, E, F = 1, 2, 4, 8, 16, 32
UP, DOWN, RIGHT, LEFT = 1 << 11, 1 << 12, 1 << 13, 1 << 14


QRCODEGEN = REPO / "engine" / "vendor" / "qrcodegen-3c6d0b3c" / "qrcodegen.c"


def host_sources() -> list[Path]:
    """Exactly what CMakeLists.txt adds to the Android library for the phone controller, plus the host's main."""
    return ([PHONEPAD / "phonepad.cc", PHONEPAD / "host" / "phonepad_host.cc"] + sorted(PHONEPAD.glob("phonepad_*.cc"))
            + [QRCODEGEN])


def build_host(out_dir: Path, extra: list[Path] | None = None) -> Path:
    cxx = shutil.which(os.environ.get("CXX", "g++")) or shutil.which("c++")
    assert cxx, "no host C++ compiler"
    exe = out_dir / "phonepad_host"
    objs = []
    flags = ["-O1", "-g", "-Wall", "-Wextra", "-Werror", "-fsanitize=address,undefined", "-fno-sanitize-recover=all"]
    for src in host_sources() + list(extra or []):
        obj = out_dir / (src.name + ".o")
        if src.suffix == ".c":
            cc = shutil.which(os.environ.get("CC", "gcc")) or shutil.which("cc")
            cmd = [cc, "-std=c99", *flags, "-c", str(src), "-o", str(obj)]
        else:
            cmd = [cxx, "-std=c++17", *flags, "-c", str(src), "-o", str(obj)]
        subprocess.run(cmd, check=True)
        objs.append(str(obj))
    subprocess.run([cxx, "-fsanitize=address,undefined", *objs, "-o", str(exe)], check=True)
    return exe


class Host:
    """The running phonepad_host: its stdout lines arrive on a queue, commands go to stdin."""

    def __init__(self, exe: Path, app: str = "condo", pin: str = PIN, timeout_ms: int = 1000):
        self.proc = subprocess.Popen(
            [str(exe), "--pin", pin, "--page", str(PAGE), "--layout", str(LAYOUTS[app]), "--timeout-ms", str(timeout_ms)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        self.lines: queue.Queue = queue.Queue()
        self.log: list[str] = []
        threading.Thread(target=self._pump, daemon=True).start()
        self.port = int(self.expect(r"^LISTEN (\d+)$").group(1))

    def _pump(self):
        for line in self.proc.stdout:
            line = line.rstrip("\n")
            self.log.append(line)
            self.lines.put((time.monotonic(), line))
        self.lines.put((time.monotonic(), None))

    def expect(self, pattern: str, timeout: float = 3.0):
        """The next line matching `pattern` (skipping others); AssertionError on timeout or exit."""
        rx = re.compile(pattern)
        deadline = time.monotonic() + timeout
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                raise AssertionError(f"no line matching {pattern!r} within {timeout} s; log tail: {self.log[-15:]}")
            try:
                t, line = self.lines.get(timeout=left)
            except queue.Empty:
                continue
            if line is None:
                raise AssertionError(f"phonepad_host exited ({self.proc.poll()}); log tail: {self.log[-15:]}")
            m = rx.search(line)
            if m:
                self.last_time = t
                return m

    def expect_mask(self, value: int, timeout: float = 3.0):
        return self.expect(rf"^MASK 0x{value:04x}$", timeout)

    def command(self, cmd: str):
        self.proc.stdin.write(cmd + "\n")
        self.proc.stdin.flush()

    def state(self) -> dict:
        self.command("state")
        m = self.expect(r"^STATE mask=0x([0-9a-f]{4}) phone=(\d) running=(\d)$")
        return {"mask": int(m.group(1), 16), "phone": m.group(2) == "1", "running": m.group(3) == "1"}

    def close(self):
        if self.proc.poll() is None:
            try:
                self.command("quit")
                self.proc.wait(timeout=3)
            except (BrokenPipeError, subprocess.TimeoutExpired):
                self.proc.kill()
        out = "\n".join(self.log)
        assert "ERROR: AddressSanitizer" not in out and "runtime error:" not in out, out[-3000:]


def http_get(port: int, target: str, headers: dict | None = None, raw: bytes | None = None, timeout: float = 3.0):
    """(status, headers, body) for one HTTP/1.1 request; the server closes after each answer."""
    s = socket.create_connection(("127.0.0.1", port), timeout=timeout)
    if raw is None:
        h = {"Host": f"127.0.0.1:{port}", **(headers or {})}
        raw = (f"GET {target} HTTP/1.1\r\n" + "".join(f"{k}: {v}\r\n" for k, v in h.items()) + "\r\n").encode()
    s.sendall(raw)
    data = b""
    while True:
        try:
            chunk = s.recv(65536)
        except ConnectionResetError:
            break
        if not chunk:
            break
        data += chunk
    s.close()
    head, _, body = data.partition(b"\r\n\r\n")
    lines = head.decode("latin-1").split("\r\n")
    status = int(lines[0].split()[1])
    hdrs = {k.lower(): v.strip() for k, _, v in (ln.partition(":") for ln in lines[1:])}
    return status, hdrs, body


class WS:
    """A raw RFC 6455 client: real handshakes, and frames that may be deliberately broken."""

    def __init__(self, port: int, pin: str = PIN, key: str = "dGhlIHNhbXBsZSBub25jZQ=="):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=3)
        req = (f"GET /ws?k={pin} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nUpgrade: websocket\r\n"
               f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        self.sock.sendall(req.encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                break
            buf += chunk
        head, _, self.buf = buf.partition(b"\r\n\r\n")
        lines = head.decode("latin-1").split("\r\n")
        self.status = int(lines[0].split()[1]) if lines and lines[0] else 0
        self.headers = {k.lower(): v.strip() for k, _, v in (ln.partition(":") for ln in lines[1:])}

    def frame(self, opcode: int, payload: bytes, fin: bool = True, masked: bool = True, rsv: int = 0,
              length: int | None = None) -> bytes:
        n = len(payload) if length is None else length
        b0 = (0x80 if fin else 0) | (rsv << 4) | opcode
        if n < 126:
            hdr = bytes([b0, (0x80 if masked else 0) | n])
        elif n < 65536:
            hdr = bytes([b0, (0x80 if masked else 0) | 126]) + struct.pack(">H", n)
        else:
            hdr = bytes([b0, (0x80 if masked else 0) | 127]) + struct.pack(">Q", n)
        if not masked:
            return hdr + payload
        key = os.urandom(4)
        return hdr + key + bytes(b ^ key[i & 3] for i, b in enumerate(payload))

    def send_raw(self, data: bytes):
        self.sock.sendall(data)

    def send_text(self, text: str):
        self.send_raw(self.frame(1, text.encode()))

    def send_mask(self, mask: int):
        self.send_text(f"b:{mask:x}")

    def recv(self, timeout: float = 3.0):
        """(opcode, payload) of the next server frame, or None when the server closes the socket."""
        self.sock.settimeout(timeout)
        while True:
            if len(self.buf) >= 2:
                n = self.buf[1] & 0x7F
                if len(self.buf) >= 2 + n:
                    op, payload = self.buf[0] & 0x0F, self.buf[2:2 + n]
                    self.buf = self.buf[2 + n:]
                    return op, payload
            try:
                chunk = self.sock.recv(4096)
            except ConnectionResetError:
                return None
            if not chunk:
                return None
            self.buf += chunk

    def recv_close(self, timeout: float = 3.0):
        """The close code the server sent (skipping data frames), or None if it just dropped the socket."""
        while True:
            fr = self.recv(timeout)
            if fr is None:
                return None
            op, payload = fr
            if op == 8:
                return struct.unpack(">H", payload[:2])[0] if len(payload) >= 2 else 1005

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def ws_accept(key: str) -> str:
    import hashlib
    return base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()


def overlay_rects(host: "Host", w: int, h: int, t: int):
    """Ask the host's overlay for its rectangles: (changed, [(x0, y0, x1, y1, (r, g, b, a)), ...])."""
    host.command(f"ov-rects {w} {h} {t}")
    m = host.expect(r"^RECTS (\d+) changed=(\d)$")
    rects = []
    for _ in range(int(m.group(1))):
        r = host.expect(r"^R (\S+) (\S+) (\S+) (\S+) ([0-9a-f]{8})$")
        c = int(r.group(5), 16)
        rects.append((*map(float, r.groups()[:4]), (c >> 24, (c >> 16) & 255, (c >> 8) & 255, c & 255)))
    return m.group(2) == "1", rects


def render_rects(rects, w: int, h: int, background: Path | None = None):
    """Composite the overlay's rectangles the way the GL side does (source-over alpha), as a PIL image."""
    from PIL import Image, ImageDraw
    base = (Image.open(background).convert("RGBA").resize((w, h)) if background
            else Image.new("RGBA", (w, h), (40, 60, 80, 255)))
    draw = ImageDraw.Draw(base)
    for x0, y0, x1, y1, rgba in rects:
        box = (max(0, round(x0)), max(0, round(y0)), min(w, round(x1)), min(h, round(y1)))
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        if rgba[3] == 255:
            draw.rectangle([box[0], box[1], box[2] - 1, box[3] - 1], fill=rgba)
        else:                                   # source-over, only over the rectangle itself
            region = base.crop(box)
            base.paste(Image.alpha_composite(region, Image.new("RGBA", region.size, rgba)), box)
            draw = ImageDraw.Draw(base)
    return base.convert("RGB")
