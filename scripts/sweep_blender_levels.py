#!/usr/bin/env python3
"""sweep_blender_levels.py — rebuild every Blender-built level and render it before and after.

    python3 scripts/sweep_blender_levels.py [--only LEVEL,…] [--out DIR] [--no-before]

For each level in LEVELS: capture a frame of the current standalone .iff (before), run the
level's Blender script + build_level_binary.sh, capture again (after), then write
<out>/contact-sheet.png (one row per level: before | after | after with WF_CULL=1) and
<out>/sweep.log. Levels whose script needs an input this machine lacks are reported as
SKIPPED, never silently passed. Capture is `wf_game -record_video` for CAPTURE_S seconds,
last clean frame (the recorder runs at level-clock speed).

Written for docs/plans/2026-09-19-exporter-face-hand.md; reusable for any exporter change.
"""
import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WF = REPO / 'engine' / 'wf_game'
CAPTURE_S = 6
VRAM_BIG = ['--vram-width=4096', '--vram-height=2048', '--vram-slot-width=1024', '--vram-slot-height=1024',
            '--vram-perm-width=1024', '--vram-perm-height=1024']
VRAM_MOON = ['--vram-width=4096', '--vram-height=2048', '--vram-slot-width=1024', '--vram-slot-height=1024',
             '--vram-perm-width=1024', '--vram-perm-height=512']

# level name → (blender script, extra engine flags, precondition path or None)
LEVELS = {
    'condo_639_640':      ('wflevels/condo_639_640/blender_create_condo.py', VRAM_BIG, os.path.expanduser('~/docs/aircon/units-639-640.blend')),
    'moon_site01':        ('wflevels/moon_site01/blender_create_moon.py', VRAM_MOON, 'wflevels/moon_site01/terrain_texture.tga'),
    'qbert_practice':     ('wflevels/qbert_practice/blender_create_qbert.py', [], None),
    'smb_w1_1':           ('wflevels/smb_w1_1/blender_create_smb.py', [], None),
    'smb_w1_2':           ('wflevels/smb_w1_2/blender_create_smb_w1_2.py', [], None),
    'smb_w1_3':           ('wflevels/smb_w1_3/blender_create_smb_w1_3.py', [], None),
    'smb_w1_4':           ('wflevels/smb_w1_4/blender_create_smb_w1_4.py', [], None),
    'pilot_demo':         ('wflevels/pilot_demo/blender_create_pilot_demo.py', [], None),
    'treemap':            ('wflevels/treemap/blender_treemap.py', [], None),
    'filesys':            ('wflevels/filesys/blender_filesys.py', [], None),
    'filelight':          ('wflevels/filelight/blender_filelight.py', [], None),
    'dome':               ('wflevels/dome/blender_dome.py', [], None),
    'mm_practice_blender_rt': ('wflevels/mm_practice_blender/blender_roundtrip_mm_practice_blender.py', [], None),
}


def log(msg, f):
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {msg}"
    print(line, flush=True); f.write(line + '\n'); f.flush()


def capture(iff: Path, out_png: Path, flags, cull=False) -> bool:
    env = dict(os.environ, LD_LIBRARY_PATH=f"{REPO / 'engine' / 'libs'}", DISPLAY=os.environ.get('DISPLAY', ':0'))
    if cull:
        env['WF_CULL'] = '1'
    work = out_png.parent / '.work'; work.mkdir(exist_ok=True)
    for stale in work.glob('output.mp4'):
        stale.unlink()
    cmd = [str(WF), *flags, '-width=640', '-height=480', '-record_video', f'-L{iff}']
    try:
        subprocess.run(['timeout', '-s', 'INT', str(CAPTURE_S), *cmd], cwd=work, env=env,
                       stdout=open(out_png.with_suffix('.log'), 'w'), stderr=subprocess.STDOUT, timeout=CAPTURE_S + 30)
    except subprocess.TimeoutExpired:
        return False
    time.sleep(1.0)
    mp4 = work / 'output.mp4'
    if not mp4.exists() or mp4.stat().st_size < 5000:
        return False
    n = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames',
                        '-of', 'csv=p=0', str(mp4)], capture_output=True, text=True).stdout.strip()
    try:
        n = int(n)
    except ValueError:
        return False
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(mp4), '-vf', f'select=eq(n\\,{max(n - 2, 0)})', '-vframes', '1', str(out_png)], check=False)
    mp4.unlink(missing_ok=True)
    return out_png.exists()


