"""scripts/make-soundfont-subset.py builds the engine's soundfont from FluidR3_GM (MIT): a valid, small SF2 with the preset level0.mid needs.

Skipped when the base soundfont is not on this machine (it is 145 MB and comes from `apt-get download fluid-soundfont-gm`; the script fetches it).
When present, the test builds the subset and checks it with TinySoundFont, the library the engine uses: it loads, has the piano, and renders the same
sound as the full base.
"""
import pathlib, shutil, subprocess, struct

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
BASE = pathlib.Path.home() / "tmp" / "sf" / "x" / "usr" / "share" / "sounds" / "sf2" / "FluidR3_GM.sf2"
SCRIPT = REPO / "scripts" / "make-soundfont-subset.py"

RENDER_C = r"""
#define TSF_IMPLEMENTATION
#include "tsf.h"
#include <stdio.h>
#include <math.h>
int main(int c, char** v) {
    tsf* f = tsf_load_filename(v[1]); if (!f) { printf("LOAD FAILED\n"); return 1; }
    tsf_set_output(f, TSF_MONO, 44100, 0); tsf_note_on(f, 0, 60, 0.8f);
    static float b[22050]; double e = 0; tsf_render_float(f, b, 22050, 0);
    for (int i = 0; i < 22050; i++) e += b[i] * b[i];
    printf("%d %s %.6f\n", tsf_get_presetcount(f), tsf_get_presetname(f, 0), sqrt(e / 22050)); return 0;
}
"""


def test_help_exits_zero():
    r = subprocess.run([str(SCRIPT), "--help"], capture_output=True, text=True, timeout=20)
    assert r.returncode == 0 and "FluidR3" in r.stdout and "MIT" in r.stdout


@pytest.mark.skipif(not BASE.exists() or not shutil.which("cc"), reason="needs the FluidR3 base (task soundfont fetches it) and a C compiler")
def test_subset_is_valid_small_and_sounds_the_same(tmp_path):
    out = tmp_path / "subset.sf2"
    r = subprocess.run([str(SCRIPT), "--base", str(BASE), "--out", str(out)], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr
    data = out.read_bytes()
    assert data[:4] == b"RIFF" and data[8:12] == b"sfbk" and struct.unpack("<I", data[4:8])[0] == len(data) - 8
    assert len(data) < 10 * 1024 * 1024, f"{len(data)} bytes: not a subset"
    assert b"MIT licence" in data, "the MIT notice must travel inside the file"
    (tmp_path / "r.c").write_text(RENDER_C)
    subprocess.run(["cc", "-O1", "-I", str(REPO / "engine" / "vendor" / "tsf"), "-o", str(tmp_path / "r"), str(tmp_path / "r.c"), "-lm"], check=True)
    sub = subprocess.run([str(tmp_path / "r"), str(out)], capture_output=True, text=True).stdout.split()
    full = subprocess.run([str(tmp_path / "r"), str(BASE)], capture_output=True, text=True).stdout.split()
    assert sub[0] == "1" and sub[1:3] == ["Yamaha", "Grand"], sub
    assert sub[-1] == full[-1], f"the subset renders {sub[-1]}, the full base {full[-1]}"
