"""The lava lamp director, written as zForth by this generator.

docs/plans/2026-11-26-lava-lamp.md, D5-D9 and "One frame". Every word mirrors
model.py operation for operation (the same 32-bit float products in the same
order), so tests/verify_lava_lamp_forth.py can run the script in the real zForth
VM and compare it with the reference step for step. The state lives in the
level's user mailboxes (lamp.py, "Cells"), as Tide Harbour's does; the eight
blobs and their 28 pairs are unrolled with their cell numbers written in.

Per frame (ll-tick): the settings (ll-settings: colours and the Time display, on
change only), whole 1/30 s model steps from DELTA_TIME (ll-frame, at most four),
the pose of every wax mesh (ll-pose: merges, positions, scale, deform blocks),
the base's starlight holes (ll-time, on a change of minute or mode) and the
camera drift (ll-camera).

Guides (docs/level-design-troubleshooting.md): ASCII only, one backslash comment
on the first line, no and/or/<0, the definitions first and the call last. A
zForth comparison pushes -1 for true, so a flag that is stored (a visibility,
the time mode) is negated to 1 first.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lamp as L  # noqa: E402
import model as M  # noqa: E402

F = M.F
lit = M.lit
DT = lit(M.DT)
N = M.N_BLOBS


def cell(i: int, field: str) -> int:
    return L.BLOB0 + L.BLOB_STRIDE * i + L.BLOB_FIELDS.index(field)


def at(i: int, field: str) -> str:
    return f"{cell(i, field)} read-mailbox"


def put(i: int, field: str) -> str:
    return f"{cell(i, field)} write-mailbox"


def rd(c: int) -> str:
    return f"{c} read-mailbox"


def wr(c: int) -> str:
    return f"{c} write-mailbox"


def smooth_words() -> List[str]:
    # ( x e0 span -- s ): smoothstep with the span e1 - e0 given, as model.smoothstep computes it
    return [": ll-smooth >r - r> / 0 max 1 min dup dup * swap 2 * 3 swap - * ;"]


def model_words() -> List[str]:
    out = [
        f": ll-env dup {lit(0.08)} / negate exp {lit(0.75)} * {lit(0.3)} + swap {lit(0.08)} * - ;",
        f": ll-gr dup {lit(0.25)} < if {lit(0.25)} swap - dup {lit(0.72)} * * {lit(0.27)} swap - "
        f"else {lit(0.25)} - dup {lit(0.2)} * * {lit(0.27)} swap - then ;",
    ]
    for i in range(N):
        g = lambda f: at(i, f)   # noqa: E731
        p = lambda f: put(i, f)  # noqa: E731
        out.append(
            f": ll-heat{i} "
            f"{lit(0.06)} {g('r')} / {lit(0.012)} * {g('stuck')} 1 = if 2 * then "
            f"{g('stuck')} 1 = if {lit(1.1)} else {g('y')} ll-env then "
            f"{g('T')} - swap {DT} * negate expm1 negate * {g('T')} + dup {p('T')} "
            f"dup {lit(0.88)} > {g('stuck')} 1 = * if 0 {p('stuck')} then "
            f"{lit(0.5)} < {g('stuck')} 2 = * if 0 {p('stuck')} then "
            f"{g('stuck')} 0 = if {g('T')} {lit(0.6)} - {lit(0.55)} * else 0 then "
            f"{g('vy')} {lit(1.6)} * - {DT} * {g('vy')} + "
            f"{g('stuck')} if drop 0 then dup {p('vy')} "
            f"{rd(L.P1)} {g('a')} + sin-rev {lit(0.010)} * {rd(L.P2)} {g('b')} + sin-rev {lit(0.006)} * + "
            f"swap dup 0 > if drop {g('x')} {lit(-0.05)} * "
            f"else {lit(-0.01)} < if {g('x')} 0 < if {lit(-0.035)} else {lit(0.035)} then else 0 then then "
            f"+ {g('vx')} {lit(1.2)} * - {DT} * {g('vx')} + {p('vx')} ;")
    for i in range(N):
        for j in range(i + 1, N):
            a = lambda f: at(i, f)   # noqa: E731
            c = lambda f: at(j, f)   # noqa: E731
            pa = lambda f: put(i, f)  # noqa: E731
            pc = lambda f: put(j, f)  # noqa: E731
            out.append(
                f": ll-pair{i}{j} "
                f"{c('x')} {a('x')} - {c('y')} {a('y')} - 2dup hypot dup 0 = if drop {lit(1e-6)} then "
                f"{a('r')} {c('r')} + {lit(0.85)} * 2dup < if "
                f"over - {lit(1.5)} * {DT} * swap / tuck * -rot * "
                f"{a('vx')} over - {pa('vx')} {c('vx')} + {pc('vx')} "
                f"{a('vy')} over - {pa('vy')} {c('vy')} + {pc('vy')} "
                f"{c('T')} {a('T')} - {lit(0.08)} * {DT} * dup {a('T')} + {pa('T')} {c('T')} swap - {pc('T')} "
                f"else drop dup {lit(0.3)} < if "
                f"dup {lit(0.3)} / 1 swap - {lit(0.004)} * {DT} * swap / tuck * -rot * "
                f"dup {a('vx')} + {pa('vx')} {c('vx')} swap - {pc('vx')} "
                f"dup {a('vy')} + {pa('vy')} {c('vy')} swap - {pc('vy')} "
                f"else drop drop drop then then ;")
    for i in range(N):
        g = lambda f: at(i, f)   # noqa: E731
        p = lambda f: put(i, f)  # noqa: E731
        lo = f"{g('r')} {lit(0.45)} * {lit(0.03)} +"
        hi = f"1 {g('r')} {lit(0.8)} * - {lit(0.012)} -"
        out.append(
            f": ll-int{i} "
            f"{g('x')} {g('vx')} {DT} * + {g('y')} {g('vy')} {DT} * + "
            f"dup {lo} > not if drop {lo} {g('vy')} 0 < if 0 {p('vy')} then "
            f"{g('T')} {lit(0.88)} < if 1 {p('stuck')} then then "
            f"dup {hi} < not if drop {hi} {g('vy')} 0 > if 0 {p('vy')} then "
            f"{g('T')} {lit(0.5)} > if 2 {p('stuck')} then then "
            f"dup {p('y')} ll-gr {g('r')} {lit(0.9)} * - "
            f"over abs over > if swap 0 < if negate then {g('vx')} {lit(-0.2)} * {p('vx')} else drop then "
            f"{p('x')} ;")
    steps = (" ".join(f"ll-heat{i}" for i in range(N)) + " " +
             " ".join(f"ll-pair{i}{j}" for i in range(N) for j in range(i + 1, N)) + " " +
             " ".join(f"ll-int{i}" for i in range(N)))
    phases = " ".join(f"{rd(c)} {lit(rate * M.DT)} + dup floor - {wr(c)}"
                      for c, rate in ((L.P1, M.RATE1), (L.P2, M.RATE2), (L.P3, M.RATE3)))
    out.append(f": ll-step {steps} {phases} ;")
    one = f"dup {DT} < not if ll-step {DT} - then"
    out.append(f": ll-frame {rd(L.ACC)} INDEXOF_DELTA_TIME read-mailbox + {' '.join([one] * M.MAX_STEPS)} "
               f"dup {DT} < not if drop 0 then {wr(L.ACC)} ;")
    return out


def pose_words(ix: Dict[str, int]) -> List[str]:
    """ll-pose: merges (D5), positions, scale, visibility and the deform blocks; see model.pose."""
    out: List[str] = []
    wax = " ".join(rd(L.WAX_RGB + k) for k in range(3))
    # ( vy -- rise fall ): stretch along vy
    out.append(f": ll-stretch {lit(8)} * {lit(-0.6)} max {lit(0.6)} min dup 0 max {lit(0.6)} / swap negate 0 max {lit(0.6)} / ;")
    # ( turns -- wa wb )
    out.append(f": ll-wobble dup sin-rev {lit(0.5)} * {lit(0.5)} + swap cos-rev {lit(0.5)} * {lit(0.5)} + ;")
    # ( y -- glow )
    out.append(f": ll-glow {lit(0.5)} * {lit(1.2)} swap - ;")
    # ( v block -- ) and the scene placement ( x y scale actor -- ), x y in globe heights
    out.append(f": ll-place >r dup INDEXOF_X_SCALE r@ write-actor-mailbox dup INDEXOF_Y_SCALE r@ write-actor-mailbox "
               f"INDEXOF_Z_SCALE r@ write-actor-mailbox {lit(M.G)} * {lit(M.GZ0)} + INDEXOF_Z_POS r@ write-actor-mailbox "
               f"{lit(M.G)} * INDEXOF_X_POS r> write-actor-mailbox ;")
    smooth_span = lit(M.REL - F(0.75))
    for i in range(N):
        g = lambda f: at(i, f)   # noqa: E731
        blk = L.BLOCK_BLOB0 + 10 * i
        hi = f"1 {g('r')} {lit(0.8)} * - {lit(0.012)} -"
        out.append(
            f": ll-show{i} {rd(L.TAKEN0 + i)} if 0 {L.VIS_BLOB0 + i} write-mailbox else 1 {L.VIS_BLOB0 + i} write-mailbox "
            f"{g('vy')} ll-stretch {wr(blk + 1)} {wr(blk)} "
            f"{g('stuck')} 2 = if 1 else {hi} {g('y')} - {lit(0.03)} {lit(F(0) - F(0.03))} ll-smooth {lit(0.6)} * then {wr(blk + 2)} "
            f"{g('stuck')} 1 = if {g('T')} {lit(0.75)} {smooth_span} ll-smooth {wr(blk)} then "
            f"0 {wr(blk + 3)} {rd(L.P3)} {g('a')} + ll-wobble {wr(blk + 5)} {wr(blk + 4)} "
            f"{wax} {wr(blk + 8)} {wr(blk + 7)} {wr(blk + 6)} {g('y')} ll-glow {wr(blk + 9)} "
            f"{g('x')} {g('y')} {g('r')} {lit(M.G)} * {ix[f'Blob{i}']} ll-place "
            f"{blk} 10 7 {ix[f'Blob{i}']} deform-block drop then ;")
    # merges: pair (i, j) into the next free slot, greedily in index order
    for k in range(L.N_MERGED):
        blk = L.BLOCK_MERGED0 + 10 * k
        name = f"Merged{k}"
        # ( i-cells... ) the slot's word reads its pair's cells from 6 scratch cells written by the pair test:
        # 680 dx, 681 dy, 682 d, and the two blob bases in 683, 684
        out.append(
            f": ll-merge{k} 1 {L.VIS_MERGED0 + k} write-mailbox "
            f"{rd(683)} 4 + read-mailbox dup dup * * {rd(684)} 4 + read-mailbox dup dup * * "   # ( ca cc )
            f"2dup + cbrt >r "                                                                     # R on the return stack
            f"{rd(683)} read-mailbox 2 pick * {rd(684)} read-mailbox 2 pick * + 2 pick 2 pick + / >r "  # cx
            f"{rd(683)} 1 + read-mailbox 2 pick * {rd(684)} 1 + read-mailbox 2 pick * + 2 pick 2 pick + / "  # ( ca cc cy )
            f"nip nip r> swap r> "                                                                 # ( cx cy R )
            f"{rd(682)} over {lit(M.NECK_SPAN)} * / 1 min {wr(blk + 3)} "
            f"{rd(683)} 3 + read-mailbox {rd(684)} 3 + read-mailbox + {lit(0.5)} * ll-stretch {wr(blk + 1)} {wr(blk)} "
            f"0 {wr(blk + 2)} {rd(L.P3)} {rd(683)} 7 + read-mailbox + ll-wobble {wr(blk + 5)} {wr(blk + 4)} "
            f"{wax} {wr(blk + 8)} {wr(blk + 7)} {wr(blk + 6)} over ll-glow {wr(blk + 9)} "
            f"{lit(M.G)} * {ix[name]} ll-place "
            f"{rd(681)} {rd(680)} atan2-rev negate INDEXOF_ROTATION_B {ix[name]} write-actor-mailbox "
            f"{blk} 10 7 {ix[name]} deform-block drop ;")
    dispatch = " ".join(f"dup {k} = if ll-merge{k} then" for k in range(L.N_MERGED))
    out.append(f": ll-merge {rd(L.MERGES)} {dispatch} drop {rd(L.MERGES)} 1 + {wr(L.MERGES)} ;")
    for i in range(N):
        for j in range(i + 1, N):
            out.append(
                f": ll-try{i}{j} {rd(L.TAKEN0 + i)} {rd(L.TAKEN0 + j)} + 0 = {rd(L.MERGES)} {L.N_MERGED} < * if "
                f"{at(j, 'x')} {at(i, 'x')} - {at(j, 'y')} {at(i, 'y')} - 2dup hypot "
                f"dup {at(i, 'r')} {at(j, 'r')} + < if {wr(682)} {wr(681)} {wr(680)} "
                f"{cell(i, 'x')} {wr(683)} {cell(j, 'x')} {wr(684)} "
                f"1 {wr(L.TAKEN0 + i)} 1 {wr(L.TAKEN0 + j)} ll-merge else drop drop drop then then ;")
    clear = " ".join(f"0 {wr(L.TAKEN0 + i)}" for i in range(N))
    tries = " ".join(f"ll-try{i}{j}" for i in range(N) for j in range(i + 1, N))
    hide = " ".join(f"{rd(L.MERGES)} {k} > not if 0 {L.VIS_MERGED0 + k} write-mailbox then" for k in range(L.N_MERGED))
    shows = " ".join(f"ll-show{i}" for i in range(N))
    pooled = " ".join(f"{at(i, 'stuck')} 1 = if 1 + swap {at(i, 'T')} {lit(0.75)} {smooth_span} ll-smooth max swap then"
                      for i in range(N))
    pb = L.BLOCK_POOL
    out.append(f": ll-pool 0 0 {pooled} {lit(0.25)} * 1 min {wr(pb)} {wr(pb + 1)} "
               f"0 {wr(pb + 2)} 0 {wr(pb + 3)} 0 {wr(pb + 4)} 0 {wr(pb + 5)} {wax} {wr(pb + 8)} {wr(pb + 7)} {wr(pb + 6)} "
               f"{lit(1.15)} {wr(pb + 9)} {pb} 10 7 {ix['Pool']} deform-block drop ;")
    out.append(f": ll-pose {clear} 0 {wr(L.MERGES)} {tries} {hide} {shows} ll-pool ;")
    return out


def palette_words() -> List[str]:
    """The colour tables (generated from lamp.LAVA and lamp.WATER) and the tints of the static actors."""
    init = []
    for table, base in ((L.LAVA, L.LAVA_TABLE), (L.WATER, L.WATER_TABLE)):
        for k, (_name, h) in enumerate(table):
            for ch, v in enumerate(L.rgb(h)):
                init.append(f"{lit(v)} {wr(base + 3 * k + ch)}")
    out = [": ll-tables " + " ".join(init) + " ;"]
    # ( index base ch -- v )
    out.append(": ll-col >r swap 3 * + r> + read-mailbox ;")
    mix = lit(L.WAX_WATER_MIX)
    keep = lit(1 - L.WAX_WATER_MIX)
    wax = " ".join(f"{rd(L.SET_LAVA)} {L.LAVA_TABLE} {ch} ll-col {keep} * {rd(L.SET_WATER)} {L.WATER_TABLE} {ch} ll-col "
                   f"{mix} * + {wr(L.WAX_RGB + ch)}" for ch in range(3))
    tints = []
    # liquid: the water colour; glass: half way to white; wall glow: water with a third of lava, dim; table: lava and water
    recipes = {"Liquid": ("1 * 0 +", lit(1.0)), "Glass": (f"{lit(0.5)} * {lit(0.5)} +", lit(1.0)),
               "WallGlow": (None, lit(0.55)), "TableLight": (None, lit(0.8))}
    for k, name in enumerate(L.TINTED):
        blk = L.BLOCK_TINT0 + 10 * k
        expr, glow = recipes[name]
        words = []
        for ch in range(3):
            w = f"{rd(L.SET_WATER)} {L.WATER_TABLE} {ch} ll-col"
            if name == "WallGlow":
                v = f"{w} {lit(0.65)} * {rd(L.SET_LAVA)} {L.LAVA_TABLE} {ch} ll-col {lit(0.35)} * +"
            elif name == "TableLight":
                v = f"{w} {lit(0.5)} * {rd(L.SET_LAVA)} {L.LAVA_TABLE} {ch} ll-col {lit(0.5)} * +"
            else:
                v = f"{w} {expr}"
            words.append(f"{v} {wr(blk + 6 + ch)}")
        zero = " ".join(f"0 {wr(blk + w)}" for w in range(6))
        tints.append(f"{zero} {' '.join(words)} {glow} {wr(blk + 9)}")
    out.append(f": ll-tint {wax} " + " ".join(tints) + " ;")
    return out


def settings_words(ix: Dict[str, int], fields: Dict[str, int]) -> List[str]:
    """ll-settings: read the three Lava lamp fields with property@ every frame and apply them on change only."""
    s = ix["LavaLampSettings"]
    out = [f": ll-prop {s} swap property@ if nip else drop then ;"]    # ( default field -- v )
    tint_calls = " ".join(f"{L.BLOCK_TINT0 + 10 * k} 10 7 {ix[name]} deform-block drop" for k, name in enumerate(L.TINTED))
    out.append(
        f": ll-settings {rd(L.SET_INIT)} 0 = if ll-tables -1 {wr(L.SET_LAVA)} then "
        f"{L.DEFAULT_LAVA} {fields['Lava color']} ll-prop {L.DEFAULT_WATER} {fields['Water color']} ll-prop "
        f"over {rd(L.SET_LAVA)} = over {rd(L.SET_WATER)} = * {rd(L.SET_INIT)} * if drop drop else "
        f"{wr(L.SET_WATER)} {wr(L.SET_LAVA)} 1 {wr(L.SET_INIT)} ll-tint {tint_calls} then "
        f"{L.DEFAULT_TIME} {fields['Time display']} ll-prop {wr(L.SET_TIME)} ;")
    return out


def time_words() -> List[str]:
    """ll-time: WALL_HOUR and WALL_MINUTE to the four digits' visibility (D7), on a change of minute or mode only.
    Mode 0 shows the time, 1 the dashes (WALL_DAY before 2026-01-01: the clock was never set), 2 nothing (Time
    display Off: only the faint starlight holes stay)."""
    vis = []
    for p in range(4):
        for v in range(10):
            vis.append(f"{rd(L.DIGITS + p)} {v} = over 0 = * {L.VIS_DIGIT0 + 10 * p + v} write-mailbox")
    digits = (f"INDEXOF_WALL_HOUR read-mailbox floor dup 10 / floor dup {wr(L.DIGITS)} 10 * - {wr(L.DIGITS + 1)} "
              f"INDEXOF_WALL_MINUTE read-mailbox floor dup 10 / floor dup {wr(L.DIGITS + 2)} 10 * - {wr(L.DIGITS + 3)}")
    return [
        f": ll-mode {rd(L.SET_TIME)} 0 = if INDEXOF_WALL_DAY read-mailbox {L.CLOCK_SET_DAY} < negate else 2 then ;",
        f": ll-time ll-mode INDEXOF_WALL_HOUR read-mailbox floor 60 * INDEXOF_WALL_MINUTE read-mailbox floor + "
        f"over 10000 * + 1 + dup {rd(L.TIME_KEY)} = if drop drop else {wr(L.TIME_KEY)} {digits} "
        + " ".join(vis) +
        f" dup 0 = negate {L.VIS_COLON} write-mailbox 1 = negate {L.VIS_DASH} write-mailbox then ;",
    ]


def camera_words(ix: Dict[str, int], fields: Dict[str, int], cam0) -> List[str]:
    """Camera drift (the shared Clock sheet): Slow moves the shot a few degrees over ten minutes; Off holds it."""
    s = ix["LavaLampSettings"]
    x0, z0 = cam0
    shot = ix["cs_wide"]
    return [
        f": ll-camera 0 {fields['Camera drift']} ll-prop 0 = if "
        f"INDEXOF_WALL_MINUTE read-mailbox 60 * INDEXOF_WALL_SECOND read-mailbox + 600 / dup sin-rev {lit(1.6)} * {lit(x0)} + "
        f"INDEXOF_X_POS {shot} write-actor-mailbox cos-rev {lit(0.5)} * {lit(z0)} + INDEXOF_Z_POS {shot} write-actor-mailbox "
        f"else {lit(x0)} INDEXOF_X_POS {shot} write-actor-mailbox {lit(z0)} INDEXOF_Z_POS {shot} write-actor-mailbox then ;"
    ]


def initial_words(lamp: M.Lamp) -> List[str]:
    """The warmed state (D9, baked at build time) written once, on the first frame."""
    sets = []
    for i, b in enumerate(lamp.blobs):
        for f in L.BLOB_FIELDS:
            sets.append(f"{lit(b[f])} {put(i, f)}")
    for c, v in ((L.P1, lamp.p1), (L.P2, lamp.p2), (L.P3, lamp.p3)):
        sets.append(f"{lit(v)} {wr(c)}")
    return [": ll-start " + " ".join(sets) + f" 0 {wr(L.ACC)} 1 {wr(L.BLOB0 + 9)} ;"]


def definitions(ix: Dict[str, int], fields: Dict[str, int], cam0=(0.0, 12.8), lamp: M.Lamp | None = None) -> str:
    lamp = lamp or M.warmed()
    lines = ["\\ Lava lamp director: the wax model of model.py with merges, the base holes, the settings."]
    lines += smooth_words() + model_words() + pose_words(ix) + palette_words() + settings_words(ix, fields)
    lines += time_words() + camera_words(ix, fields, cam0) + initial_words(lamp)
    lines.append(f": ll-tick {rd(L.BLOB0 + 9)} 0 = if ll-start then ll-settings ll-frame ll-pose ll-time ll-camera ;")
    return "\n".join(lines)


def director_script(ix: Dict[str, int], fields: Dict[str, int], cam0=(0.0, 12.8), lamp: M.Lamp | None = None) -> str:
    return definitions(ix, fields, cam0, lamp) + "\nll-tick"


def default_indices() -> Dict[str, int]:
    """Actor indices for tests run without a generated level (the generator passes the real map)."""
    names = ["Director", "LavaLampSettings", "cs_wide", "Pool"] + [f"Blob{i}" for i in range(N)] + \
        [f"Merged{k}" for k in range(L.N_MERGED)] + list(L.TINTED)
    return {n: 10 + k for k, n in enumerate(names)}


def default_fields() -> Dict[str, int]:
    return {"Camera drift": 30, "Lava color": 31, "Water color": 32, "Time display": 33}