def build(level: str, script: str, f) -> bool:
    r = subprocess.run(['blender', '--background', '--python-exit-code', '1', '--python', script],
                       cwd=REPO, capture_output=True, text=True, timeout=1800)
    tail = '\n'.join(r.stdout.splitlines()[-6:])
    if r.returncode != 0:
        log(f"  blender FAILED ({r.returncode}):\n{tail}\n{r.stderr[-800:]}", f)
        return False
    r2 = subprocess.run(['bash', 'wftools/wf_blender/build_level_binary.sh', level], cwd=REPO, capture_output=True, text=True, timeout=900)
    if r2.returncode != 0:
        log(f"  build_level_binary FAILED:\n{r2.stdout[-800:]}\n{r2.stderr[-400:]}", f)
        return False
    return True


def contact_sheet(rows, out: Path):
    from PIL import Image, ImageDraw
    W, H = 320, 240
    sheet = Image.new('RGB', (W * 3 + 40, (H + 24) * len(rows) + 30), (28, 30, 34))
    d = ImageDraw.Draw(sheet)
    d.text((10, 6), 'before (old exporter)              after (Blender-hand exporter)              after, WF_CULL=1', fill=(230, 230, 230))
    for i, (name, imgs, note) in enumerate(rows):
        y = 30 + i * (H + 24)
        d.text((10, y + 4), f"{name}  {note}", fill=(255, 220, 120))
        for j, p in enumerate(imgs):
            if p and Path(p).exists():
                im = Image.open(p).convert('RGB').resize((W, H))
                sheet.paste(im, (10 + j * (W + 10), y + 20))
            else:
                d.rectangle([10 + j * (W + 10), y + 20, 10 + j * (W + 10) + W, y + 20 + H], outline=(90, 90, 90))
                d.text((20 + j * (W + 10), y + 30), 'n/a', fill=(150, 150, 150))
    sheet.save(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--only', help='comma-separated level names')
    ap.add_argument('--out', default='docs/plans/2026-09-19-exporter-face-hand', help='output dir (contact sheet, frames, log)')
    ap.add_argument('--no-before', action='store_true', help='skip the before capture (already taken)')
    a = ap.parse_args()
    out = (REPO / a.out).resolve(); out.mkdir(parents=True, exist_ok=True)
    names = a.only.split(',') if a.only else list(LEVELS)
    rows = []
    with open(out / 'sweep.log', 'a') as f:
        log(f"sweep start: {names}", f)
        for name in names:
            script, flags, pre = LEVELS[name]
            iff = REPO / 'wflevels' / f'{name}-standalone.iff'
            before, after, cull = out / f'{name}-before.png', out / f'{name}-after.png', out / f'{name}-after-cull.png'
            if pre and not Path(pre).exists():
                log(f"{name}: SKIPPED — needs {pre}", f); rows.append((name, [None, None, None], f'SKIPPED: needs {pre}')); continue
            if not a.no_before and iff.exists():
                log(f"{name}: capture before", f); capture(iff, before, flags)
            log(f"{name}: build ({script})", f)
            ok = build(name, script, f)
            if not ok:
                rows.append((name, [before, None, None], 'BUILD FAILED')); continue
            log(f"{name}: capture after", f); capture(iff, after, flags)
            capture(iff, cull, flags, cull=True)
            rows.append((name, [before, after, cull], 'ok'))
        contact_sheet(rows, out / 'contact-sheet.png')
        log(f"contact sheet → {out / 'contact-sheet.png'}", f)
    for name, _, note in rows:
        print(f"{name:26s} {note}")


if __name__ == '__main__':
    main()
