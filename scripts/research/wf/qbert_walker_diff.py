#!/usr/bin/env python3
"""Pixel-diff WF walker captures against the MAME walker captures.

Compares the cube-top color signature for each round, state-0 and state-1.
MAME side reads at the documented hardcoded sample coords; WF side reads
at hand-tuned pixel coords (auto-projection from world coords was fighting
WF's BungeeCameraHandler framing). Pass = max-channel diff < THRESHOLD.

This tool's purpose is to surface authoring gaps between the WF port and
the MAME ROM-grounded captures: per-round palette swaps, per-state cube
colour authoring, etc. A universal FAIL is informative — it tells you
which (round, state) cells need work in `gen_cube.py`.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[3]

# MAME framebuffer sample coordinates — see scripts/research/mame/sample_cube_colors.py
MAME_APEX   = (120, 56)        # apex cube (0,0) top
MAME_CUBE11 = (137, 80)        # down-right cube (1,1) top — flipped after MAME's DR+UL

# WF 640×640 hand-tuned sample coordinates (eyeballed from L1R1 captures;
# stable across rounds because the camera doesn't track Q*bert).
WF_APEX_TOP   = (320, 240)     # apex cube (0,0) top centre
WF_CUBE10_TOP = (290, 285)     # cube (1,0) top — DL hop dest, flipped on WF's step 1


def sample_color(img: Image.Image, xy):
    x, y = xy
    if not (0 <= x < img.width and 0 <= y < img.height):
        return None
    px = img.getpixel((x, y))
    return px[:3] if isinstance(px, tuple) else (px, px, px)


def max_channel_diff(a, b):
    return max(abs(a[i] - b[i]) for i in range(3))


def hex_color(rgb):
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def diff_round(L, R, mame_dir, wf_dir, threshold):
    rows = []
    cases = [
        ("state0", f"qbert_L{L}R{R}.png",     MAME_APEX,   WF_APEX_TOP),
        ("state1", f"qbert_hop_L{L}R{R}.png", MAME_CUBE11, WF_CUBE10_TOP),
    ]
    for state, mame_name, mame_xy, wf_xy in cases:
        mame_path = mame_dir / mame_name
        wf_path   = wf_dir / f"wf_walker_L{L}R{R}_{state}.png"
        if not mame_path.exists() or not wf_path.exists():
            rows.append((state, None, None, None, "MISSING"))
            continue
        mame_img = Image.open(mame_path).convert("RGB")
        wf_img   = Image.open(wf_path).convert("RGB")

        m_rgb = sample_color(mame_img, mame_xy)
        w_rgb = sample_color(wf_img,   wf_xy)
        if m_rgb is None or w_rgb is None:
            rows.append((state, m_rgb, w_rgb, None, "OUT-OF-FRAME"))
            continue
        d = max_channel_diff(m_rgb, w_rgb)
        verdict = "PASS" if d <= threshold else "FAIL"
        rows.append((state, m_rgb, w_rgb, d, verdict))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mame-dir",
                    default=str(REPO_ROOT / "docs/investigations/mame-screenshots"))
    ap.add_argument("--wf-dir",
                    default=str(REPO_ROOT / "docs/investigations/wf-screenshots"))
    ap.add_argument("--threshold", type=int, default=32,
                    help="Max-channel diff threshold for PASS (default 32/255).")
    args = ap.parse_args()

    mame_dir = Path(args.mame_dir)
    wf_dir   = Path(args.wf_dir)

    print(f"  L R  state    MAME       WF         dmax  verdict")
    print(f"  ---  ------   --------   --------   ----  -------")
    pass_count = 0
    total = 0
    for L in (1, 2, 3, 4):
        for R in (1, 2, 3, 4):
            rows = diff_round(L, R, mame_dir, wf_dir, args.threshold)
            for state, m, w, d, verdict in rows:
                total += 1
                m_s = hex_color(m) if m else "    -   "
                w_s = hex_color(w) if w else "    -   "
                d_s = f"{d:>4d}" if d is not None else "  - "
                print(f"  {L} {R}  {state}   {m_s}   {w_s}   {d_s}  {verdict}")
                if verdict == "PASS":
                    pass_count += 1
    print(f"\n  {pass_count}/{total} PASS")
    return 0 if pass_count == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
