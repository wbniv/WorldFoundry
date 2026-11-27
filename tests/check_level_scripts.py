#!/usr/bin/env python3
"""Compile every actor script of every level source on the current engine; name each level that fails.

    python3 tests/check_level_scripts.py [--lev PATH ...] [--legacy-opener] [-v]
    task test-level-scripts            # the same, in the linux-test container

The roster is every tracked ``wflevels/**/*.lev`` plus any ``--lev`` given (a generated,
gitignored source such as ``wflevels/pilot_demo/pilot_demo.lev``). Each level gets a fresh
zForth context holding the engine's dictionary, read from the engine's own sources so it
cannot drift from what ``forth_engine::Init`` defines:

* ``kCoreBootstrap`` and every ``zf_eval(&g_ctx, "...")`` literal and ``{ "name", "N sys" }``
  table in ``Init()`` of ``engine/stubs/scripting_zforth.cc`` (an ``Init()`` eval of any other
  form stops the run: extend this extractor rather than guess);
* the math words of ``engine/stubs/forth_math_zforth.hpp`` (``ZF_SYSCALL_USER + custom``);
* the ``INDEXOF_*`` constants of ``wfsource/source/mailbox/mailbox.inc`` and the
  ``JOYSTICK_BUTTON_*`` table of ``engine/stubs/scripting_stub.cc``, as ``AddConstantArray``
  defines them.

``tests/level_script_compile.cc`` then strips the opener and splits each script with the
engine's ``forth_source.hp`` and compiles it like ``RunScript``. Nothing runs, so this is
fast and needs no GL; it catches a script that no longer compiles (an unknown word, a
malformed opener line, a word the engine dropped). Exit 1 when any level fails.

``--legacy-opener`` compiles with RunScript's opener handling from before 00978ee7d
(2026-09-25: drop the first non-blank line whatever it holds), to show what that commit changed.

Regression guard for docs/plans/2026-11-27-level-scripts-and-rebuilds.md. Needs cc and c++.
"""
from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Sources known not to compile, each with why; reported on every run, and a listed source that
# compiles again fails the run so the entry is removed. Nothing ships from these files.
KNOWN_BROKEN = {
    'wflevels/main_game/main_game.lev':
        'decompiled (cff9dc34b): its Script fields hold undecoded bytes, not the scripts',
    'wflevels/marble-madness/mm_fromscratch.lev':
        "blender_mm_fromscratch.py writes the opener as r'\\\\ wf' (two backslashes)",
    'wflevels/marble-madness/mm_intermediate.lev':
        "blender_mm_intermediate.py writes the opener as r'\\\\ wf' (two backslashes)",
    'wflevels/marble-madness/mm_practice_rom.lev':
        "blender_mm_practice_rom.py writes the opener as r'\\\\ wf' (two backslashes)",
}
VENDOR = ROOT / 'engine/vendor/zforth-41db72d1/src/zforth'
ZF_SYSCALL_USER = 128
C_STRING = r'"(?:\\.|[^"\\])*"'


def strip_c_comments(src: str) -> str:
    """Remove // and /* */ comments, leaving string and char literals intact."""
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c in '"\'':
            j = i + 1
            while j < n and src[j] != c:
                j += 2 if src[j] == '\\' else 1
            out.append(src[i:j + 1])
            i = j + 1
        elif src.startswith('//', i):
            while i < n and src[i] != '\n':
                i += 1
        elif src.startswith('/*', i):
            i = src.index('*/', i) + 2
        else:
            out.append(c)
            i += 1
    return ''.join(out)


def c_literals(text: str) -> str:
    return ''.join(ast.literal_eval(x) for x in re.findall(C_STRING, text))


