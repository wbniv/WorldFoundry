"""zfhost.py: build and drive the standalone zForth host (zf_host.c) for testing level scripts without the engine.

The bootstrap words are taken from the engine's own text (kCoreBootstrap in engine/stubs/scripting_zforth.cc), so a test runs the same dictionary the game does.
"""
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ENGINE = ROOT / "engine"
BIN = Path.home() / "tmp" / "zf_host"


def build():
    BIN.parent.mkdir(parents=True, exist_ok=True)
    src = ENGINE / "vendor/zforth-41db72d1/src/zforth"
    cmd = ["cc", "-O1", f"-I{ENGINE / 'stubs'}", f"-I{src}", str(HERE / "zf_host.c"), str(src / "zforth.c"), "-lm", "-o", str(BIN)]
    subprocess.run(cmd, check=True)
    return BIN


def engine_bootstrap():
    """The engine's kCoreBootstrap as one Forth text (the C string literals concatenated, // comments dropped)."""
    text = (ENGINE / "stubs/scripting_zforth.cc").read_text()
    body = text[text.index("kCoreBootstrap ="):]
    body = body[:body.index("\n    ;")]
    out = []
    for line in body.splitlines()[1:]:
        line = re.sub(r"//.*$", "", line)
        out += re.findall(r'"((?:[^"\\]|\\.)*)"', line)
    return "".join(out)


def fish_trig():
    """fish-wrap, fish-sin and fish-cos, taken from the aquarium's own clownfish_idle.fth."""
    keep = []
    for line in (ROOT / "wflevels/aquarium/clownfish_idle.fth").read_text().splitlines():
        if line.startswith((": fish-wrap", ": fish-sin", ": fish-cos")) or (keep and line.startswith("  2 * dup 1 swap")):
            keep.append(line)
    return "\n".join(keep)


class Host:
    def __init__(self):
        if not BIN.exists():
            build()
        self.p = subprocess.Popen([str(BIN)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        r = self.eval(engine_bootstrap())                                  # one eval of the whole text, like the engine
        assert r == "ok", r
        for line in [": read-mailbox 128 sys ;", ": write-mailbox 129 sys ;", ": r@ ' lit , 0 , ' pickr , ; immediate"]:     # the engine defines r@ after its bootstrap
            assert self.eval(line) == "ok"

    def cmd(self, s):
        self.p.stdin.write(s + "\n")
        self.p.stdin.flush()
        return self.p.stdout.readline().strip()

    def eval(self, text):
        return self.cmd("E " + text)

    def load(self, path):
        return self.cmd("F " + str(path))

    def write(self, idx, val):
        self.p.stdin.write(f"W {idx} {val!r}\n")

    def read(self, idx, n=1):
        vals = [float(x) for x in self.cmd(f"R {idx} {n}").split()]
        return vals if n > 1 else vals[0]

    def size(self):
        return int(self.cmd("S"))

    def close(self):
        self.p.stdin.close()
        self.p.wait()
