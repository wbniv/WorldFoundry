#!/usr/bin/env python3
"""Pixel-diff WF walker captures against the MAME walker captures.

Compares the cube-top color signature for each round, state-0 and state-1.
MAME side reads at the documented hardcoded sample coords; WF side reads at
camera-projected cube positions (apex + cube(1,1)). Pass = max-channel diff
< THRESHOLD (default 32/255).
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[3]

# MAME framebuffer sample coordinates — see scripts/research/mame/sample_cube_colors.py
# These are pixel-perfect for the MAME PNGs (256x256ish viewport).
MAME_APEX = (120, 56)        # apex cube (0,0) top
MAME_CUBE11 = (137, 80)      # down-right cube (1,1) top

# WF camera config (mirrors blender_create_qbert.py CAMSHOT_POS/CAMSHOT_LOOKAT).
WF_CAM_POS    = (0.0, -15.0, 19.0)
WF_CAM_LOOKAT = (0.0, 3.0, 8.5)
WF_FOV_Y_DEG  = 60.0   # default; refine empirically if cube positions miss

# World coords of the two sample cubes (top centers, +1 above cube center).
# Mirrors cube_world_position(0,0) and cube_world_position(1,0) with the
# diamond layout: apex at (0, 6√2, 13), cube(1,0) at (-√2, 5√2, 11).
# WF walker hops DL on step 1 (= cube(1,0)) to get state-1 captures; MAME
# walker hops DR (= cube(1,1)) — the colour is the same per round, only
# the on-screen sample location differs.
SQRT2 = math.sqrt(2.0)
APEX_TOP_WORLD     = (0.0,          6.0 * SQRT2, 14.0)   # 13 + 1 (top face)
CUBE_FLIPPED_WORLD = (-SQRT2 * 1.0, 5.0 * SQRT2, 12.0)   # cube(1,0) top — DL hop dest


def vec_sub(a, b):
    return (a[0]-b[0], a[1]-b[1], a[2]-b[2])

def vec_add(a, b):
    return (a[0]+b[0], a[1]+b[1], a[2]+b[2])

def vec_scale(a, s):
    return (a[0]*s, a[1]*s, a[2]*s)

def vec_dot(a, b):
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]

def vec_cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])

def vec_norm(a):
    m = math.sqrt(vec_dot(a, a))
    return (a[0]/m, a[1]/m, a[2]/m) if m else a


def project_world_to_pixel(world, cam_pos, cam_lookat, fov_y_deg, w, h):
    """Project a world-space point to pixel coords (top-left origin, +y down).

    Right-handed look-at, perspective with vertical fov; aspect = w/h.
    Returns (x, y) in pixels or None if behind the camera.
    """
    fwd = vec_norm(vec_sub(cam_lookat, cam_pos))
    # Up-world is +Z (Z-up convention in WF level files).
    up_world = (0.0, 0.0, 1.0)
    right = vec_norm(vec_cross(fwd, up_world))
    up    = vec_cross(right, fwd)

    rel = vec_sub(world, cam_pos)
    cx, cy, cz = vec_dot(rel, right), vec_dot(rel, up), vec_dot(rel, fwd)
    if cz <= 1e-3:
        return None

    fov_y = math.radians(fov_y_deg)
    f = 1.0 / math.tan(fov_y * 0.5)
    aspect = w / h
    ndc_x = (cx / cz) * (f / aspect)
    ndc_y = (cy / cz) * f
    px = (ndc_x * 0.5 + 0.5) * w
    py = (1.0 - (ndc_y * 0.5 + 0.5)) * h
    return (int(round(px)), int(round(py)))


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


def diff_round(L, R, mame_dir, wf_dir, fov_deg, threshold):
    rows = []
    for state, mame_name, mame_xy, wf_world in [
        ("state0", f"qbert_L{L}R{R}.png",     MAME_APEX,   APEX_TOP_WORLD),
        ("state1", f"qbert_hop_L{L}R{R}.png", MAME_CUBE11, CUBE_FLIPPED_WORLD),
    ]:
        mame_path = mame_dir / mame_name
        wf_path   = wf_dir / f"wf_walker_L{L}R{R}_{state}.png"
        if not mame_path.exists() or not wf_path.exists():
            rows.append((state, None, None, None, "MISSING"))
            continue
        mame_img = Image.open(mame_path).convert("RGB")
        wf_img   = Image.open(wf_path).convert("RGB")

        wf_xy = project_world_to_pixel(
            wf_world, WF_CAM_POS, WF_CAM_LOOKAT,
            fov_deg, wf_img.width, wf_img.height)

        m_rgb = sample_color(mame_img, mame_xy)
        w_rgb = sample_color(wf_img, wf_xy) if wf_xy else None
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
    ap.add_argument("--fov", type=float, default=WF_FOV_Y_DEG,
                    help="Vertical FOV in degrees. Tune if cube samples land off-target.")
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
            rows = diff_round(L, R, mame_dir, wf_dir, args.fov, args.threshold)
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
