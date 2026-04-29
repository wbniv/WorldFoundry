"""
debug_bridge.py — TCP/JSON debug bridge between Blender and wf_game.

The engine must be launched with --debug-port N (default 7777).
Protocol: newline-delimited JSON. Each message is one UTF-8 line + \\n.

Object identity uses the actor index (integer), which corresponds to the
object's position in the level export order (1-based). Blender maintains
an idx→name mapping so UI can show human-readable labels.
"""

import socket
import threading
import json
import queue
import time
import bpy

# Module-level singleton — one bridge per Blender session.
_bridge = None


def get_bridge():
    global _bridge
    if _bridge is None:
        _bridge = DebugBridge()
    return _bridge


class DebugBridge:
    def __init__(self):
        self._sock = None
        self._thread = None
        self._send_q = queue.Queue()
        self._running = False
        self._lock = threading.Lock()

        # idx (int) → object name (str) populated from last export.
        self.idx_to_name: dict[int, str] = {}
        # name → idx reverse map
        self.name_to_idx: dict[str, int] = {}

        # Last received frame state — set on background thread, read on main.
        self.frame_n: int = 0
        self.frame_dt_ms: float = 0.0
        # idx → [x, y, z]
        self.positions: dict[int, list] = {}

        self.connected = False
        self.error: str = ""

    # ── Public API ────────────────────────────────────────────────────────────

    def connect(self, host: str, port: int):
        with self._lock:
            if self._running:
                return
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3.0)
            sock.connect((host, port))
            sock.settimeout(None)
        except OSError as e:
            self.error = str(e)
            return
        with self._lock:
            self._sock = sock
            self._running = True
            self.connected = True
            self.error = ""
        self._thread = threading.Thread(target=self._io_loop, daemon=True)
        self._thread.start()

    def disconnect(self):
        with self._lock:
            self._running = False
            if self._sock:
                try:
                    self._sock.close()
                except OSError:
                    pass
                self._sock = None
            self.connected = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None

    def send(self, msg: dict):
        line = json.dumps(msg, separators=(',', ':')) + '\n'
        self._send_q.put(line)

    def ping(self):
        self.send({"op": "ping"})

    def set_transform(self, idx: int, pos: list):
        self.send({"op": "scene:set_transform", "idx": idx, "pos": pos})

    def set_prop(self, idx: int, key: str, value):
        self.send({"op": "scene:set_prop", "idx": idx, "key": key, "value": value})

    def update_index_map(self, mapping: dict[int, str]):
        """Called by the export step with {idx: blender_obj_name, ...}."""
        self.idx_to_name = dict(mapping)
        self.name_to_idx = {v: k for k, v in mapping.items()}

    # ── Background I/O loop ───────────────────────────────────────────────────

    def _io_loop(self):
        partial = b""
        while True:
            with self._lock:
                if not self._running:
                    break
                sock = self._sock

            # Drain the send queue (non-blocking).
            while not self._send_q.empty():
                try:
                    line = self._send_q.get_nowait()
                    try:
                        sock.sendall(line.encode())
                    except OSError:
                        self._on_disconnect("send error")
                        return
                except queue.Empty:
                    break

            # Read incoming data (short timeout so we can drain send_q regularly).
            sock.settimeout(0.05)
            try:
                data = sock.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                self._on_disconnect("recv error")
                return

            if not data:
                self._on_disconnect("server closed connection")
                return

            partial += data
            while b'\n' in partial:
                line_bytes, partial = partial.split(b'\n', 1)
                try:
                    msg = json.loads(line_bytes.decode('utf-8', errors='replace'))
                    bpy.app.timers.register(lambda m=msg: self._on_message(m), first_interval=0)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass

    def _on_disconnect(self, reason: str):
        with self._lock:
            self._running = False
            self.connected = False
            self.error = reason
        bpy.app.timers.register(lambda: self._refresh_ui(), first_interval=0)

    def _on_message(self, msg: dict):
        op = msg.get("op", "")
        if op == "state":
            idx = msg.get("idx")
            pos = msg.get("pos")
            if isinstance(idx, int) and isinstance(pos, list) and len(pos) == 3:
                self.positions[idx] = pos
        elif op == "frame":
            self.frame_n = msg.get("n", self.frame_n)
            self.frame_dt_ms = msg.get("dt_ms", self.frame_dt_ms)
        elif op == "pong":
            pass
        elif op in ("log", "error"):
            level = msg.get("level", "info")
            text = msg.get("msg", "")
            idx = msg.get("idx")
            prefix = f"[wf idx={idx}] " if idx is not None else "[wf] "
            print(f"[debug bridge] {level}: {prefix}{text}")
        return None  # timers expect None to cancel

    def _refresh_ui(self):
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                area.tag_redraw()
        return None
