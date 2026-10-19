#!/usr/bin/env python3
"""Verify SMB Fire Flower + Star power-ups.

Companion to docs/plans/2026-05-26-smb-fire-flower-and-star.md.

Engine constraints that shape this test (same lessons as verify_smb_brick_break.py):
  * COLLIDER_IDX / COLLISION_NORMAL_Z (3044/3047) are cleared at the TOP of every
    frame, so an *injected* contact is wiped before any script reads it. The Star
    bounce therefore can't be faked by injection — it needs a REAL Jolt floor
    contact, so that check spawns a star and RESUMES real-time physics, sampling
    Z_POS for the bounce sawtooth.
  * The power-up state machine, by contrast, is driven by persistent global
    mailboxes (SMB_*_PICKUP, SMB_MARIO_STATE, SMB_*_UNTIL) that survive the frame —
    so those checks inject the signal directly and step (dt-independent).
  * Global user mailboxes (idx < 1900) read back at idx=1; per-actor mailboxes
    (>= 3000: scales, ALIVE, positions) read at the actor's own index.

Checks:
  1. Fire from Small:  pickup -> state 2 + super scale (1.25/1.25/1.9).
  2. Fire from Super:  pickup -> state 2 (super stays big).
  3. Fire power-down keeps size:  state 2 -> 1 stays 1.9; 1 -> 0 shrinks to 1.0.
  4. Star window:  pickup sets SMB_STAR_UNTIL + SMB_INVULN_UNTIL in the future.
  5. Star defeat-on-touch:  with the window held open, a touched Goomba dies and
     does NOT hurt the player.
  6. Star expiry:  with the window in the past, a touched Koopa survives and hurts.
  7. Star bounce:  a spawned star's Z_POS oscillates (falls, then rises again).
Screenshots: fire mario / mid power-down / star flicker beside a vanished enemy / bounce.
"""
from __future__ import annotations

import os, re, sys, time, subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from debug_bridge_client import BridgeClient  # noqa: E402

REPO  = Path(__file__).resolve().parent.parent
WF    = REPO / "engine" / "wf_game"
LEVEL = REPO / "wflevels" / "smb_w1_1-standalone.iff"
LIB   = REPO / "engine" / "libs"
CWD   = REPO / "wfsource" / "source" / "game"
SCROT = REPO / "tests" / "screenshots"
LOG   = REPO / "tests" / ".verify_smb_fire_star.log"
PORT  = 7787

# globals (idx < 1900 -> read at idx=1)
SMB_PLAYER_X, SMB_MAX_CAM_X, SMB_PLAYER_Z = 1800, 1802, 1803
SMB_PLAYER_HURT, SMB_INVULN_UNTIL         = 1804, 1805
SMB_MARIO_STATE                           = 1814
SMB_FIREFLOWER_PICKUP, SMB_STAR_PICKUP    = 1816, 1817
SMB_STAR_UNTIL                            = 1818
# per-actor (read at the actor's own idx)
ALIVE, X_POS, Z_POS, XSPEED, ZSPEED       = 3004, 3009, 3011, 3018, 3020
X_SCALE, Y_SCALE, Z_SCALE                 = 3040, 3041, 3042
SMB_QBLOCK_ACTIVATE                       = 2010

FAR_FUTURE = 999999.0
PAST       = 0.001
_MESH_RE = re.compile(r"actor idx=(\d+) mesh=([^\s]+)")


def discover(log_path: Path, want: set[str], timeout=8.0) -> dict[str, int]:
    deadline = time.time() + timeout
    found: dict[str, int] = {}
    while time.time() < deadline and not want.issubset(found):
        try:
            for m in _MESH_RE.finditer(log_path.read_text(errors="replace")):
                base = m.group(2).removesuffix(".iff")
                if base in want:
                    found[base] = int(m.group(1))
        except OSError:
            pass
        if want.issubset(found):
            break
        time.sleep(0.15)
    return found


