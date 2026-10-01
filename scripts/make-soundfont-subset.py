#!/usr/bin/env python3
"""make-soundfont-subset.py: build wfsource/source/game/florestan-subset.sf2 reproducibly, from a permissively licensed base soundfont.

Why this exists. The engine loads one soundfont, `florestan-subset.sf2` (audio/linux/music.cc, WF_MIDI_SOUNDFONT), through TinySoundFont. That file was
never in git (it is in .gitignore), no recipe for it was ever written down, and no copy survives: the snowgoons Android flavor's symlink to it dangles,
so its release build fails. See docs/plans/2026-09-30-aquarium-chromecast.md (Phase D). This script replaces it with a recipe anyone can run.

What it does. It reads the base soundfont (FluidR3_GM.sf2, Frank Wen, MIT licence; the Ubuntu/Debian package `fluid-soundfont-gm`), keeps ONLY the
presets that the given MIDI files actually use (General MIDI program 0 on every melodic channel unless a program change says otherwise; the drum kit,
bank 128, if channel 10 plays), and everything they reference (instruments and samples), and writes a new, much smaller SF2. The base is pinned by SHA-256.
The kept presets are written under the same bank/preset numbers, so a MIDI file selects them exactly as before.

    scripts/make-soundfont-subset.py [--base FluidR3_GM.sf2] [--midi FILE.mid ...] [--preset BANK:PROGRAM ...] [--out PATH] [-h]

  --base      the base soundfont. Default: ~/tmp/sf/x/usr/share/sounds/sf2/FluidR3_GM.sf2, else it is fetched with `apt-get download fluid-soundfont-gm`
              (no root needed; the .deb is unpacked with dpkg-deb under ~/tmp/sf/) and its licence file is checked.
  --midi      MIDI files whose instruments to keep (default: wfsource/source/game/level0.mid, which is Fur Elise: program 0 only).
  --preset    extra presets to keep, e.g. 0:0 (piano) or 128:0 (drum kit); repeatable.
  --out       default wfsource/source/game/florestan-subset.sf2 (the name the engine loads; its content is now a FluidR3 subset).

Licence. FluidR3_GM: "I hereby release Fluid under the MIT license" (Frank Wen). MIT requires the copyright and permission notice to travel with
copies: the output's INFO chunk carries it (ICOP), and the notice is in engine/vendor/README.md. The project's own asset policy (wflevels/licence_policy.toml)
does not list MIT; whether to accept it, and whether to commit the generated file, is the user's decision (the output stays gitignored until then).
"""
import argparse
import hashlib
import os
import pathlib
import struct
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
BASE_SHA256 = "74594e8f4250680adf590507a306655a299935343583256f3b722c48a1bc1cb0"     # FluidR3_GM.sf2 from fluid-soundfont-gm 3.1-5.3
WORK = pathlib.Path.home() / "tmp" / "sf"
NOTICE = ("FluidR3_GM, Copyright (c) 2000-2002, 2008 Frank Wen. Released under the MIT licence: permission is granted, free of charge, to any person "
          "obtaining a copy of this software and associated documentation files (the Software), to deal in the Software without restriction, including "
          "without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, subject to the "
          "inclusion of this notice in all copies or substantial portions of the Software. THE SOFTWARE IS PROVIDED AS IS, WITHOUT WARRANTY OF ANY KIND. "
          "This file is a subset of the original made by scripts/make-soundfont-subset.py.")


# ---- SF2 parsing -------------------------------------------------------------------------------------------------------
def chunks(buf, start, end):
    p = start
    while p + 8 <= end:
        cid, size = buf[p:p + 4], struct.unpack_from("<I", buf, p + 4)[0]
        yield cid, p + 8, size
        p += 8 + size + (size & 1)


def parse(buf):
    assert buf[:4] == b"RIFF" and buf[8:12] == b"sfbk", "not an SF2"
    out = {}
    for cid, p, size in chunks(buf, 12, len(buf)):
        if cid == b"LIST":
            kind = buf[p:p + 4]
            for sid, sp, ss in chunks(buf, p + 4, p + size):
                out[(kind, sid)] = buf[sp:sp + ss]
    return out


def recs(data, size):
    return [data[i:i + size] for i in range(0, len(data) - len(data) % size, size)]


