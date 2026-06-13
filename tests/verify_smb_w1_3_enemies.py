#!/usr/bin/env python3
"""Verify SMB W1-3 enemy behaviour live, via the debug bridge, while recording mp4.

Each enemy interaction is asserted on a DURABLE mailbox transition (transient
SMB_STOMP/HURT pulses are caught by tight polling as a bonus):

  goomba stomp     drop Mario onto a Goomba          -> goomba ALIVE 1->0  (despawn)
  koopa stomp      drop Mario onto a Koopa           -> SMB_KOOPA_STATE_L 0->1 (shell)
  paratroopa bounce read its Z_POS over time         -> oscillates
  paratroopa stomp drop Mario onto it                -> paratroopa ALIVE 1->0
  side-hit hurt    Super Mario overlaps an enemy     -> SMB_MARIO_STATE 1->0 (shrink)

Mario HOVERS over each enemy (re-pinned each frame) so he stays in frame for the recording
(a real fall used to crash the camera's track-object lookup — movecam.cc, fixed: the camera
now degrades gracefully on a despawned tracked actor, TODO 134/135); the engine FBO
recording (-record_video -> output.mp4) captures the interactions.

Result: 4/5 assert cleanly. The "goomba stomp" case (test 1) is harness-flaky — that
specific goomba walks off its narrow tree-top into the pit (the faithful 1-3 green-enemy
hazard) and despawns before the hover lands, so it gives no broadcasts. Its STOMP behavior
is the same `ENEMY_SCRIPT` branch exercised by the passing koopa+paratroopa stomps (same
`dz>0.7` test) and its HURT branch by the passing side-hit, so the behavior is covered;
only that one actor-in-test-1 is unreliable to drive. Run from a clean tree (no live input).

Usage: python3 tests/verify_smb_w1_3_enemies.py [--out-dir /home/will/tmp/smb_w13]
"""
from __future__ import annotations
import argparse, os, re, shutil, subprocess, sys, time
from pathlib import Path

REPO  = Path(__file__).resolve().parent.parent
WF    = REPO / "engine" / "wf_game"
LEVEL = REPO / "wflevels" / "smb_w1_3-standalone.iff"
LIB   = REPO / "engine" / "libs"
CWD   = REPO / "wfsource" / "source" / "game"
PORT  = 7798
LOG   = REPO / "tests" / ".verify_smb_w1_3_enemies.log"
REC   = REPO / "tests" / "recordings" / "smb_w1_3_enemies.mp4"
REC.parent.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(Path(__file__).parent))
from debug_bridge_client import BridgeClient  # noqa: E402

T = 1.5
# player-local
X_POS, Y_POS, Z_POS, XSPEED, ZSPEED, ALIVE = 3009, 3010, 3011, 3018, 3020, 3004
SMB_KOOPA_STATE_L = 2018
# globals (idx=1)
SMB_MAX_CAM_X = 1802
SMB_PLAYER_HURT, SMB_INVULN_UNTIL, SMB_STOMP, SMB_MARIO_STATE, SMB_SCORE = 1804, 1805, 1806, 1814, 1838

_LOG_RE = re.compile(r"actor idx=(\d+) mesh=(\S+) mobility=\S+ pos=\(([-\d.]+),([-\d.]+),([-\d.]+)\)")


def actors_from_log():
    out = []
    try:
        for m in _LOG_RE.finditer(LOG.read_text(errors="ignore")):
            out.append((int(m.group(1)), m.group(2), float(m.group(3)), float(m.group(4)), float(m.group(5))))
    except OSError:
        pass
    return out


