"""scripts/find-chromecast.sh walks the last octet (up, then down) asking each host's Cast descriptor for its model.

The user's rule when a Chromecast is not at its last address: increment the last octet until it is found (its DHCP lease
moved it from .37 to .38 on 2026-10-01). These tests prove the walk with fake Cast servers on loopback addresses
(127.0.0.x all answer on Linux), so no device is needed.
"""
from __future__ import annotations

import http.server
import os
import socket
import subprocess
import threading
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "find-chromecast.sh"
XML = ("<?xml version=\"1.0\"?><root><device><friendlyName>{name}</friendlyName>"
       "<manufacturer>Google</manufacturer><modelName>{model}</modelName></device></root>")


def _server(ip: str, model: str, name: str):
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = XML.format(name=name, model=model).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/xml")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    try:
        srv = http.server.ThreadingHTTPServer((ip, 0), H)
    except OSError:
        pytest.skip(f"cannot bind {ip} here")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _run(*args, cache: Path):
    env = dict(os.environ, XDG_CACHE_HOME=str(cache))
    return subprocess.run([str(SCRIPT), *args], capture_output=True, text=True, timeout=60, env=env)


def test_help_exits_zero():
    r = subprocess.run([str(SCRIPT), "--help"], capture_output=True, text=True, timeout=10)
    assert r.returncode == 0 and "last octet" in r.stdout


def test_walks_up_to_the_new_address(tmp_path):
    srv = _server("127.0.0.4", "Chromecast HD", "Bedroom TV")
    try:
        r = _run("--from", "127.0.0.1", "--span", "6", "--port", str(srv.server_address[1]), cache=tmp_path)
    finally:
        srv.shutdown()
    assert r.returncode == 0, r.stderr
    assert r.stdout.split("\t")[:2] == ["127.0.0.4", "Chromecast HD"]
    assert (tmp_path / "wf" / "chromecast-ip").read_text().strip() == "127.0.0.4"      # remembered for next time


def test_walks_down_when_the_address_dropped(tmp_path):
    srv = _server("127.0.0.2", "Chromecast HD", "Bedroom TV")
    try:
        r = _run("--from", "127.0.0.5", "--span", "6", "--port", str(srv.server_address[1]), cache=tmp_path)
    finally:
        srv.shutdown()
    assert r.returncode == 0 and r.stdout.startswith("127.0.0.2\t")


def test_skips_a_different_model(tmp_path):
    # a Nest Hub at .2 and the Chromecast at .3: starting at .1 must skip the first and return the second
    hub = _server("127.0.0.2", "Google Nest Hub Max", "kitchen")
    port = hub.server_address[1]
    try:
        cc = http.server.ThreadingHTTPServer(("127.0.0.3", port), type(hub.RequestHandlerClass.__name__, (hub.RequestHandlerClass,), {}))
    except OSError:
        hub.shutdown()
        pytest.skip("cannot bind the fixed port on 127.0.0.3")
    cc.RequestHandlerClass.do_GET = lambda self: (
        self.send_response(200), self.send_header("Content-Length", str(len(XML.format(name="Bedroom TV", model="Chromecast HD")))),
        self.end_headers(), self.wfile.write(XML.format(name="Bedroom TV", model="Chromecast HD").encode()))
    threading.Thread(target=cc.serve_forever, daemon=True).start()
    try:
        r = _run("--from", "127.0.0.1", "--span", "4", "--port", str(port), cache=tmp_path)
    finally:
        hub.shutdown()
        cc.shutdown()
    assert r.returncode == 0 and r.stdout.startswith("127.0.0.3\t") and "Chromecast HD" in r.stdout


def test_exit_one_when_nothing_matches(tmp_path):
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    free = s.getsockname()[1]
    s.close()                                                  # nothing listens on this port
    r = _run("--from", "127.0.0.1", "--span", "2", "--port", str(free), cache=tmp_path)
    assert r.returncode == 1 and "no host matching" in r.stderr