def required_presets(midis, extra):
    """(bank, program) pairs the MIDI files use: program changes and bank selects per channel; GM defaults to bank 0 program 0, channel 10 to the drum kit."""
    keep = set(extra)
    for f in midis:
        d = pathlib.Path(f).read_bytes()
        assert d[:4] == b"MThd"
        pos = 14
        prog, bank, played = {}, {}, set()

        def vlq(p):
            v = 0
            while True:
                b = d[p]; p += 1; v = (v << 7) | (b & 0x7F)
                if not b & 0x80:
                    return v, p
        while pos < len(d):
            ln = struct.unpack(">I", d[pos + 4:pos + 8])[0]; p = pos + 8; end = p + ln; run = None
            while p < end:
                _, p = vlq(p); b = d[p]
                if b == 0xFF:
                    l, p2 = vlq(p + 2); p = p2 + l; run = None; continue
                if b in (0xF0, 0xF7):
                    l, p2 = vlq(p + 1); p = p2 + l; run = None; continue
                if b & 0x80:
                    run = b; p += 1
                ch, hi = run & 15, run >> 4
                if hi == 0xC:
                    prog[ch] = d[p]; p += 1
                elif hi == 0xD:
                    p += 1
                elif hi == 0xB:
                    if d[p] == 0:
                        bank[ch] = d[p + 1]
                    p += 2
                else:
                    if hi == 0x9 and d[p + 1] > 0:
                        played.add(ch)
                    p += 2
            pos = end
        for ch in played:
            keep.add((128, 0) if ch == 9 else (bank.get(ch, 0), prog.get(ch, 0)))
    return keep


def subset(buf, keep):
    s = parse(buf)
    phdr, pbag, pmod, pgen = (recs(s[(b"pdta", k)], n) for k, n in ((b"phdr", 38), (b"pbag", 4), (b"pmod", 10), (b"pgen", 4)))
    inst, ibag, imod, igen = (recs(s[(b"pdta", k)], n) for k, n in ((b"inst", 22), (b"ibag", 4), (b"imod", 10), (b"igen", 4)))
    shdr = recs(s[(b"pdta", b"shdr")], 46)
    smpl = s[(b"sdta", b"smpl")]

    def pr(i): return struct.unpack_from("<20sHHHIII", phdr[i])
    chosen = [i for i in range(len(phdr) - 1) if (pr(i)[2], pr(i)[1]) in keep]       # (bank, preset)
    missing = keep - {(pr(i)[2], pr(i)[1]) for i in chosen}
    if missing:
        sys.exit(f"make-soundfont-subset: the base has no preset(s) {sorted(missing)}")

    # preset i's zones are pbag[bagNdx_i : bagNdx_{i+1}]; a zone's generators are pgen[genNdx_z : genNdx_{z+1}]
    def zones(heads, bagoff, i): return range(struct.unpack_from("<H", heads[i], bagoff)[0], struct.unpack_from("<H", heads[i + 1], bagoff)[0])
    def gens(bags, z): return range(struct.unpack_from("<H", bags[z], 0)[0], struct.unpack_from("<H", bags[z + 1], 0)[0])
    def mods(bags, z): return range(struct.unpack_from("<H", bags[z], 2)[0], struct.unpack_from("<H", bags[z + 1], 2)[0])

    used_inst = []
    for i in chosen:
        for z in zones(phdr, 20 + 2 + 2, i):
            for g in gens(pbag, z):
                op, amt = struct.unpack_from("<HH", pgen[g])
                if op == 41 and amt not in used_inst:
                    used_inst.append(amt)
    used_samp = []
    for ii in used_inst:
        for z in zones(inst, 20, ii):
            for g in gens(ibag, z):
                op, amt = struct.unpack_from("<HH", igen[g])
                if op == 53 and amt not in used_samp:
                    used_samp.append(amt)
    for si in list(used_samp):                                   # a stereo sample's partner must come along
        link = struct.unpack_from("<H", shdr[si], 42)[0]
        if link < len(shdr) - 1 and link not in used_samp:
            used_samp.append(link)
    used_samp.sort()
    inst_map = {old: new for new, old in enumerate(used_inst)}
    samp_map = {old: new for new, old in enumerate(used_samp)}

    # samples: concatenate, each followed by the 46 zero samples the spec requires, and rebase the offsets
    new_smpl, new_shdr = bytearray(), []
    for old in used_samp:
        name, start, end, sl, el, rate, pitch, corr, link, typ = struct.unpack_from("<20sIIIIIBbHH", shdr[old])
        base = len(new_smpl) // 2
        new_smpl += smpl[start * 2:end * 2] + bytes(46 * 2)
        link = samp_map.get(link, 0) if link in samp_map else 0
        new_shdr.append(struct.pack("<20sIIIIIBbHH", name, base, base + (end - start), base + (sl - start), base + (el - start), rate, pitch, corr, link, typ))
    new_shdr.append(struct.pack("<20sIIIIIBbHH", b"EOS" + bytes(17), 0, 0, 0, 0, 0, 0, 0, 0, 0))

    def rebuild(first, heads, bags, modrecs, genrecs, ids, ref_op, ref_map, bagoff, head_fmt, head_size):
        nb, nm, ng, nh = [], [], [], []
        for i in ids:
            nh.append(bytearray(heads[i])); struct.pack_into("<H", nh[-1], bagoff, len(nb))
            for z in zones(heads, bagoff, i):
                nb.append(struct.pack("<HH", len(ng), len(nm)))
                for g in gens(bags, z):
                    op, raw = struct.unpack_from("<H2s", genrecs[g])
                    if op == ref_op:
                        raw = struct.pack("<H", ref_map[struct.unpack("<H", raw)[0]])
                    ng.append(struct.pack("<H2s", op, raw))
                for m in mods(bags, z):
                    nm.append(modrecs[m])
        term = bytearray(heads[-1]); struct.pack_into("<H", term, bagoff, len(nb))
        nh.append(term)
        nb.append(struct.pack("<HH", len(ng), len(nm)))
        ng.append(bytes(4)); nm.append(bytes(10))
        return nh, nb, nm, ng

    ph, pb, pm, pg = rebuild(None, phdr, pbag, pmod, pgen, chosen, 41, inst_map, 24, None, 38)
    ih, ib, im, ig = rebuild(None, inst, ibag, imod, igen, used_inst, 53, samp_map, 20, None, 22)

    def L(kind, parts):
        body = kind + b"".join(parts)
        return b"LIST" + struct.pack("<I", len(body)) + body

    def C(cid, data):
        return cid + struct.pack("<I", len(data)) + data + (b"\0" if len(data) & 1 else b"")

    def z(txt): return txt.encode("latin-1", "replace") + b"\0" + (b"\0" if (len(txt) + 1) & 1 else b"")
    info = L(b"INFO", [C(b"ifil", struct.pack("<HH", 2, 1)), C(b"isng", z("EMU8000")), C(b"INAM", z("WF subset of FluidR3_GM")),
                       C(b"ICOP", z(NOTICE)), C(b"ICMT", z("Made by scripts/make-soundfont-subset.py; see docs/plans/2026-09-30-aquarium-chromecast.md"))])
    sdta = L(b"sdta", [C(b"smpl", bytes(new_smpl))])
    pdta = L(b"pdta", [C(b"phdr", b"".join(map(bytes, ph))), C(b"pbag", b"".join(pb)), C(b"pmod", b"".join(pm)), C(b"pgen", b"".join(pg)),
                       C(b"inst", b"".join(map(bytes, ih))), C(b"ibag", b"".join(ib)), C(b"imod", b"".join(im)), C(b"igen", b"".join(ig)),
                       C(b"shdr", b"".join(new_shdr))])
    body = b"sfbk" + info + sdta + pdta
    return b"RIFF" + struct.pack("<I", len(body)) + body, (len(chosen), len(used_inst), len(used_samp))