def engine_prelude() -> str:
    src = strip_c_comments((ROOT / 'engine/stubs/scripting_zforth.cc').read_text())
    core = re.compile(rf'static const char\* kCoreBootstrap =\s*((?:{C_STRING}\s*)+);').search(src)
    if not core:
        raise SystemExit('check_level_scripts: kCoreBootstrap not found in scripting_zforth.cc')
    parts = [c_literals(core.group(1))]

    init = src[src.index('void Init(MailboxesManager& mgr)'):src.index('void Shutdown()')]
    calls = 0
    for m in re.finditer(r'zf_eval\(\s*&g_ctx\s*,\s*(.*?)\)\s*(?:!=|;)', init, re.S):
        arg = m.group(1).strip()
        calls += 1
        if arg == 'kCoreBootstrap':
            continue
        if arg == 'buf':      # the table loops below
            continue
        if not re.fullmatch(rf'(?:{C_STRING}\s*)+', arg):
            raise SystemExit(f'check_level_scripts: Init() evaluates {arg!r}; teach engine_prelude() about it')
        parts.append(c_literals(arg))
    if calls < 10:
        raise SystemExit(f'check_level_scripts: found only {calls} zf_eval calls in Init(); extractor out of date')
    tables = re.findall(r'\{\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\}', init)
    if not tables:
        raise SystemExit('check_level_scripts: no { "name", "body" } word tables in Init(); extractor out of date')
    parts += [f': {name} {body} ;' for name, body in tables]
    if 'wf::forthmath::kWords' in init:
        math = (ROOT / 'engine/stubs/forth_math_zforth.hpp').read_text()
        words = re.findall(r'\{\s*"([^"]+)"\s*,\s*(\d+)\s*,', math[math.index('kWords[]'):])
        if not words:
            raise SystemExit('check_level_scripts: no math words in forth_math_zforth.hpp')
        parts += [f': {name} {ZF_SYSCALL_USER + int(custom)} sys ;' for name, custom in words]

    # One syscall id, one word: the engine's dispatch tests ids in order, so a second word on a
    # taken id is silently shadowed (FSN's node-kind/x/y behind read-actor-mailbox and random).
    owners: dict[int, set[str]] = {}
    for name, sysid in re.findall(r':\s+(\S+)\s+(\d+)\s+sys\s+;', '\n'.join(parts)):
        owners.setdefault(int(sysid), set()).add(name)
    shared = {i: sorted(n) for i, n in owners.items() if len(n) > 1}
    if shared:
        raise SystemExit('check_level_scripts: engine words share a syscall id (scripting_zforth.cc): '
                         + '; '.join(f'{i} = {" ".join(n)}' for i, n in sorted(shared.items())))

    mailbox = (ROOT / 'wfsource/source/mailbox/mailbox.inc').read_text()
    for name, value in re.findall(r'MAILBOXENTRY\(\s*(\w+)\s*,\s*(-?\d+)', mailbox):
        parts.append(f': INDEXOF_{name} {value} ;')
    stub = (ROOT / 'engine/stubs/scripting_stub.cc').read_text()
    joystick = stub[stub.index('joystickArray[]'):]
    for name, value in re.findall(r'\{\s*"(JOYSTICK_BUTTON_\w+)"\s*,\s*(\d+)\s*\}', joystick[:joystick.index('};')]):
        parts.append(f': {name} {value} ;')
    return '\n'.join(parts) + '\n'


def iff_unescape(body: str) -> str:
    """iffcomp-rs writer.rs string escapes: \\t \\n \\\\ \\" and \\<decimal>; anything else literal."""
    out, i = [], 0
    while i < len(body):
        c = body[i]
        if c != '\\' or i + 1 >= len(body):
            out.append(c)
            i += 1
            continue
        nxt = body[i + 1]
        if nxt in 'tn\\"':
            out.append({'t': '\t', 'n': '\n', '\\': '\\', '"': '"'}[nxt])
            i += 2
        elif nxt.isdigit():
            j = i + 1
            while j < len(body) and body[j].isdigit():
                j += 1
            out.append(chr(int(body[i + 1:j]) & 0xFF))
            i = j
        else:
            out.append(c + nxt)
            i += 2
    return ''.join(out)


SCRIPT_FIELD = re.compile(r'\{\s*\'STR\'\s*\{\s*\'NAME\'\s*"Script"\s*\}\s*\{\s*\'STR\'\s*("(?:\\.|[^"\\])*")')


def level_scripts(lev: Path) -> list[tuple[int, str]]:
    """(actor index, script) per scripted object, actor index = 1-based object order."""
    out = []
    for index, block in enumerate(lev.read_text(errors='replace').split("{ 'OBJ'")[1:], start=1):
        m = SCRIPT_FIELD.search(block)
        if m:
            out.append((index, iff_unescape(m.group(1)[1:-1])))
    return out


