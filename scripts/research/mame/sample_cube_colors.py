#!/usr/bin/env python3
"""
Sample Q*bert cube face colors from MAME screenshots.

Samples three points per round screenshot:
  - Apex cube top (state 0): (120, 56)
  - Apex cube left side:     (107, 65)
  - Apex cube right side:    (135, 65)
  - HUD "CHANGE TO" target:  (40, 55)   -- gives state 2 (target top color)

If post-hop screenshots exist (qbert_hop_L*R*.png in mame-screenshots/), also
samples the down-right neighbor cube top to determine state 1 vs state 2 and
classify the round as 1-step or 2-step.

File→round mapping (transition screens skip actual gameplay):
  qbert_L2R1.png = L2 transition screen  (skip)
  qbert_L3R2.png = L3 transition screen  (skip)
  qbert_L4R3.png = L4 transition screen  (skip)
"""
from PIL import Image
from pathlib import Path
from collections import Counter

SHOTS_DIR = Path(__file__).parent.parent.parent.parent / "docs/investigations/mame-screenshots"

# (file, actual_level, actual_round, notes)
FILE_MAP = [
    ("qbert_L1R1.png", 1, 1, ""),
    ("qbert_L1R2.png", 1, 2, ""),
    ("qbert_L1R3.png", 1, 3, ""),
    ("qbert_L1R4.png", 1, 4, ""),
    ("qbert_L2R1.png", None, None, "L2 transition screen"),
    ("qbert_L2R2.png", 2, 1, ""),
    ("qbert_L2R3.png", 2, 2, ""),
    ("qbert_L2R4.png", 2, 3, ""),
    ("qbert_L3R1.png", 2, 4, "flat"),
    ("qbert_L3R2.png", None, None, "L3 transition screen"),
    ("qbert_L3R3.png", 3, 1, ""),
    ("qbert_L3R4.png", 3, 2, ""),
    ("qbert_L4R1.png", 3, 3, ""),
    ("qbert_L4R2.png", 3, 4, ""),
    ("qbert_L4R3.png", None, None, "L4 transition screen"),
    ("qbert_L4R4.png", 4, 1, ""),
    ("qbert_actual_L4R2.png", 4, 2, "flat"),
    ("qbert_actual_L4R3.png", 4, 3, ""),
    ("qbert_actual_L4R4.png", 4, 4, ""),
]

# Apex cube (row 0, col 0) sample points
APEX_TOP   = (120, 56)
APEX_LEFT  = (107, 65)
APEX_RIGHT = (135, 65)

# Flat-diamond style: only top face exists (sides render black)
FLAT_TOP = (120, 58)

# HUD "CHANGE TO" indicator: small cube top in upper-left
CHANGE_TO = (40, 55)

# Down-right neighbor cube (row 1, col 1) top — for post-hop snapshots
# Verified empirically by scanning solid-color regions in known hop screenshots:
# (1,1) top diamond is at y=78-82, x=125-149; center ~(137, 80).
# (Earlier (134,75) sample was hitting Q*bert sprite spillover, not the cube top.)
HOP_TARGET_TOP = (137, 80)


def dominant_color(img, cx, cy, radius=2):
    """Most common non-black color in a small window."""
    px = img.load()
    w, h = img.size
    counts = Counter()
    for dy in range(-radius, radius+1):
        for dx in range(-radius, radius+1):
            x, y = cx+dx, cy+dy
            if 0 <= x < w and 0 <= y < h:
                r, g, b = px[x, y]
                if r+g+b > 30:
                    counts[(r,g,b)] += 1
    if not counts:
        return (0, 0, 0)
    return counts.most_common(1)[0][0]


def hex_color(c):
    return f"#{c[0]:02X}{c[1]:02X}{c[2]:02X}"


def sample_round(filepath, flat=False):
    img = Image.open(filepath)
    if flat:
        top = dominant_color(img, *FLAT_TOP)
        left = right = (0, 0, 0)
    else:
        top = dominant_color(img, *APEX_TOP)
        left = dominant_color(img, *APEX_LEFT)
        right = dominant_color(img, *APEX_RIGHT)
    target = dominant_color(img, *CHANGE_TO)
    return top, left, right, target


def sample_post_hop(filepath):
    img = Image.open(filepath)
    return dominant_color(img, *HOP_TARGET_TOP)


print(f"{'Round':<7} {'state0':<10} {'left':<10} {'right':<10} {'state2':<10} {'post-hop':<10} {'kind':<8} Notes")
print("-" * 90)

results = []
for fname, lv, rnd, notes in FILE_MAP:
    path = SHOTS_DIR / fname
    if lv is None:
        continue
    if not path.exists():
        print(f"L{lv}R{rnd}  MISSING: {fname}")
        continue
    flat = "flat" in notes
    state0, left, right, state2 = sample_round(path, flat=flat)

    # Look for matching post-hop snap (qbert_hop_L*R*.png)
    hop_fname = f"qbert_hop_L{lv}R{rnd}.png"
    hop_path = SHOTS_DIR / hop_fname
    post_hop = None
    kind = "?"
    state1 = None
    if hop_path.exists():
        post_hop = sample_post_hop(hop_path)
        # Classify: 1-step if post-hop matches state2, else 2-step
        if post_hop == state2:
            kind = "1-step"
        else:
            kind = "2-step"
            state1 = post_hop

    label = f"L{lv}R{rnd}"
    s0  = hex_color(state0)
    sl  = hex_color(left) if not flat else "—"
    sr  = hex_color(right) if not flat else "—"
    s2  = hex_color(state2)
    sph = hex_color(post_hop) if post_hop else "—"
    note_str = notes if notes else ""
    print(f"{label:<7} {s0:<10} {sl:<10} {sr:<10} {s2:<10} {sph:<10} {kind:<8} {note_str}")
    results.append({
        "lv": lv, "rnd": rnd, "flat": flat,
        "state0": state0, "left": left, "right": right,
        "state2": state2, "post_hop": post_hop,
        "state1": state1, "kind": kind, "notes": notes,
    })

# Summary stats
n_total = len(results)
n_1step = sum(1 for r in results if r["kind"] == "1-step")
n_2step = sum(1 for r in results if r["kind"] == "2-step")
n_unknown = sum(1 for r in results if r["kind"] == "?")
print()
print(f"Rounds: {n_total} total, {n_1step} 1-step, {n_2step} 2-step, {n_unknown} unknown (no post-hop snap yet)")
