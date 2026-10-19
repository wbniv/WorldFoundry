"""Manual headed Chrome FPS/lifecycle check; requires Python Playwright and X11.

Uses an isolated profile and real window visibility, without Playwright's
forced-visible emulation. Never attaches to the user's browser session.
"""
import argparse
import functools
import http.server
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

p = argparse.ArgumentParser()
p.add_argument("build", type=Path)
p.add_argument("--editor", action="store_true")
p.add_argument("--chrome", default=shutil.which("google-chrome"))
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
assert a.chrome, "Chrome executable not found; pass --chrome"
a.output.mkdir(parents=True, exist_ok=True)
repo = Path(__file__).resolve().parent.parent
entry = "wf-edit.html" if a.editor else "wf_game.html"
assert (a.build / entry).is_file(), f"build {entry} first"

class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_): pass

server = http.server.ThreadingHTTPServer(("127.0.0.1", 0),
    functools.partial(QuietHandler, directory=str(a.build.resolve())))
threading.Thread(target=server.serve_forever, daemon=True).start()
query = "wfenv=WF_FRAME_RATE_CHECKS%3D1" if a.editor else "level=snowgoons-standalone"
url = f"http://127.0.0.1:{server.server_port}/{entry}?{query}"
logs, errors = [], []
log = a.output / "runtime.log"

def samples():
    return [(float(raw), int(epoch)) for raw, epoch in
        re.findall(r"FPS CHECK PASS backend=\S+ raw=([\d.]+) script=[\d.]+ generation=(\d+)", "\n".join(logs))]

def await_sample(page, predicate):
    deadline = time.monotonic() + 30
    while not predicate(samples()) and time.monotonic() < deadline:
        page.wait_for_timeout(250)
    assert predicate(samples()), "missing FPS sample; see runtime.log"

try:
    # Chrome child processes can finish writing after the main process exits.
    with sync_playwright() as pw, tempfile.TemporaryDirectory(prefix="wf-fps-chrome-", ignore_cleanup_errors=True) as profile:
        chrome = subprocess.Popen([a.chrome, "--no-sandbox", "--remote-debugging-port=0",
            "--user-data-dir=" + profile, "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        browser = None
        try:
            port_file = Path(profile) / "DevToolsActivePort"
            deadline = time.monotonic() + 30
            while not port_file.exists() and time.monotonic() < deadline: time.sleep(.1)
            port = port_file.read_text().splitlines()[0]
            browser = pw.chromium.connect_over_cdp("http://127.0.0.1:" + port, no_defaults=True)
            context = browser.contexts[0]
            page = context.pages[0] if context.pages else context.new_page()
            page.on("console", lambda m: logs.append(m.text))
            page.on("pageerror", lambda e: errors.append(str(e)))
            if not a.editor:
                def enable_checks(route):
                    response = route.fetch()
                    body, count = re.subn(r"arguments:\s*([A-Za-z_$][\w$]*),",
                        r'arguments:\1.concat(["--frame-rate-checks"]),', response.text(), count=1)
                    assert count == 1, "shell arguments not found"
                    route.fulfill(response=response, body=body)
                page.route("**/wf_game.html?*", enable_checks)
            page.goto(url, wait_until="networkidle", timeout=60000)
            await_sample(page, lambda rows: any(raw > 0 for raw, _ in rows))
            initial_epoch = max(epoch for _, epoch in samples())
            page.screenshot(path=str(a.output / "frame.png"))
            cdp = context.new_cdp_session(page)
            window = cdp.send("Browser.getWindowForTarget")
            cdp.send("Browser.setWindowBounds", {"windowId":window["windowId"], "bounds":{"windowState":"minimized"}})
            page.wait_for_timeout(500)
            assert page.evaluate("document.hidden"), "Chrome window did not actually hide"
            count = len(samples())
            page.wait_for_timeout(1500)
            assert len(samples()) == count, "frame probes continued while hidden"
            cdp.send("Browser.setWindowBounds", {"windowId":window["windowId"], "bounds":{"windowState":"normal"}})
            page.bring_to_front()
            await_sample(page, lambda rows: any(raw > 0 and epoch > initial_epoch for raw, epoch in rows))
            assert not page.evaluate("document.hidden")
            assert not errors, errors
            if a.editor:
                assert any("wf-edit: HALStart (--editor" in line for line in logs), "not the hosted editor"
            log.write_text("\n".join(logs))
            subprocess.run(["python3", str(repo / "tests/check_frame_rate_log.py"), str(log), "--resume"], check=True)
        finally:
            log.write_text("\n".join(logs + errors))
            if browser: browser.close()
            chrome.terminate()
            try: chrome.wait(timeout=10)
            except subprocess.TimeoutExpired:
                chrome.kill()
                chrome.wait()
finally:
    server.shutdown()
    server.server_close()
