from PIL import Image, ImageDraw
import math, os

T = 1.5

# ── Layout data (must stay in sync with blender_create_smb_w1_4.py) ──────────
TOTAL_COLS   = 160
CEIL_Z       =  8          # tiles
LAVA1_PLATS  = [(16, 19), (21, 24), (26, 29)]   # 3 stepping stones across lava pit 1
PLAT_Z       =  0          # platform tops at floor level
BRIDGE_COLS  = (122, 152)  # boss-bridge stand-in
BRIDGE_Z     =  3
# (pivot_col, pivot_z_tiles, initial_angle_deg). Floor/platform bars pivot at
# Z=2T, ceiling bars at Z=6T; 5 segments at 0.4T spacing → 2T (3 m) max radius.
FIREBARS = [
    (22, 2,   0),   # FB#1  on lava-pit-1 platform
    (42, 2,  90),   # FB#2  corridor floor
    (50, 6,   0),   # FB#3  corridor ceiling
    (58, 2,  45),   # FB#4  corridor floor
    (66, 6, 135),   # FB#5  corridor ceiling
    (76, 2,   0),   # FB#6  fire-bar room low
    (84, 6,  90),   # FB#7  fire-bar room high
]
SEG_SPACING_T = 0.4   # tiles between segments (matches blender_create_smb_w1_4.py)
HIDDEN_BLOCK_COLS = [94, 97, 100, 103, 106, 109]   # hidden ? blocks, Z=5T
POWERUP_COL  = 22; POWERUP_Z = 4   # ? block above lava-pit-1 platform
BOWSER_COL   = 138
AXE_COL      = 152
MARIO_COL    =   2

GROUND_SECTIONS = [
    (  0,  14, 'floor'),
    ( 14,  32, 'lava'),
    ( 32, 120, 'floor'),
    (120, 154, 'lava'),
    (154, 160, 'floor'),
]
STAIRS = [(10, 'down', 4), (32, 'up', 4)]

# ── Canvas ────────────────────────────────────────────────────────────────────
ROWS = 12
PX   =  7
MX, MGT, MGB = 30, 30, 24
W = MX*2 + TOTAL_COLS * PX
H = MGT + MGB + ROWS * PX

BG      = ( 28,  28,  28)
GRAY    = (100, 100, 100)
GRAY_DK = ( 60,  60,  60)
LAVA_HI = (255,  80,   0)
LAVA_LO = (180,  30,   0)
GOLD    = (255, 216,   0)
RED     = (220,  40,  40)
GREEN   = ( 24, 150,  40)
WHITE   = (255, 255, 255)
ORANGE  = (255, 140,   0)

img = Image.new("RGB", (W, H), BG)
d   = ImageDraw.Draw(img)

def X(col):  return MX + col * PX
def Y(z_t):  return MGT + (ROWS - z_t) * PX

GROUND_Y = Y(0)

