#!/usr/bin/env python3
"""PILOT reference interpreter + driver for World Foundry (Phase 1, Python).

The host-agnostic VM (parser + expression evaluator + control flow) runs .pilot
scenarios against two backends:

  - MockHost   (@tier vm)     — pure language, deterministic, no engine.
  - BridgeHost (@tier engine) — drives a live wf_game over the TCP debug bridge
                                (tests/debug_bridge_client.BridgeClient).

This is the reference implementation that proves the language; the canonical
interpreter is the Phase 2 C++ `pilot_core`, which must pass this same corpus.

Spec:  docs/pilot-language.md
Plan:  docs/plans/2026-05-30-pilot-for-world-foundry-in-engine-object-script-la.md

CLI:   python3 pilot_driver.py FILE.pilot        # run one scenario (vm or engine)
"""
from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Optional

REPO = Path(__file__).resolve().parents[2]            # tests/pilot/ -> repo root
MAILBOX_INC = REPO / "wfsource" / "source" / "mailbox" / "mailbox.inc"
SCREENSHOTS = Path(__file__).resolve().parent / "screenshots"

# Mailboxes below LOCAL_START are global/system and are broadcast only for a
# valid actor index — so they must be watched at idx=1 (the convention every
# verify_smb_*.py uses). Per-actor mailboxes use the actor's own index.
LOCAL_START = 2000


# ─────────────────────────────────────────────────────────────────────────────
# Constants — prefix-free mailbox names from mailbox.inc + joystick buttons.

_BUTTONS = {
    "JOYSTICK_BUTTON_UP": 2048, "JOYSTICK_BUTTON_DOWN": 4096,
    "JOYSTICK_BUTTON_RIGHT": 8192, "JOYSTICK_BUTTON_LEFT": 16384,
    "JOYSTICK_BUTTON_A": 1, "JOYSTICK_BUTTON_B": 2, "JOYSTICK_BUTTON_C": 4,
    "JOYSTICK_BUTTON_D": 8, "JOYSTICK_BUTTON_E": 16, "JOYSTICK_BUTTON_F": 32,
    "JOYSTICK_BUTTON_G": 64, "JOYSTICK_BUTTON_H": 128, "JOYSTICK_BUTTON_I": 256,
    "JOYSTICK_BUTTON_J": 512, "JOYSTICK_BUTTON_K": 1024,
}
_MBENTRY_RE = re.compile(
    r"MAILBOXENTRY\(\s*([A-Za-z_]\w*)\s*,\s*(-?\d+|0[xX][0-9A-Fa-f]+)\s*\)")


def load_constants() -> dict[str, int]:
    """Bare mailbox names (X_POS, TIME, GOLD…) + INDEXOF_ aliases + buttons.

    PILOT exposes mailbox names PREFIX-FREE; the INDEXOF_ aliases are kept only
    for back-compat with the engine's broadcast table (the prefix is a wart the
    project wants gone — we alias, we don't propagate it into scripts).
    """
    consts: dict[str, int] = {}
    consts.update(_BUTTONS)
    for name, v in _BUTTONS.items():                       # BTN_RIGHT, BTN_A, …
        consts[f"BTN_{name.split('_')[-1]}"] = v
    try:
        for m in _MBENTRY_RE.finditer(MAILBOX_INC.read_text(errors="replace")):
            name, val = m.group(1), int(m.group(2), 0)
            consts[name] = val
            consts[f"INDEXOF_{name}"] = val
    except OSError:
        pass
    return consts


CONSTS = load_constants()


def fmt(v: float) -> str:
    """Format a numeric value: integers without a decimal, else minimal."""
    if isinstance(v, bool):
        return "1" if v else "0"
    return f"{v:g}"


class PilotError(Exception):
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Expression evaluator — recursive descent over a tiny token stream.

_TOK_RE = re.compile(r"""\s*(?:
    (?P<num>0[xX][0-9A-Fa-f]+|\d+\.\d+|\.\d+|\d+) |
    (?P<str>"[^"]*") |
    (?P<id>[#$]?[A-Za-z_]\w*) |
    (?P<op><=|>=|<>|//|[-+*/()<>=,&|!])
)""", re.X)