def main() -> int:
    SCROT.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH','')}"
    env.setdefault("DISPLAY", ":0")
    log_fp = open(LOG, "w")
    proc = subprocess.Popen(
        [str(WF), f"-L{LEVEL}", "--debug-port", str(PORT),
         "--debug-bind", "127.0.0.1", "--debug-print-actors"],
        cwd=str(CWD), env=env, stdout=log_fp, stderr=subprocess.STDOUT)

    cli = None
    fails: list[str] = []

    def check(cond, msg):
        print(f"  [{'PASS' if cond else 'FAIL'}] {msg}")
        if not cond:
            fails.append(msg)

    def g(idx, mb):
        with cli._lock:
            return cli.mailbox_values.get((idx, mb))

    def step(n=1, dt=0.04):
        for _ in range(n):
            cli.send({"op": "step"})
            time.sleep(dt)

    def setg(mb, value):
        """Write a global; idx is irrelevant for the global slot."""
        cli.set_mailbox(idx=PLAYER, mailbox=mb, value=value)

    def poll(idx, mb, pred, secs=3.0):
        end = time.time() + secs
        while time.time() < end:
            step(1, dt=0.03)
            v = g(idx, mb)
            if v is not None and pred(v):
                return v
        return g(idx, mb)

    def despawned(idx) -> bool:
        """A live set_mailbox on a despawned actor returns 'not found'."""
        cli.send({"op": "set_mailbox", "idx": idx, "mailbox": ALIVE, "value": 1})
        err = cli.wait_for(
            lambda m: m.get("op") == "error" and "not found" in str(m.get("msg", "")),
            timeout=1.0)
        return err is not None

    def shot(label):
        out = SCROT / f"smb_firestar_{label}.png"
        cli.send({"op": "screenshot", "filename": str(out)})
        m = cli.wait_for(lambda m: m.get("op") in ("screenshot_done", "error"), timeout=6.0)
        ok = m and m.get("op") == "screenshot_done"
        print(f"  screenshot {label}: {'OK -> ' + out.name if ok else 'WARN ' + str(m)}")

    try:
        names = {"player", "star_block", "goomba_00.001", "koopa_00.001"}
        idx = discover(LOG, names)
        print("discovered indices:", idx)
        if "player" not in idx or "star_block" not in idx:
            print("FATAL: missing core actors; aborting"); return 1
        global PLAYER
        PLAYER  = idx["player"]
        STARBLK = idx["star_block"]
        GOOMBA  = idx.get("goomba_00.001")
        KOOPA   = idx.get("koopa_00.001")

        cli = BridgeClient("127.0.0.1", PORT, timeout=15.0)
        print("bridge: connected"); time.sleep(1.0)
        cli.watch(idx=1, mailbox=SMB_MARIO_STATE)
        cli.watch(idx=1, mailbox=SMB_STAR_UNTIL)
        cli.watch(idx=PLAYER, mailbox=Z_SCALE)
        cli.watch(idx=PLAYER, mailbox=X_SCALE)

        cli.send({"op": "pause"}); time.sleep(0.2)
        step(5)

        # ── 1. Fire from Small ───────────────────────────────────────────────────
        setg(SMB_MARIO_STATE, 0)
        setg(SMB_FIREFLOWER_PICKUP, 1)
        st = poll(1, SMB_MARIO_STATE, lambda v: v == 2.0, secs=2.0)
        zs = g(PLAYER, Z_SCALE); xs = g(PLAYER, X_SCALE)
        print(f"  fire-from-small: state={st} X_SCALE={xs} Z_SCALE={zs}")
        check(st == 2.0, f"Small + flower -> Fire (state 2), got {st}")
        check(zs is not None and abs(zs - 1.9) < 0.1, f"Fire is super-tall (Z_SCALE 1.9), got {zs}")
        shot("01_fire_mario")

        # ── 2. Fire from Super ───────────────────────────────────────────────────
        setg(SMB_MARIO_STATE, 1)
        setg(SMB_FIREFLOWER_PICKUP, 1)
        st = poll(1, SMB_MARIO_STATE, lambda v: v == 2.0, secs=2.0)
        check(st == 2.0, f"Super + flower -> Fire (state 2), got {st}")

        # ── 3. Fire power-down keeps size ────────────────────────────────────────
        setg(SMB_MARIO_STATE, 2)
        setg(SMB_INVULN_UNTIL, PAST)      # un-gate the hurt
        setg(SMB_PLAYER_HURT, 1)
        st = poll(1, SMB_MARIO_STATE, lambda v: v == 1.0, secs=2.0)
        zs = g(PLAYER, Z_SCALE)
        print(f"  fire->super on hit: state={st} Z_SCALE={zs}")
        check(st == 1.0, f"Fire hit -> Super (state 1), got {st}")
        check(zs is not None and abs(zs - 1.9) < 0.1, f"Fire->Super STAYS big (Z_SCALE 1.9), got {zs}")
        shot("02_powered_down_to_super")
        setg(SMB_INVULN_UNTIL, PAST)      # un-gate again (power-down set its own i-frames)
        setg(SMB_PLAYER_HURT, 1)
        st = poll(1, SMB_MARIO_STATE, lambda v: v == 0.0, secs=2.0)
        zs = g(PLAYER, Z_SCALE)
        print(f"  super->small on hit: state={st} Z_SCALE={zs}")
        check(st == 0.0, f"Super hit -> Small (state 0), got {st}")
        check(zs is not None and abs(zs - 1.0) < 0.1, f"Super->Small shrinks (Z_SCALE 1.0), got {zs}")

        # ── 4. Star window ───────────────────────────────────────────────────────
        setg(SMB_MARIO_STATE, 0)
        setg(SMB_STAR_UNTIL, 0)
        setg(SMB_INVULN_UNTIL, 0)
        setg(SMB_STAR_PICKUP, 1)
        until = poll(1, SMB_STAR_UNTIL, lambda v: v > 1.0, secs=2.0)
        print(f"  star pickup: SMB_STAR_UNTIL={until}")
        check(until is not None and until > 1.0, f"Star pickup opens invincibility window (got {until})")
        st = g(1, SMB_MARIO_STATE)
        check(st == 0.0, f"Star does NOT change size (state still 0), got {st}")

        # The player script rebroadcasts SMB_PLAYER_X/Z from its own X/Z_POS every
        # tick, so we move the PLAYER to the enemy (teleport X/Z_POS) rather than
        # poking SMB_PLAYER_X (which the player would immediately overwrite).
        cli.watch(idx=PLAYER, mailbox=X_POS)

        # ── 5. Star defeat-on-touch (Goomba) ─────────────────────────────────────
        if GOOMBA is not None:
            cli.watch(idx=GOOMBA, mailbox=X_POS)
            cli.watch(idx=1, mailbox=SMB_PLAYER_HURT)
            step(2)
            gx = g(GOOMBA, X_POS) or 43.5
            setg(SMB_STAR_UNTIL, FAR_FUTURE)            # hold the window open
            setg(SMB_MAX_CAM_X, gx + 5.0)              # reveal the enemy
            setg(SMB_PLAYER_HURT, 0)
            cli.set_mailbox(idx=PLAYER, mailbox=X_POS, value=gx)         # walk Mario into it
            cli.set_mailbox(idx=PLAYER, mailbox=Z_POS, value=g(GOOMBA, Z_POS) or 0.75)
            step(8, dt=0.03)
            hurt = g(1, SMB_PLAYER_HURT)
            gone = despawned(GOOMBA)
            print(f"  star touch goomba (gx={gx}): despawned={gone} SMB_PLAYER_HURT={hurt}")
            check(gone, "Star: touched Goomba is defeated (despawns)")
            check(hurt in (0.0, None), f"Star: touch does NOT hurt the player (HURT={hurt})")
            shot("03_star_enemy_defeated")
        else:
            check(False, "Goomba not discovered (defeat-on-touch skipped)")

        # ── 6. Star expiry -> normal hurt resumes (Koopa) ────────────────────────
        # With the window closed, a side-hit must power Mario down (Super 1 -> 0),
        # proving the enemy hurts again. We assert the EFFECT (state drop) rather
        # than read SMB_PLAYER_HURT, which the player consumes (clears) each tick.
        if KOOPA is not None:
            cli.watch(idx=KOOPA, mailbox=X_POS)
            cli.watch(idx=KOOPA, mailbox=Z_POS)
            cli.watch(idx=KOOPA, mailbox=ALIVE)
            step(2)
            setg(SMB_STAR_UNTIL, PAST)                  # window closed
            setg(SMB_INVULN_UNTIL, PAST)                # and not in i-frames
            setg(SMB_MARIO_STATE, 1)                    # Super, so a hit powers down (no respawn)
            kx0 = g(KOOPA, X_POS) or 48.0
            setg(SMB_MAX_CAM_X, kx0 + 5.0)              # reveal the koopa
            # Pin Mario onto the koopa at ITS OWN Z each tick (dz=0 -> side hit, NOT a
            # stomp — a stomp would kill the koopa for reasons unrelated to the Star)
            # and track its walk so dx stays small. Stop when Mario powers down.
            st = None
            for _ in range(40):
                kxi, kzi = g(KOOPA, X_POS), g(KOOPA, Z_POS)
                if kxi is not None: cli.set_mailbox(idx=PLAYER, mailbox=X_POS, value=kxi)
                if kzi is not None: cli.set_mailbox(idx=PLAYER, mailbox=Z_POS, value=kzi)
                step(1, dt=0.03)
                st = g(1, SMB_MARIO_STATE)
                if st == 0.0:
                    break
            koopa_gone = despawned(KOOPA)
            print(f"  expired touch koopa (kx={kx0}): state={st} koopa_gone={koopa_gone}")
            check(not koopa_gone, "Expiry: touched Koopa survives (not defeated by touch)")
            check(st == 0.0, f"Expiry: enemy hurts the player again (Super->Small, state={st})")
        else:
            check(False, "Koopa not discovered (expiry check skipped)")

        # ── 7. Star bounce + wall-reversal (real physics) ────────────────────────
        # Spawn a star and let real-time physics run; the bounce + reversal both need
        # genuine contacts (injected contacts are wiped per-frame). The star pops from
        # the block @X=57 moving right, bounces along ground_2 to the flagpole @63,
        # then reverses. We track Z (bounce), X (reached the flagpole), and XSPEED — a
        # sign flip (+ -> -) is the direct proof of reversal regardless of distance.
        band = list(range(51, 56))
        for i in band:
            cli.watch(idx=i, mailbox=Z_POS)
            cli.watch(idx=i, mailbox=X_POS)
            cli.watch(idx=i, mailbox=XSPEED)
        cli.set_mailbox(idx=STARBLK, mailbox=SMB_QBLOCK_ACTIVATE, value=1)
        cli.send({"op": "resume"})
        zsamp: dict[int, list[float]] = {i: [] for i in band}
        xsamp: dict[int, list[float]] = {i: [] for i in band}
        vsamp: dict[int, list[float]] = {i: [] for i in band}
        # Poll until a reversal is observed (XSPEED of some mover goes + -> -), rather
        # than a fixed wall-clock window: headless engine speed varies, so we drive on
        # simulated progress. Generous cap in case it never reverses. (XSPEED holds its
        # value between contacts, so once it flips negative the cached read stays < 0.)
        t_cap = time.time() + 16.0
        while time.time() < t_cap:
            for i in band:
                z = g(i, Z_POS); x = g(i, X_POS); v = g(i, XSPEED)
                if z is not None: zsamp[i].append(z)
                if x is not None: xsamp[i].append(x)
                if v is not None: vsamp[i].append(v)
            if any(vsamp[i] and max(vsamp[i]) > 0.5 and min(vsamp[i]) < -0.3 for i in band):
                break   # a mover went right then reversed left — reversal captured
            time.sleep(0.05)
        cli.send({"op": "pause"})
        # the spawned star = the index whose Z moved the most
        mover, span = None, 0.0
        for i, zs in zsamp.items():
            if len(zs) >= 4:
                s = max(zs) - min(zs)
                if s > span:
                    mover, span = i, s

        bounced = False
        if mover is not None:
            seq = zsamp[mover]
            lo = min(seq); lo_i = seq.index(lo)
            after = seq[lo_i + 1:]
            bounced = bool(after) and (max(after) > lo + 0.3)   # Z rose again after a low
            print(f"  bounce: star idx={mover} Zspan={span:.2f} min={lo:.2f} rose_after={bool(after) and max(after):.2f}")
        check(bounced, f"Star bounces (Z falls then rises; idx={mover}, span={span:.2f})")
        shot("04_star_bounce")

        # Wall-reversal: XSPEED starts positive (moving right) and goes negative after
        # the flagpole contact. The sign flip is the reversal; X reaching ~62 confirms
        # it actually hit the pole (rather than reversing off something spurious).
        reversed_x = False
        if mover is not None and len(vsamp[mover]) >= 4:
            vs = vsamp[mover]; xs3 = xsamp[mover]
            maxv, minv = max(vs), min(vs)
            maxx = max(xs3) if xs3 else 0.0
            reversed_x = maxv > 0.5 and minv < -0.3 and maxx >= 60.0   # sign flip = reversal
            print(f"  reversal: star XSPEED max={maxv:.2f} min={minv:.2f}  maxX={maxx:.1f}")
        check(reversed_x, f"Star reverses X off the flagpole (XSPEED flips + -> -; idx={mover})")

    finally:
        if cli:
            try: cli.close()
            except Exception: pass
        if proc.poll() is None:
            proc.terminate()
            try: proc.wait(timeout=3)
            except Exception: proc.kill()
        log_fp.close()

    print()
    if fails:
        print(f"FAIL — {len(fails)} check(s) failed:")
        for f in fails:
            print(f"   - {f}")
        return 1
    print("PASS — Fire Flower power-up + Star invincibility/defeat/bounce all verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