# ---- the base soundfont ------------------------------------------------------------------------------------------------
def find_base(arg):
    if arg:
        return pathlib.Path(arg)
    sf = WORK / "x" / "usr" / "share" / "sounds" / "sf2" / "FluidR3_GM.sf2"
    if not sf.exists():
        WORK.mkdir(parents=True, exist_ok=True)
        subprocess.run(["apt-get", "download", "fluid-soundfont-gm"], cwd=WORK, check=True)
        deb = sorted(WORK.glob("fluid-soundfont-gm_*.deb"))[-1]
        subprocess.run(["dpkg-deb", "-x", str(deb), str(WORK / "x")], check=True)
    return sf


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base"); ap.add_argument("--midi", action="append"); ap.add_argument("--preset", action="append", default=[])
    ap.add_argument("--out", default=str(REPO / "wfsource" / "source" / "game" / "florestan-subset.sf2"))
    a = ap.parse_args()
    base = find_base(a.base)
    data = base.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    if sha != BASE_SHA256:
        print(f"make-soundfont-subset: WARNING the base is {sha}, not the pinned {BASE_SHA256}; the output may differ", file=sys.stderr)
    midis = a.midi or [str(REPO / "wfsource" / "source" / "game" / "level0.mid")]
    keep = required_presets(midis, [tuple(int(v) for v in p.split(":")) for p in a.preset])
    out, (np_, ni, ns) = subset(data, keep)
    pathlib.Path(a.out).write_bytes(out)
    print(f"kept presets {sorted(keep)}: {np_} preset(s), {ni} instrument(s), {ns} sample(s); {len(data) // 1024} KB -> {len(out) // 1024} KB: {a.out}")


if __name__ == "__main__":
    main()
