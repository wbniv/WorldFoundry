"""Drive tests/level_script_vm.cc: every actor script of an exported .lev, run like the engine runs it.

    vm = LevelScriptVM(Path('wflevels/qbert_practice/qbert_practice.lev'), build_dir)
    vm.step(60, 0); vm.get(400, 401); vm.errors()

The prelude is the engine's own: kCoreBootstrap and the mailbox bridge words are read
from engine/stubs/scripting_zforth.cc, and every INDEXOF_ constant from
wfsource/source/mailbox/mailbox.inc, so a script that compiles here compiles in the engine.
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / 'engine/vendor/zforth-41db72d1/src/zforth'


def prelude() -> str:
    src = (ROOT / 'engine/stubs/scripting_zforth.cc').read_text()
    core = src[src.index('static const char* kCoreBootstrap ='):src.index('void Init(')]
    core = re.sub(r'//[^\n]*', '', core)
    text = ''.join(ast.literal_eval(x) for x in re.findall(r'"(?:\\.|[^"\\])*"', core))
    text += '\n: read-mailbox 128 sys ; : write-mailbox 129 sys ; : write-actor-mailbox 130 sys ; : read-actor-mailbox 152 sys ;\n'
    mailbox = (ROOT / 'wfsource/source/mailbox/mailbox.inc').read_text()
    for name, value in re.findall(r'MAILBOXENTRY\(\s*(\w+)\s*,\s*(\d+)', mailbox):
        text += f'{value} constant INDEXOF_{name}\n'
    return text


def level_scripts(lev: Path) -> list[tuple[int, str]]:
    """(actor index, script) per scripted object; actor index = 1-based object order in the .lev."""
    out = []
    for index, block in enumerate(lev.read_text().split("{ 'OBJ'")[1:], start=1):
        m = re.search(r'\{ \'STR\' \{ \'NAME\' "Script" \} \{ \'STR\' ("(?:\\.|[^"\\])*")', block)
        if m:
            out.append((index, json.loads(m.group(1))))
    return out


def build(build_dir: Path) -> Path:
    binary = build_dir / 'level_script_vm'
    obj = build_dir / 'zforth.o'
    subprocess.run(['cc', '-O1', '-c', '-I' + str(ROOT / 'engine/stubs'), '-I' + str(VENDOR),
                    str(VENDOR / 'zforth.c'), '-o', str(obj)], check=True)
    subprocess.run(['c++', '-std=c++17', '-O1', '-I' + str(ROOT / 'engine/stubs'), '-I' + str(VENDOR),
                    str(ROOT / 'tests/level_script_vm.cc'), str(obj), '-lm', '-o', str(binary)], check=True)
    return binary


class LevelScriptVM:
    def __init__(self, lev: Path, build_dir: Path, binary: Path | None = None):
        build_dir.mkdir(parents=True, exist_ok=True)
        binary = binary or build(build_dir)
        (build_dir / 'prelude.fth').write_text(prelude())
        with open(build_dir / 'scripts.txt', 'wb') as f:
            for actor, script in level_scripts(lev):
                data = script.encode()
                f.write(f'{actor}\n{len(data)}\n'.encode() + data + b'\n')
        self.proc = subprocess.Popen([str(binary), str(build_dir / 'prelude.fth'), str(build_dir / 'scripts.txt')],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.frame = 0

    def _cmd(self, line: str, reply: bool = False) -> str | None:
        self.proc.stdin.write(line + '\n')
        self.proc.stdin.flush()
        if not reply:
            return None
        out = self.proc.stdout.readline()
        if not out:
            raise RuntimeError('level_script_vm exited: ' + self.proc.stderr.read())
        return out.strip()

    def step(self, frames: int, bits: int = 0) -> None:
        self._cmd(f'step {frames} {bits}')
        self.frame += frames

    def set(self, mailbox: int, value: float) -> None:
        self._cmd(f'set {mailbox} {value}')

    def get(self, *mailboxes: int) -> list[float]:
        return [float(v) for v in self._cmd('get ' + ' '.join(map(str, mailboxes)), reply=True).split()[1:]]

    def errors(self) -> tuple[int, list[tuple[int, int, int]]]:
        self.proc.stdin.write('errors\n')
        self.proc.stdin.flush()
        total = int(self.proc.stdout.readline().split()[1])
        rows = []   # (actor, aborts, first zf_result); one row per script that aborted
        while sum(r[1] for r in rows) < total:
            rows.append(tuple(int(x) for x in self.proc.stdout.readline().split()[1:]))
        return total, rows

    def run_until(self, mailbox: int, value: float, limit: int, bits: int = 0) -> int | None:
        """Step one frame at a time until `mailbox` == value; return frames taken or None."""
        for n in range(1, limit + 1):
            self.step(1, bits)
            if self.get(mailbox)[0] == value:
                return n
        return None

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.stdin.close()
            self.proc.wait(timeout=10)
