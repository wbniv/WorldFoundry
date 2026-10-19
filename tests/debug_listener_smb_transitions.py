"""Continuous real SMB flag/axe transitions with bridge reconnects.

Run: DISPLAY=:0 python3 tests/debug_listener_smb_transitions.py /path/to/wf_game
Requires a desktop debug build, the four-world menu bundle, and X/GL.
No authored assets are changed; a temporary cwd selects the menu bundle.
"""
import argparse
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile
import time

from debug_bridge_client import BridgeClient, lev_name_to_pos


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("--laps", type=int, default=2)
    args = parser.parse_args()
    assert args.laps > 0
    repo = Path(__file__).resolve().parents[1]
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix="wf-smb-reconnect-") as directory:
        cwd = Path(directory)
        (cwd / "cd.iff").symlink_to(repo / "wflevels/smb-menu-cd.iff")
        log = cwd / "engine.log"
        with log.open("w") as output:
            proc = subprocess.Popen(
                [str(args.binary.resolve()), "--menu-input=wait:10,a",
                 "--debug-port", str(port), "--debug-bind", "127.0.0.1",
                 "--debug-print-actors", "--frame-rate-checks", "--windowed"],
                cwd=cwd, stdout=output, stderr=subprocess.STDOUT,
                env={**os.environ, "WF_REST_PORT": "0"})
            client = None
            results = []
            try:
                client = BridgeClient(port=port, timeout=20)
                for transition in range(args.laps * 4):
                    world = transition % 4 + 1
                    text = log.read_text(errors="replace")
                    player = int(re.findall(r"\[Actor\] idx=(\d+) class=22 ", text)[-1])
                    for mailbox in (1903, 1862, 5000):
                        client.watch(player, mailbox)
                    deadline = time.monotonic() + 5
                    while client.mailbox_values.get((player, 1903), 0) <= 0:
                        assert time.monotonic() < deadline, "no FPS after reconnect"
                        time.sleep(.05)
                    fps_before = client.mailbox_values[(player, 1903)]
                    name = f"smb_w1_{world}"
                    trigger = "w14_axe" if world == 4 else "flagpole_trigger"
                    position = lev_name_to_pos(repo / "wflevels" / name / f"{name}.lev")[trigger]
                    celebrated = requested = False
                    deadline = time.monotonic() + 20
                    while time.monotonic() < deadline:
                        assert proc.poll() is None, "engine exited during transition"
                        if not celebrated:
                            for mb, value in zip((3009, 3010, 3011, 3018, 3019, 3020),
                                                 (*position, 0, 0, 0)):
                                client.set_mailbox(mb, value, idx=player)
                        celebrated |= client.mailbox_values.get((player, 1862), 0) >= 1
                        requested |= celebrated and client.mailbox_values.get((player, 5000)) == world % 4
                        text = log.read_text(errors="replace")
                        resets = len(re.findall(r"FPS CHECK PASS backend=zforth raw=0\.000000", text))
                        if celebrated and requested and resets >= transition + 2:
                            break
                        time.sleep(.1)
                    assert celebrated and requested and resets >= transition + 2, (world, celebrated, requested, resets)
                    client.close()
                    client = BridgeClient(port=port, timeout=10)
                    player = int(re.findall(r"\[Actor\] idx=(\d+) class=22 ", log.read_text())[-1])
                    client.watch(player, 1903)
                    deadline = time.monotonic() + 5
                    while client.mailbox_values.get((player, 1903), 0) <= 0:
                        assert time.monotonic() < deadline, "reconnected but no mailbox traffic"
                        time.sleep(.05)
                    result = {"lap": transition // 4 + 1, "world": world,
                              "trigger": trigger, "baseline_resets": resets,
                              "fps_before": fps_before, "fps_after": client.mailbox_values[(player, 1903)]}
                    results.append(result)
                    print(json.dumps(result), flush=True)
                assert not re.search(r"accept\(\) failed|bind/listen.*failed|ASSERTION FAILED|FPS CHECK FAIL|terminate called", log.read_text())
                print(f"PASS: {len(results)} continuous transitions in one engine process")
            except Exception:
                print(log.read_text(errors="replace")[-8000:])
                raise
            finally:
                if client:
                    client.close()
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()


if __name__ == "__main__":
    main()
