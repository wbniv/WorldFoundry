"""Minimal pure-socket client for the wf_game debug bridge.

Standalone (no bpy) so it can drive pytest harnesses. Speaks the
newline-delimited JSON protocol on TCP/7777 (or whatever --debug-port set).
"""
from __future__ import annotations

import json
import socket
import threading
import time
from typing import Any, Callable


class BridgeClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 7777, timeout: float = 5.0):
        self.host = host
        self.port = port
        self._sock: socket.socket | None = None
        self._buf = b""
        self._lock = threading.Lock()
        self._listeners: list[Callable[[dict], None]] = []
        self._inbox: list[dict] = []
        self._reader: threading.Thread | None = None
        self._running = False
        # State the reader thread updates from broadcasts:
        self.mailbox_values: dict[tuple[int, int], float] = {}
        # Connect with retries (bridge may take a moment to bind).
        deadline = time.time() + timeout
        last_err: Exception | None = None
        while time.time() < deadline:
            try:
                self._sock = socket.create_connection((host, port), timeout=2.0)
                break
            except OSError as e:
                last_err = e
                time.sleep(0.2)
        if self._sock is None:
            raise RuntimeError(f"could not connect to {host}:{port}: {last_err}")
        self._sock.settimeout(0.05)
        self._running = True
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def close(self) -> None:
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
        if self._reader and self._reader.is_alive():
            self._reader.join(timeout=2.0)

    # ── Protocol ─────────────────────────────────────────────────────────────

    def send(self, msg: dict) -> None:
        line = (json.dumps(msg, separators=(",", ":")) + "\n").encode()
        assert self._sock is not None
        self._sock.sendall(line)

    def ping(self) -> None:
        self.send({"op": "ping"})

    def set_mailbox(self, mailbox: int, value: int, idx: int = 0) -> None:
        self.send({"op": "set_mailbox", "idx": idx, "mailbox": mailbox, "value": value})

    def inject_input(self, slot: str, value: int, duration_frames: int = 0) -> None:
        self.send({"op": "inject_input", "slot": slot, "value": value,
                   "duration_frames": duration_frames})

    def watch(self, idx: int, mailbox: int) -> None:
        self.send({"op": "watch", "idx": idx, "mailbox": mailbox})

    def unwatch(self, idx: int, mailbox: int) -> None:
        self.send({"op": "unwatch", "idx": idx, "mailbox": mailbox})

    def undo_step(self) -> None:
        self.send({"op": "undo_step"})

    def revert_all(self) -> None:
        self.send({"op": "revert_all"})

    # ── Reader loop ──────────────────────────────────────────────────────────

    def _read_loop(self) -> None:
        assert self._sock is not None
        while self._running:
            try:
                data = self._sock.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                return
            if not data:
                return
            self._buf += data
            while b"\n" in self._buf:
                line, self._buf = self._buf.split(b"\n", 1)
                if not line.strip():
                    continue
                try:
                    msg = json.loads(line.decode("utf-8", errors="replace"))
                except json.JSONDecodeError:
                    continue
                self._dispatch(msg)

    def _dispatch(self, msg: dict) -> None:
        with self._lock:
            self._inbox.append(msg)
            if msg.get("op") == "mailbox":
                idx = msg.get("idx")
                mbx = msg.get("mailbox")
                val = msg.get("value")
                if isinstance(idx, int) and isinstance(mbx, int) and val is not None:
                    self.mailbox_values[(idx, mbx)] = float(val)

    # ── Test helpers ─────────────────────────────────────────────────────────

    def wait_for(self, predicate: Callable[[dict], bool], timeout: float = 5.0) -> dict | None:
        """Block until a NEW message matching predicate arrives, or timeout.

        Only considers messages that arrive on/after this call — prior
        replies sitting in the inbox are skipped, so back-to-back ops don't
        accidentally match the previous reply.
        """
        deadline = time.time() + timeout
        with self._lock:
            seen = len(self._inbox)
        while time.time() < deadline:
            with self._lock:
                while seen < len(self._inbox):
                    msg = self._inbox[seen]
                    seen += 1
                    if predicate(msg):
                        return msg
            time.sleep(0.05)
        return None

    def wait_for_mailbox(self, idx: int, mailbox: int, expected: float,
                         timeout: float = 5.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                cur = self.mailbox_values.get((idx, mailbox))
            if cur is not None and abs(cur - expected) < 1e-3:
                return True
            time.sleep(0.05)
        return False


# ── Actor discovery by authored name → runtime index ──────────────────────────
# The engine log identifies actors only by mesh filename + position
# ("actor idx=N mesh=foo.iff ... pos=(x,y,z)"); it carries no authored name
# (the runtime _ObjectOnDisk has no name field — stripped for MCU targets).
# When many actors share one mesh datablock (mesh-sharing / P2b), the mesh name
# no longer identifies an instance, so we bridge the authored NAME → idx through
# POSITION: the .lev has both name and Position; the log has idx and pos.
import re as _re                                                    # noqa: E402
from pathlib import Path as _Path                                   # noqa: E402

_LEV_OBJ_NAME_RE = _re.compile(r"\{\s*'NAME'\s*\"([^\"]+)\"\s*\}")
_LEV_POS_RE = _re.compile(
    r"'VEC3'\s*\{\s*'NAME'\s*\"Position\"\s*\}\s*\{\s*'DATA'\s*"
    r"([-\d.]+)\(1\.15\.16\)\s+([-\d.]+)\(1\.15\.16\)\s+([-\d.]+)\(1\.15\.16\)")
_LOG_ACTOR_POS_RE = _re.compile(
    r"actor idx=(\d+) mesh=\S+ mobility=\S+ pos=\(([-\d.]+),([-\d.]+),([-\d.]+)\)")


def lev_name_to_pos(lev_path) -> dict[str, tuple[float, float, float]]:
    """Parse a text `.lev`: return {authored object name: (x, y, z)}."""
    text = _Path(lev_path).read_text(errors="ignore")
    out: dict[str, tuple[float, float, float]] = {}
    for chunk in text.split("'OBJ'")[1:]:
        nm = _LEV_OBJ_NAME_RE.search(chunk)          # first NAME = the object's
        pm = _LEV_POS_RE.search(chunk)
        if nm and pm:
            out[nm.group(1)] = (float(pm.group(1)), float(pm.group(2)), float(pm.group(3)))
    return out


def discover_by_pos(log_path, lev_path, want: set[str],
                    timeout: float = 8.0, tol: float = 0.6) -> dict[str, int]:
    """Map authored object names → runtime actor idx via position.

    Robust to mesh-sharing (where several actors log the same mesh name). Only
    valid for anchored/static actors, whose runtime pos equals the authored one.
    """
    name_pos = lev_name_to_pos(lev_path)
    missing = [n for n in want if n not in name_pos]
    if missing:
        raise KeyError(f"names not found in {lev_path}: {missing}")
    targets = {n: name_pos[n] for n in want}
    deadline = time.time() + timeout
    found: dict[str, int] = {}
    while time.time() < deadline and len(found) < len(want):
        if _Path(log_path).exists():
            idx_pos = [(int(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4)))
                       for m in _LOG_ACTOR_POS_RE.finditer(_Path(log_path).read_text(errors="ignore"))]
            for nm, (tx, ty, tz) in targets.items():
                if nm in found:
                    continue
                for idx, x, y, z in idx_pos:
                    if abs(x - tx) < tol and abs(y - ty) < tol and abs(z - tz) < tol:
                        found[nm] = idx
                        break
        if len(found) < len(want):
            time.sleep(0.1)
    return found