_RELOPS: dict[str, Callable[[float, float], bool]] = {
    "=": lambda a, b: a == b, "<>": lambda a, b: a != b,
    "<": lambda a, b: a < b, "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b, ">=": lambda a, b: a >= b,
}


def tokenize(text: str) -> list[tuple[str, str]]:
    toks: list[tuple[str, str]] = []
    pos = 0
    while pos < len(text):
        if text[pos].isspace():
            pos += 1
            continue
        m = _TOK_RE.match(text, pos)
        if not m or m.end() == pos:
            raise PilotError(f"bad token at {text[pos:]!r}")
        pos = m.end()
        kind = m.lastgroup
        toks.append((kind, m.group()))
    return toks


class Eval:
    """Evaluate an expression against a VM's variables + the host's mailboxes."""

    def __init__(self, toks: list[tuple[str, str]], vm: "PilotVM"):
        self.toks, self.i, self.vm = toks, 0, vm

    def _peek(self) -> Optional[str]:
        return self.toks[self.i][1] if self.i < len(self.toks) else None

    def _next(self) -> tuple[str, str]:
        t = self.toks[self.i]
        self.i += 1
        return t

    def run(self) -> float:
        v = self._or()
        if self.i != len(self.toks):
            raise PilotError(f"trailing tokens: {self.toks[self.i:]}")
        return v

    def _or(self) -> float:
        v = self._and()
        while self._peek() == "|":
            self._next()
            r = self._and()
            v = 1.0 if (v != 0 or r != 0) else 0.0
        return v

    def _and(self) -> float:
        v = self._cmp()
        while self._peek() == "&":
            self._next()
            r = self._cmp()
            v = 1.0 if (v != 0 and r != 0) else 0.0
        return v

    def _cmp(self) -> float:
        v = self._add()
        if self._peek() in _RELOPS:
            op = self._next()[1]
            r = self._add()
            return 1.0 if _RELOPS[op](v, r) else 0.0
        return v

    def _add(self) -> float:
        v = self._mul()
        while self._peek() in ("+", "-"):
            op = self._next()[1]
            r = self._mul()
            v = v + r if op == "+" else v - r
        return v

    def _mul(self) -> float:
        v = self._unary()
        while self._peek() in ("*", "/", "//"):
            op = self._next()[1]
            r = self._unary()
            if op == "*":
                v = v * r
            elif op == "/":                       # Scalar (float) division
                v = v / r if r != 0 else 0.0
            else:                                 # // truncating integer division
                v = float(int(v) // int(r)) if int(r) != 0 else 0.0
        return v

    def _unary(self) -> float:
        if self._peek() == "-":
            self._next()
            return -self._unary()
        if self._peek() == "!":
            self._next()
            return 0.0 if self._unary() != 0 else 1.0
        return self._primary()

    def _primary(self) -> float:
        if self.i >= len(self.toks):
            raise PilotError("unexpected end of expression")
        kind, text = self._next()
        if kind == "num":
            return float(int(text, 0)) if text.lower().startswith("0x") else float(text)
        if kind == "str":
            raise PilotError("string literal in numeric context")
        if text == "(":
            v = self._or()
            if self._peek() != ")":
                raise PilotError("missing )")
            self._next()
            return v
        if kind == "id":
            if text == "mb" and self._peek() == "(":
                self._next()
                args = [self._or()]
                while self._peek() == ",":
                    self._next()
                    args.append(self._or())
                if self._peek() != ")":
                    raise PilotError("missing ) in mb(...)")
                self._next()
                mbx = int(args[0])
                actor = int(args[1]) if len(args) > 1 else self.vm.self_actor
                return self.vm.host.read_mailbox(actor, mbx)
            return self.vm.resolve(text)
        raise PilotError(f"unexpected {text!r}")


# ─────────────────────────────────────────────────────────────────────────────
# Parser — line-oriented; produces statements, a label table, and directives.

VERBS = {
    "T", "TH", "A", "M", "C", "J", "U", "E", "EX", "PA",          # standard
    "PS", "PR", "ST", "IN", "WM", "WB", "WT", "SP", "SF", "SM",   # WF extension
    "WA", "SH", "SR", "SG", "PK", "UD", "RV", "NW", "DL", "BT",
}
_HEAD_RE = re.compile(r"([A-Za-z]+)(\(([^)]*)\))?:")


class Stmt:
    __slots__ = ("verb", "cond", "guard", "operand", "lineno")

    def __init__(self, verb, cond, guard, operand, lineno):
        self.verb, self.cond, self.guard = verb, cond, guard
        self.operand, self.lineno = operand, lineno


class Program:
    def __init__(self):
        self.stmts: list[Stmt] = []
        self.labels: dict[str, int] = {}
        self.directives: list[tuple[str, str]] = []


def _decompose(head: str) -> tuple[str, Optional[str]]:
    if head in VERBS:
        return head, None
    if head[-1] in "YN" and head[:-1] in VERBS:           # TY:, JN:, AN: …
        return head[:-1], head[-1]
    raise PilotError(f"unknown verb {head!r}")


def parse(source: str) -> Program:
    prog = Program()
    for lineno, raw in enumerate(source.splitlines(), 1):
        line = raw.rstrip()
        s = line.strip()
        if not s:
            continue
        # Remark / directive — never an executable statement.
        if s.startswith("R:"):
            body = s[2:].strip()
            if body.startswith("@"):
                parts = body[1:].split(None, 1)
                prog.directives.append((parts[0], parts[1] if len(parts) > 1 else ""))
            continue
        # Label, optionally followed by a statement on the same line.
        if s.startswith("*"):
            m = re.match(r"\*(\S+)\s*(.*)", s)
            prog.labels[m.group(1)] = len(prog.stmts)
            s = m.group(2).strip()
            if not s:
                continue
        m = _HEAD_RE.match(s)
        if not m:
            raise PilotError(f"line {lineno}: not a statement: {s!r}")
        verb, cond = _decompose(m.group(1))
        guard = m.group(3)
        operand = s[m.end():]
        prog.stmts.append(Stmt(verb, cond, guard, operand, lineno))
    return prog


# ─────────────────────────────────────────────────────────────────────────────
# Hosts.

class Host:
    """Effect interface. Engine-control ops are no-ops in the base/mock host."""
    def type(self, text: str, newline: bool) -> None: ...
    def read_mailbox(self, actor: int, mbx: int) -> float: return 0.0
    def set_mailbox(self, actor: int, mbx: int, val: float) -> None: ...
    def pause(self) -> None: ...
    def resume(self) -> None: ...
    def step(self, frames: int) -> None: ...
    def inject(self, slot: str, bits: int, held: int) -> None: ...
    def watch(self, actor: int, mbx: int, off: bool = False) -> None: ...
    def screenshot(self, name: str) -> bool: return True
    def set_transform(self, actor, x, y, z) -> None: ...
    def set_prop(self, actor, key, val) -> None: ...
    def await_mailbox(self, actor, mbx, relop, val, timeout) -> tuple[str, float]:
        raise PilotError("await (A:/WM:) needs an engine host")
    def await_broadcast(self, op, timeout) -> bool: return False
    def wait_seconds(self, secs: float) -> None: ...
    def reload(self, actor, src) -> None: ...
    def pick(self, o, d) -> int: return -1
    def undo(self) -> None: ...
    def revert(self) -> None: ...


class MockHost(Host):
    """Pure-language tier: capture T:/TH: output; mailboxes in-memory."""
    def __init__(self):
        self.out: list[str] = []
        self._mb: dict[tuple[int, int], float] = {}
        self.screenshots: list[str] = []

    def type(self, text, newline):
        self.out.append(text + ("\n" if newline else ""))

    def read_mailbox(self, actor, mbx):
        return self._mb.get((actor, mbx), 0.0)

    def set_mailbox(self, actor, mbx, val):
        self._mb[(actor, mbx)] = val

    @property
    def output(self) -> str:
        return "".join(self.out)


class BridgeHost(Host):
    """Engine tier: drive a live wf_game over the debug bridge."""
    def __init__(self, client):
        self.cli = client
        self.out: list[str] = []
        self.screenshots: list[str] = []
        self._watched: set[tuple[int, int]] = set()
        self._injects: set[str] = set()

    @staticmethod
    def route(actor: int, mbx: int) -> int:
        return 1 if mbx < LOCAL_START else int(actor)   # globals -> idx 1

    def type(self, text, newline):
        line = text + ("\n" if newline else "")
        self.out.append(line)
        sys.stdout.write(line)

    def read_mailbox(self, actor, mbx):
        r = self.route(actor, mbx)
        with self.cli._lock:
            v = self.cli.mailbox_values.get((r, mbx))
        if v is None:
            sys.stderr.write(f"[pilot] mb({mbx}) not watched/seen at idx {r}; -> 0\n")
            return 0.0
        return float(v)

    def set_mailbox(self, actor, mbx, val):
        self.cli.set_mailbox(mbx, val, idx=self.route(actor, mbx))

    def pause(self):
        self.cli.send({"op": "pause"})
        self.cli.wait_for(lambda m: m.get("op") == "paused", timeout=3.0)

    def resume(self):
        self.cli.send({"op": "resume"})

    def step(self, frames):
        for _ in range(max(1, int(frames))):
            self.cli.send({"op": "step"})
            time.sleep(0.03)

    def inject(self, slot, bits, held):
        self._injects.add(slot)
        self.cli.inject_input(slot, int(bits), held)

    def watch(self, actor, mbx, off=False):
        r = self.route(actor, mbx)
        if off:
            self.cli.unwatch(r, mbx)
            self._watched.discard((r, mbx))
        else:
            self.cli.watch(r, mbx)
            self._watched.add((r, mbx))

    def await_mailbox(self, actor, mbx, relop, val, timeout):
        # NEW relational poll — wait_for_mailbox is exact-equality only and
        # cannot express > / >= / <. Poll the broadcast value against the RelOp.
        r = self.route(actor, mbx)
        if (r, mbx) not in self._watched:
            self.watch(actor, mbx)
        cmp = _RELOPS[relop]
        deadline = time.time() + (timeout if timeout else 5.0)
        last = None
        while time.time() < deadline:
            with self.cli._lock:
                cur = self.cli.mailbox_values.get((r, mbx))
            if cur is not None:
                last = float(cur)
                if cmp(last, val):
                    return ("Satisfied", last)
            time.sleep(0.02)
        return ("TimedOut", last if last is not None else 0.0)

    def await_broadcast(self, op, timeout):
        m = self.cli.wait_for(lambda m: m.get("op") == op, timeout=timeout or 5.0)
        return m is not None

    def screenshot(self, name):
        SCREENSHOTS.mkdir(parents=True, exist_ok=True)
        out = SCREENSHOTS / name
        self.cli.send({"op": "screenshot", "filename": str(out)})
        m = self.cli.wait_for(
            lambda m: m.get("op") in ("screenshot_done", "error"), timeout=6.0)
        ok = bool(m) and m.get("op") == "screenshot_done"
        if ok:
            self.screenshots.append(name)
        return ok

    def set_transform(self, actor, x, y, z):
        self.cli.send({"op": "scene:set_transform", "idx": int(actor),
                       "pos": [x, y, z]})

    def set_prop(self, actor, key, val):
        self.cli.send({"op": "scene:set_prop", "idx": int(actor),
                       "key": key, "value": val})

    def wait_seconds(self, secs):
        # LevelClock seconds via TIME(idx=1); the clock advances only on stepped
        # frames, so a paused scenario must interleave ST:. Poll, but cap on wall.
        t = CONSTS.get("TIME", 1906)
        if (1, t) not in self._watched:
            self.watch(1, t)
        with self.cli._lock:
            t0 = self.cli.mailbox_values.get((1, t))
        if t0 is None:
            time.sleep(secs)
            return
        deadline = time.time() + secs + 5.0
        while time.time() < deadline:
            with self.cli._lock:
                cur = self.cli.mailbox_values.get((1, t))
            if cur is not None and cur >= t0 + secs:
                return
            time.sleep(0.02)

    def teardown(self):
        for slot in list(self._injects):
            try:
                self.cli.inject_input(slot, 0, 1)
            except Exception:
                pass
        for (idx, mbx) in list(self._watched):
            try:
                self.cli.unwatch(idx, mbx)
            except Exception:
                pass

    @property
    def output(self) -> str:
        return "".join(self.out)


# ─────────────────────────────────────────────────────────────────────────────
# VM.

class PilotVM:
    def __init__(self, prog: Program, host: Host, self_actor: int = 0):
        self.prog, self.host, self.self_actor = prog, host, self_actor
        self.num: dict[str, float] = {"#last": 0.0}
        self.strv: dict[str, str] = {}
        self.match = False
        self.accept = ""
        self.pc = 0
        self.callstack: list[int] = []
        self.exit_code: Optional[int] = None

    # variable / constant resolution for the evaluator
    def resolve(self, name: str) -> float:
        if name.startswith("#"):
            return self.num.get(name, 0.0)
        if name.startswith("$"):
            try:
                return float(self.strv.get(name, "0"))
            except ValueError:
                return 0.0
        if name in CONSTS:
            return float(CONSTS[name])
        raise PilotError(f"unknown name {name!r}")

    def evalf(self, text: str) -> float:
        return Eval(tokenize(text), self).run()

    def bind(self, name: str, value: float) -> None:
        self.num[name if name.startswith("#") else "#" + name] = float(value)

    def run(self) -> int:
        n = 0
        while self.pc < len(self.prog.stmts) and self.exit_code is None:
            st = self.prog.stmts[self.pc]
            self.pc += 1
            n += 1
            if n > 100000:
                raise PilotError("statement budget exceeded (runaway loop?)")
            self._exec(st)
        return self.exit_code if self.exit_code is not None else 0

    def _exec(self, st: Stmt) -> None:
        if st.cond == "Y" and not self.match:
            return
        if st.cond == "N" and self.match:
            return
        if st.guard is not None and self.evalf(st.guard) == 0:
            return
        getattr(self, f"_do_{st.verb}", self._unknown)(st)

    def _unknown(self, st: Stmt):
        raise PilotError(f"line {st.lineno}: verb {st.verb} not implemented")

    # ── interpolation for T:/TH: ──
    def _interp(self, text: str) -> str:
        out, i = [], 0
        while i < len(text):
            c = text[i]
            if c == "$" and i + 1 < len(text):
                if text[i + 1] == "$":
                    out.append("$"); i += 2; continue
                if text[i + 1] == "#":
                    j = i + 2
                    while j < len(text) and (text[j].isalnum() or text[j] == "_"):
                        j += 1
                    out.append(fmt(self.num.get("#" + text[i + 2:j], 0.0)))
                    i = j; continue
                j = i + 1
                while j < len(text) and (text[j].isalnum() or text[j] == "_"):
                    j += 1
                out.append(self.strv.get("$" + text[i + 1:j], ""))
                i = j; continue
            out.append(c); i += 1
        return "".join(out)

    # ── standard verbs ──
    def _do_T(self, st):  self.host.type(self._interp(st.operand), True)
    def _do_TH(self, st): self.host.type(self._interp(st.operand), False)

    def _do_C(self, st):
        lhs, _, rhs = st.operand.partition("=")
        lhs, rhs = lhs.strip(), rhs.strip()
        if lhs.startswith("mb"):
            toks = tokenize(lhs)
            ev = Eval(toks, self)
            assert toks[0][1] == "mb" and toks[1][1] == "("
            ev.i = 2
            idx = int(ev._or())
            actor = self.self_actor
            if ev._peek() == ",":
                ev._next(); actor = int(ev._or())
            self.host.set_mailbox(actor, idx, self.evalf(rhs))
        elif lhs.startswith("$"):
            r = rhs
            if r.startswith('"') and r.endswith('"'):
                self.strv[lhs] = r[1:-1]
            else:
                self.strv[lhs] = fmt(self.evalf(r))
        else:
            self.num[lhs] = self.evalf(rhs)

    def _do_M(self, st):
        op = st.operand.strip()
        toks = tokenize(op)
        if any(t[1] in _RELOPS for t in toks):
            self.match = self.evalf(op) != 0
        else:
            items = [x.strip() for x in op.split(",")]
            self.match = self.accept.strip() in items

    def _label(self, operand: str) -> int:
        name = operand.strip().lstrip("*")
        if name not in self.prog.labels:
            raise PilotError(f"unknown label *{name}")
        return self.prog.labels[name]

    def _do_J(self, st):  self.pc = self._label(st.operand)
    def _do_U(self, st):  self.callstack.append(self.pc); self.pc = self._label(st.operand)

    def _do_E(self, st):
        if self.callstack:
            self.pc = self.callstack.pop()
        else:
            self.exit_code = 0

    def _do_EX(self, st):
        self.exit_code = int(self.evalf(st.operand)) if st.operand.strip() else 0

    def _do_PA(self, st): self.host.wait_seconds(self.evalf(st.operand))

    def _do_A(self, st):
        # Accept = await the engine: bind the awaited value into #last + a var.
        var = st.operand.strip()
        state, value = self.host.await_mailbox(self.self_actor, 0, ">=", 0, 5.0)
        self.num["#last"] = value
        self.accept = fmt(value)
        if var:
            self.bind(var, value)

    # ── WF engine-control extension verbs ──
    def _args(self, operand: str) -> list[str]:
        return operand.split()

    def _do_PS(self, st): self.host.pause()
    def _do_PR(self, st): self.host.resume()
    def _do_ST(self, st): self.host.step(int(self.evalf(st.operand)) if st.operand.strip() else 1)

    def _do_IN(self, st):
        a = self._args(st.operand)
        slot = a[0]
        bits = int(self.evalf(a[1]))
        held = 0
        if "held" in a:
            held = int(self.evalf(a[a.index("held") + 1]))
        self.host.inject(slot, bits, held)

    def _do_WM(self, st):
        a = self._args(st.operand)
        actor = int(self.evalf(a[0]))
        mbx = int(self.evalf(a[1]))
        relop = a[2]
        val = self.evalf(a[3])
        timeout = 5.0
        if "timeout" in a:
            timeout = self.evalf(a[a.index("timeout") + 1])
        state, value = self.host.await_mailbox(actor, mbx, relop, val, timeout)
        self.num["#last"] = value
        self.accept = fmt(value)

    def _do_WB(self, st):
        a = self._args(st.operand)
        timeout = self.evalf(a[a.index("timeout") + 1]) if "timeout" in a else 5.0
        self.match = self.host.await_broadcast(a[0], timeout)

    def _do_WT(self, st): self.host.wait_seconds(self.evalf(st.operand))

    def _do_WA(self, st):
        a = self._args(st.operand)
        off = len(a) > 2 and a[2] == "off"
        self.host.watch(int(self.evalf(a[0])), int(self.evalf(a[1])), off)

    def _do_SP(self, st):
        a = self._args(st.operand)
        self.host.set_transform(int(self.evalf(a[0])),
                                self.evalf(a[1]), self.evalf(a[2]), self.evalf(a[3]))

    def _do_SF(self, st):
        a = self._args(st.operand)
        self.host.set_prop(int(self.evalf(a[0])), a[1], self.evalf(a[2]))

    def _do_SM(self, st):
        a = self._args(st.operand)
        self.host.set_mailbox(int(self.evalf(a[0])), int(self.evalf(a[1])), self.evalf(a[2]))

    def _do_SH(self, st):
        ok = self.host.screenshot(st.operand.strip())
        if not ok:
            sys.stderr.write(f"[pilot] screenshot {st.operand.strip()} failed\n")

    def _do_UD(self, st): self.host.undo()
    def _do_RV(self, st): self.host.revert()


# ─────────────────────────────────────────────────────────────────────────────
# Scenario runner + directive checking.

def tier_of(path: Path) -> str:
    for key, val in parse(Path(path).read_text()).directives:
        if key == "tier":
            return val.strip()
    return "vm"


def _check(prog: Program, code: int, output: str, screenshots: list[str]) -> list[str]:
    fails: list[str] = []
    for key, val in prog.directives:
        val = val.strip()
        if key == "expect-exit":
            if code != int(val):
                fails.append(f"expect-exit {val}, got {code}")
        elif key == "expect-out":
            if val not in output:
                fails.append(f"expect-out {val!r} not in output")
        elif key == "expect-no-out":
            if val in output:
                fails.append(f"expect-no-out {val!r} present in output")
        elif key == "screenshot":
            if val not in screenshots:
                fails.append(f"screenshot {val!r} not produced")
    return fails


def run_vm_scenario(path: Path) -> tuple[bool, list[str], int, str]:
    prog = parse(Path(path).read_text())
    host = MockHost()
    vm = PilotVM(prog, host, self_actor=0)
    code = vm.run()
    fails = _check(prog, code, host.output, host.screenshots)
    return (not fails, fails, code, host.output)


# ── engine launch helpers (mirror tests/verify_smb_fireball.py) ──
WF_GAME = REPO / "engine" / "wf_game"
LIB_DIR = REPO / "engine" / "libs"
GAME_CWD = REPO / "wfsource" / "source" / "game"
_MESH_RE = re.compile(r"actor idx=(\d+) mesh=([^\s]+)")


def _discover(logpath: Path, want: set[str], timeout: float = 8.0) -> dict[str, int]:
    deadline = time.time() + timeout
    found: dict[str, int] = {}
    while time.time() < deadline and not want.issubset(found):
        try:
            for m in _MESH_RE.finditer(logpath.read_text(errors="replace")):
                base = m.group(2).removesuffix(".iff")
                if base in want:
                    found[base] = int(m.group(1))
        except OSError:
            pass
        if want.issubset(found):
            break
        time.sleep(0.15)
    return found


def run_engine_scenario(path: Path, port: int = 7795) -> Optional[tuple[bool, list[str], int, str]]:
    """Self-launch wf_game per @level, drive over the bridge. None => skip."""
    sys.path.insert(0, str(REPO / "tests"))           # for debug_bridge_client
    from debug_bridge_client import BridgeClient

    prog = parse(Path(path).read_text())
    d = dict(prog.directives)
    level_name = d.get("level", "").strip()
    if not WF_GAME.exists() or not os.environ.get("DISPLAY"):
        return None
    level = REPO / "wflevels" / level_name
    if not level.exists():
        return None

    # @needs ACTOR as #VAR
    needs: list[tuple[str, str]] = []
    for key, val in prog.directives:
        if key == "needs":
            m = re.match(r"(\S+)\s+as\s+(#\w+)", val.strip())
            if m:
                needs.append((m.group(1), m.group(2)))

    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = f"{LIB_DIR}:{env.get('LD_LIBRARY_PATH', '')}"
    log = Path(__file__).resolve().parent / f".{Path(path).stem}.log"
    log_fp = open(log, "w")
    proc = subprocess.Popen(
        [str(WF_GAME), f"-L{level}", "--debug-port", str(port),
         "--debug-bind", "127.0.0.1", "--debug-print-actors"],
        cwd=str(GAME_CWD), env=env, stdout=log_fp, stderr=subprocess.STDOUT)

    cli = host = None
    try:
        want = {a for a, _ in needs}
        found = _discover(log, want) if want else {}
        if not want.issubset(found):
            return (False, [f"actors not discovered: {want - set(found)}"], 1, "")
        cli = BridgeClient("127.0.0.1", port, timeout=15.0)
        time.sleep(0.5)
        host = BridgeHost(cli)
        vm = PilotVM(prog, host, self_actor=found.get("player", 0))
        for actor_name, var in needs:
            vm.bind(var, found[actor_name])
        code = vm.run()
        fails = _check(prog, code, host.output, host.screenshots)
        return (not fails, fails, code, host.output)
    finally:
        if host is not None:
            host.teardown()
        if cli is not None:
            try: cli.close()
            except Exception: pass
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try: proc.wait(timeout=3.0)
            except Exception: proc.kill()
        log_fp.close()


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: pilot_driver.py FILE.pilot", file=sys.stderr)
        return 2
    path = Path(argv[1])
    tier = tier_of(path)
    if tier == "engine":
        res = run_engine_scenario(path)
        if res is None:
            print(f"SKIP {path.name}: engine prereqs missing (wf_game/level/DISPLAY)")
            return 0
        ok, fails, code, out = res
    else:
        ok, fails, code, out = run_vm_scenario(path)
    print(f"{'PASS' if ok else 'FAIL'} {path.name} (exit {code}, tier {tier})")
    for f in fails:
        print(f"   - {f}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
