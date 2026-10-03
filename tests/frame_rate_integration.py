"""Real engine + zForth mailbox check; run with a freshly built wf_game path.

Requires DISPLAY and the debug bridge. Uses a private process/port and never
changes authored level files. SIGSTOP is an active hitch, not an app suspension.
"""
import json
import math
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time


def main():
    repo = Path(__file__).resolve().parents[1]
    binary = Path(sys.argv[1]).resolve()
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    with tempfile.TemporaryFile(mode="w+") as log:
        process = subprocess.Popen(
            [str(binary), f"-L{repo / 'wflevels/qbert_practice-standalone.iff'}",
             "--debug-port", str(port), "--debug-bind", "127.0.0.1", "--windowed",
             *sys.argv[2:]],
            cwd=repo / "wfsource/source/game", stdout=log, stderr=log,
            env=os.environ.copy())
        connection = None
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise AssertionError("engine exited during startup")
                try:
                    connection = socket.create_connection(("127.0.0.1", port), 0.2)
                    break
                except OSError:
                    time.sleep(0.05)
            assert connection is not None, "bridge did not start"
            connection.settimeout(0.2)
            buffer = bytearray()

            def send(message):
                connection.sendall((json.dumps(message) + "\n").encode())

            def receive_until(predicate, timeout=10):
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    if b"\n" not in buffer:
                        try:
                            data = connection.recv(65536)
                        except socket.timeout:
                            continue
                        assert data, "bridge closed unexpectedly"
                        buffer.extend(data)
                    while b"\n" in buffer:
                        line, _, rest = buffer.partition(b"\n")
                        buffer[:] = rest
                        message = json.loads(line)
                        if predicate(message):
                            return message
                raise AssertionError("timed out waiting for bridge evidence")

            for mailbox in (1800, 1801, 1903, 1907):
                send({"op": "watch", "idx": 5, "mailbox": mailbox})
            send({"op": "reload_script", "idx": 5, "source":
                  "\\ wf diagnostic FPS test\n"
                  "INDEXOF_FRAMERATE read-mailbox 1800 write-mailbox\n"
                  "INDEXOF_FRAMERATE read-mailbox 1801 write-mailbox\n"})
            reply = receive_until(lambda m: m.get("op") in ("script_reloaded", "error"))
            assert reply["op"] == "script_reloaded", reply
            values = {}
            pending = set()

            def snapshot(message, condition, compare_script=True):
                if message.get("op") != "mailbox" or message.get("idx") != 5:
                    return False
                values[message["mailbox"]] = message["value"]
                if not compare_script:
                    return message["mailbox"] == 1903 and condition(values[1903])
                # The bridge's watch set is unordered. Wait for all three changed
                # values before comparing, rather than relying on emission order.
                if message["mailbox"] in (1800, 1801, 1903):
                    pending.add(message["mailbox"])
                if pending != {1800, 1801, 1903}:
                    return False
                pending.clear()
                for key in (1800, 1801):
                    assert math.isclose(values[key], values[1903], abs_tol=1e-5), values
                return condition(values[1903])

            receive_until(lambda m: snapshot(m, lambda fps: fps > 0))
            print("PASS: named zForth reads match the C++ mailbox read; repeated reads agree")

            # Clear pending traffic before introducing the controlled active stall.
            send({"op": "ping"})
            receive_until(lambda m: m.get("op") == "pong")
            process.send_signal(signal.SIGSTOP)
            try:
                time.sleep(0.55)
            finally:
                process.send_signal(signal.SIGCONT)
            receive_until(lambda m: snapshot(m, lambda fps: 0 < fps < 3))
            print(f"PASS: active 550 ms hitch surfaced as {values[1903]:.3f} FPS")
            receive_until(lambda m: snapshot(m, lambda fps: fps > 3))
            print("PASS: next completed frames recover without smoothing")

            send({"op": "pause"})
            receive_until(lambda m: m.get("op") == "paused")
            receive_until(lambda m: snapshot(m, lambda fps: fps > 0, compare_script=False))
            send({"op": "resume"})
            receive_until(lambda m: m.get("op") == "resumed")
            pending.clear()
            receive_until(lambda m: snapshot(m, lambda fps: fps > 0))
            print("PASS: FPS remains available during simulation pause")

            # Existing system write policy must reject writes to the diagnostic slot.
            send({"op": "reload_script", "idx": 5, "source":
                  "\\ wf read-only FPS test\n1 INDEXOF_FRAMERATE write-mailbox\n"})
            process.wait(timeout=10)
            assert process.returncode != 0, "write to read-only FRAMERATE was accepted"
            log.seek(0)
            assert "Attempted to write to mailbox 1903" in log.read(), "unexpected engine failure"
            print("PASS: writes to FRAMERATE follow the existing system mailbox rejection policy")
        except Exception:
            log.seek(0)
            print(log.read()[-6000:], file=sys.stderr)
            raise
        finally:
            if connection:
                connection.close()
            if process.poll() is None:
                process.send_signal(signal.SIGCONT)
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == "__main__":
    main()