# ── Floor / lava / ceiling ────────────────────────────────────────────────────
for c0, c1, kind in GROUND_SECTIONS:
    if kind == 'floor':
        d.rectangle([X(c0), GROUND_Y, X(c1), GROUND_Y + PX], fill=GRAY, outline=GRAY_DK)
    else:
        d.rectangle([X(c0), GROUND_Y + PX//2, X(c1), GROUND_Y + 2*PX], fill=LAVA_LO)
        d.rectangle([X(c0), GROUND_Y,          X(c1), GROUND_Y + PX//2], fill=LAVA_HI)

d.rectangle([X(0), Y(CEIL_Z) - PX, X(TOTAL_COLS), Y(CEIL_Z)], fill=GRAY, outline=GRAY_DK)

# ── Staircases ────────────────────────────────────────────────────────────────
for col, direction, n in STAIRS:
    for i in range(n):
        z = (n - i) if direction == 'down' else (i + 1)
        sc = col + i
        d.rectangle([X(sc), Y(z), X(sc + 1), Y(0)], fill=GRAY, outline=GRAY_DK)

# ── Platforms ─────────────────────────────────────────────────────────────────
for c0, c1 in LAVA1_PLATS:    # 3 stepping stones across lava pit 1
    d.rectangle([X(c0), Y(PLAT_Z), X(c1), Y(PLAT_Z) + PX//2], fill=GRAY, outline=GRAY_DK)

c0, c1 = BRIDGE_COLS
d.rectangle([X(c0), Y(BRIDGE_Z), X(c1), Y(BRIDGE_Z) + PX//2], fill=GRAY, outline=GRAY_DK)
mid = (c0 + c1) // 2
d.text((X(mid) - 42, Y(BRIDGE_Z) - PX - 8), "BOSS BRIDGE (static stand-in)", fill=WHITE)

# ── Fire-Bars ─────────────────────────────────────────────────────────────────
N_SEGS = 5
for i, (pc, pz, angle_deg) in enumerate(FIREBARS):
    cx = X(pc) + PX//2
    cy = Y(pz) + PX//2
    d.ellipse([cx-3, cy-3, cx+3, cy+3], fill=GRAY)
    for seg in range(1, N_SEGS + 1):
        a = math.radians(angle_deg)
        r = seg * SEG_SPACING_T * PX          # 0.4-tile spacing → 2-tile max radius
        sx = cx + r * math.cos(a)
        sy = cy - r * math.sin(a)
        d.ellipse([sx-2, sy-2, sx+2, sy+2], fill=ORANGE)
    d.text((cx - 6, cy - PX - 6), f"FB{i+1}", fill=ORANGE)

# ── ? blocks ─────────────────────────────────────────────────────────────────
def draw_qblock(col, z_t, hidden=False):
    fill = (70, 70, 70) if hidden else (230, 160, 30)
    out  = (40, 40, 40) if hidden else (120,  70,  0)
    cx = X(col) + PX//2
    cy = Y(z_t) + PX//2
    d.rectangle([cx - PX//2, cy - PX//2, cx + PX//2, cy + PX//2], fill=fill, outline=out)
    d.text((cx - 3, cy - 5), "?", fill=(180, 180, 180) if hidden else (80, 40, 0))

draw_qblock(POWERUP_COL, POWERUP_Z)
for hc in HIDDEN_BLOCK_COLS:
    draw_qblock(hc, 5, hidden=True)

# ── Fake Bowser ───────────────────────────────────────────────────────────────
bx = X(BOWSER_COL) + PX//2
bz = Y(BRIDGE_Z) - 2*PX
d.ellipse([bx-8, bz-8, bx+8, bz+8], fill=GREEN, outline=(0, 0, 0))
d.text((bx - 12, bz - 20), "BOWSER", fill=GREEN)

# ── Axe ───────────────────────────────────────────────────────────────────────
ax = X(AXE_COL) + PX//2
az = Y(BRIDGE_Z) - PX
d.line([ax-5, az+5, ax+5, az-5], fill=GOLD, width=3)
d.line([ax-5, az-5, ax+5, az+5], fill=GOLD, width=3)
d.text((ax - 6, az - 16), "AXE", fill=GOLD)

# ── Mario spawn ───────────────────────────────────────────────────────────────
mx = X(MARIO_COL) + PX//2
mz = Y(1)
d.rectangle([mx-3, mz-6, mx+3, mz+2], fill=RED)
d.text((mx - 8, mz - 16), "Mario", fill=WHITE)

# ── Column ticks ──────────────────────────────────────────────────────────────
for col in range(0, TOTAL_COLS + 1, 20):
    d.line([X(col), GROUND_Y, X(col), GROUND_Y + 6], fill=WHITE)
    d.text((X(col) - 6, H - 14), f"{col}", fill=WHITE)

# ── Section labels ────────────────────────────────────────────────────────────
labels = [
    ( 2, 9, "ENTRY"),
    (16, 9, "LAVA 1"),
    (40, 9, "FIRE-BAR CORRIDOR"),
    (71, 9, "FB\nRM"),
    (94, 9, "HIDDEN\nBLOCKS"),
    (126, 9, "LAVA 2 / BOSS BRIDGE"),
    (155, 9, "TOAD"),
]
for col, z_t, txt in labels:
    d.text((X(col), Y(z_t) + 2), txt, fill=(180, 180, 180))

d.text((MX, 6),
    "SMB World 1-4 (Castle) — side elevation (to scale, 1 tile = 1.5 m)  "
    "FB=Fire-Bar  [?]=powerup  dark[?]=hidden  ✕=axe  B=Bowser",
    fill=WHITE)

out_dir  = os.path.join(os.path.dirname(__file__), "..", "docs", "plans", "screenshots")
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "2026-06-03-smb-w1-4-layout-diagram.png")
img.save(out_path)
print("diagram:", img.size, "→", out_path)