def roster(extra: list[Path]) -> list[Path]:
    tracked = subprocess.run(['git', '-C', str(ROOT), 'ls-files', '-z', 'wflevels'],
                             check=True, capture_output=True).stdout.decode().split('\0')
    levs = sorted(ROOT / p for p in tracked if p.endswith('.lev') and (ROOT / p).exists())
    return levs + [p.resolve() for p in extra if p.resolve() not in levs]


def build(work: Path) -> Path:
    obj, binary = work / 'zforth.o', work / 'level_script_compile'
    inc = ['-I' + str(ROOT / 'engine/stubs'), '-I' + str(VENDOR)]
    subprocess.run(['cc', '-O1', '-c', *inc, str(VENDOR / 'zforth.c'), '-o', str(obj)], check=True)
    subprocess.run(['c++', '-std=c++17', '-O1', '-Wall', *inc, str(ROOT / 'tests/level_script_compile.cc'),
                    str(obj), '-lm', '-o', str(binary)], check=True)
    return binary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--lev', type=Path, action='append', default=[], help='also check this .lev (repeatable)')
    ap.add_argument('--legacy-opener', action='store_true', help="compile with RunScript's pre-00978ee7d opener handling")
    ap.add_argument('-v', '--verbose', action='store_true', help='list every level, not only failures')
    args = ap.parse_args()

    levs = roster(args.lev)
    with tempfile.TemporaryDirectory(prefix='level-scripts-') as tmp:
        work = Path(tmp)
        binary = build(work)
        (work / 'prelude.fth').write_text(engine_prelude())
        with open(work / 'scripts.txt', 'wb') as f:
            for lev in levs:
                f.write(f'L {lev.relative_to(ROOT) if lev.is_relative_to(ROOT) else lev}\n'.encode())
                for actor, script in level_scripts(lev):
                    data = script.encode()
                    f.write(f'{actor}\n{len(data)}\n'.encode() + data + b'\n')
        cmd = [str(binary)] + (['--legacy-opener'] if args.legacy_opener else []) + [str(work / 'prelude.fth'), str(work / 'scripts.txt')]
        res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        sys.stderr.write(res.stdout + res.stderr)
        return 2

    fails: dict[str, list[str]] = {}
    totals = [0, 0, 0, 0]
    rows = []
    for line in res.stdout.splitlines():
        if line.startswith('FAIL '):
            _, level, actor, stage, why = line.split(' ', 4)
            fails.setdefault(level, []).append(f'actor {actor} ({stage}): unknown token {why!r}'
                                               if not why.startswith('zf_result') else f'actor {actor} ({stage}): {why}')
        elif line.startswith('LEVEL '):
            _, level, *nums = line.split()
            nums = list(map(int, nums))
            totals = [t + n for t, n in zip(totals, nums)]
            rows.append((level, nums))
    mode = ' (legacy opener)' if args.legacy_opener else ''
    known = {} if args.legacy_opener else KNOWN_BROKEN
    for level, (scripts, compiled, pilot, failed) in rows:
        tag = 'FAIL' if failed and level not in known else 'known' if failed else 'STALE' if level in known else 'ok'
        if tag != 'ok' or args.verbose:
            print(f'{tag:5} {level}: {compiled}/{scripts - pilot} compiled'
                  + (f', {pilot} PILOT skipped' if pilot else '')
                  + (f'; known broken: {known[level]}' if level in known and failed else '')
                  + ('; listed in KNOWN_BROKEN but compiles now: remove the entry' if tag == 'STALE' else ''))
            if tag == 'FAIL' or args.verbose:
                for why in fails.get(level, []):
                    print(f'        {why}')
    bad = sorted(level for level in fails if level not in known)
    stale = sorted(level for level, nums in rows if level in known and not nums[3])
    in_known = sum(nums[3] for level, nums in rows if level in known)
    print(f'{len(rows)} levels{mode}, {totals[0]} scripts: {totals[1]} compiled, {totals[2]} PILOT, '
          f'{in_known} in {len(fails) - len(bad)} known-broken sources, {totals[3] - in_known} failing elsewhere; '
          f'{len(bad)} levels FAIL' + (': ' + ', '.join(bad) if bad else '')
          + (f'; {len(stale)} STALE: ' + ', '.join(stale) if stale else ''))
    return 1 if bad or stale else 0


if __name__ == '__main__':
    sys.exit(main())