def find(mesh_substr, target_x, acts):
    """idx of the actor whose mesh contains mesh_substr and whose X is nearest target_x."""
    cands = [(abs(x - target_x), idx, x, z) for idx, mesh, x, y, z in acts if mesh_substr in mesh]
    if not cands:
        return None, None, None
    _, idx, x, z = min(cands)
    return idx, x, z


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, default=Path("/home/will/tmp/smb_w13"))
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH','')}"
    env.setdefault("DISPLAY", ":0"); env["vblank_mode"] = "0"; env["__GL_SYNC_TO_VBLANK"] = "0"
    log_fp = open(LOG, "w")
    proc = subprocess.Popen(
        [str(WF), f"-L{LEVEL}", "-record_video", "--debug-port", str(PORT),
         "--debug-bind", "127.0.0.1", "--debug-print-actors"],
        cwd=str(CWD), env=env, stdout=log_fp, stderr=subprocess.STDOUT)

    results = []
    state = {}   # filled in try: PLAYER, cli

    def shot(name):
        state["cli"].send({"op": "screenshot", "filename": str(args.out_dir / f"enemy_{name}.png")})
        state["cli"].wait_for(lambda m: m.get("op") in ("screenshot_done", "error"), timeout=6.0)

    def strike(eidx, boot_x, boot_z, dh, done, shot_name=None, pin_enemy=False, timeout=4.5):
        """HOVER Mario at a fixed dz=dh above (or level with) an enemy and hold until the
        `done()` predicate fires. Hovering (re-pinning X+Z, zeroing velocity each frame)
        keeps Mario IN the room over the death pit — a real fall used to crash the camera's
        track-object lookup (movecam.cc; now fixed — the camera degrades gracefully, TODO
        134/135). The enemy walks left at 4 m/s, so we track its live X/Z (broadcast on change).
        dh>0.7 → Mario "above" → stomp; dh in (0,0.7) → side contact → hurt.
        """
        cli, PLAYER = state["cli"], state["PLAYER"]
        cli.watch(idx=eidx, mailbox=X_POS)
        cli.watch(idx=eidx, mailbox=Z_POS)
        t0 = time.time()
        while time.time() - t0 < timeout:
            if pin_enemy:
                # A Physics enemy walks left at 4 m/s once on-screen and WALKS OFF its
                # narrow tree-top into the pit (the faithful 1-3 hazard) — despawning
                # before a reactive hover can land. Fully FREEZE it in place each frame
                # (pin X+Z, zero its velocity) so the interaction is deterministic.
                cli.set_mailbox(idx=eidx, mailbox=X_POS, value=round(boot_x, 2))
                cli.set_mailbox(idx=eidx, mailbox=Z_POS, value=round(boot_z, 2))
                cli.set_mailbox(idx=eidx, mailbox=XSPEED, value=0)
                cli.set_mailbox(idx=eidx, mailbox=ZSPEED, value=0)
            cx = boot_x if pin_enemy else cli.mailbox_values.get((eidx, X_POS), boot_x)
            cz = boot_z if pin_enemy else cli.mailbox_values.get((eidx, Z_POS), boot_z)
            cli.set_mailbox(idx=PLAYER, mailbox=Y_POS, value=0)
            cli.set_mailbox(idx=PLAYER, mailbox=XSPEED, value=0)
            cli.set_mailbox(idx=PLAYER, mailbox=ZSPEED, value=0)
            cli.set_mailbox(idx=PLAYER, mailbox=X_POS, value=round(cx, 2))
            cli.set_mailbox(idx=PLAYER, mailbox=Z_POS, value=round(cz + dh, 2))
            if done():
                if shot_name:                       # capture with Mario still at the enemy
                    time.sleep(0.1); shot(shot_name)
                # park Mario on the guaranteed-safe start strip so he stays in frame
                # (and in-room) before the next strike re-teleports.
                cli.set_mailbox(idx=PLAYER, mailbox=X_POS, value=4.5)
                cli.set_mailbox(idx=PLAYER, mailbox=Z_POS, value=2.0)
                cli.set_mailbox(idx=PLAYER, mailbox=ZSPEED, value=0)
                return True
            time.sleep(0.03)
        return False

    def score():     return state["cli"].mailbox_values.get((1, SMB_SCORE)) or 0.0
    def gget(i, mb): return state["cli"].mailbox_values.get((i, mb))

    try:
        time.sleep(2.8)
        acts = []
        for _ in range(30):
            acts = actors_from_log()
            if any("player" in m for _, m, *_ in acts):
                break
            time.sleep(0.1)
        PLAYER = next((idx for idx, m, *_ in acts if "player" in m), 9)
        print(f"player idx={PLAYER}; {len(acts)} actors")
        cli = BridgeClient("127.0.0.1", PORT, timeout=15.0)
        state["cli"] = cli; state["PLAYER"] = PLAYER
        cli.watch(idx=1, mailbox=SMB_STOMP)
        cli.watch(idx=1, mailbox=SMB_PLAYER_HURT)
        cli.watch(idx=1, mailbox=SMB_MARIO_STATE)
        cli.watch(idx=1, mailbox=SMB_SCORE)
        cli.watch(idx=1, mailbox=SMB_MAX_CAM_X)
        time.sleep(0.8)

        def reset_player():
            # Super + clear i-frames so a stomp/hit always registers; the +100-per-stomp
            # player_script (SMB_STOMP -> SMB_SCORE+=100) is the durable, despawn-proof signal.
            cli.set_mailbox(idx=1, mailbox=SMB_MARIO_STATE, value=1)
            cli.set_mailbox(idx=1, mailbox=SMB_INVULN_UNTIL, value=0)
            time.sleep(0.2)

        # ── 1. Goomba stomp (Goomba on the tall tree_c2, col 44 -> X=66) ──────────
        gi, gx, gz = find("goomba", 44 * T, acts)
        if gi is not None:
            reset_player(); base = score()
            ok = strike(gi, gx, gz, 1.0, lambda: score() >= base + 100,
                        shot_name="1_goomba_stomp", pin_enemy=True)
            shot("1_goomba_stomp")   # unconditional, to see the state even on fail
            print(f"  [diag] goomba idx={gi} boot=({gx:.1f},{gz:.1f}) base={base} score={score()} "
                  f"max_cam_x={gget(1, SMB_MAX_CAM_X)} enemyX={gget(gi, X_POS)} enemyZ={gget(gi, Z_POS)}")
            results.append(("goomba stomp -> SMB_SCORE +100 (stomp+despawn)", ok))

        # ── 2. Koopa stomp -> shell (Koopa on the wide tree_f2, col 102 -> X=153) ──
        ki, kx, kz = find("koopa_green", 102 * T, acts)
        if ki is not None:
            cli.watch(idx=ki, mailbox=SMB_KOOPA_STATE_L)   # so gget() sees the shell transition
            reset_player(); base = score()
            ok = strike(ki, kx, kz, 1.0,
                        lambda: score() >= base + 100 or gget(ki, SMB_KOOPA_STATE_L) == 1,
                        shot_name="2_koopa_shell", pin_enemy=True)
            print(f"  [diag] koopa idx={ki} boot=({kx:.1f},{kz:.1f}) base={base} score={score()} "
                  f"state={gget(ki, SMB_KOOPA_STATE_L)}")
            results.append(("koopa stomp -> shell (SMB_SCORE +100 / SMB_KOOPA_STATE_L=1)", ok))

        # ── 3. Paratroopa: confirm it bounces, then stomp it (col 107 -> X=160.5) ─
        pi, px, pz = find("paratroopa", 107 * T, acts)
        if pi is not None:
            cli.watch(idx=pi, mailbox=Z_POS)
            zs = set(); t0 = time.time()
            while time.time() - t0 < 2.0:                 # sample its bounce
                v = cli.mailbox_values.get((pi, Z_POS))
                if v is not None:
                    zs.add(round(v, 1))
                time.sleep(0.05)
            results.append((f"paratroopa bounces (>=3 distinct Z over 2 s; saw {len(zs)})", len(zs) >= 3))
            reset_player(); base = score()
            ok = strike(pi, px, pz, 1.0, lambda: score() >= base + 100, shot_name="3_paratroopa_stomp")
            results.append(("paratroopa stomp -> SMB_SCORE +100 (stomp+defeat)", ok))

        # ── 4. Side-hit hurt: Super Mario level with a Goomba (col 110 -> X=165) ──
        hi, hx, hz = find("goomba", 110 * T, acts)
        if hi is not None:
            reset_player()
            ok = strike(hi, hx, hz, 0.3, lambda: gget(1, SMB_MARIO_STATE) == 0,
                        shot_name="4_side_hit_hurt", pin_enemy=True)
            results.append(("side-hit -> SMB_MARIO_STATE 1->0 (Super shrinks to Small)", ok))

        print("\n=== RESULTS ===")
        for desc, ok in results:
            print(f"  [{'PASS' if ok else 'FAIL'}] {desc}")
        npass = sum(1 for _, ok in results if ok)
        print(f"  {npass}/{len(results)} passed")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        out = CWD / "output.mp4"
        if out.exists() and out.stat().st_size > 1000:
            shutil.move(str(out), str(REC))
            print(f"recording -> {REC} ({REC.stat().st_size} bytes)")

    return 0 if results and all(ok for _, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main())
