#!/usr/bin/env python3
"""run_spike.py — aquarium Phase 0 translucency spike: build, capture, sample.

Plan: docs/plans/2026-09-30-aquarium-level.md § Verification, Phase 0 (steps 1–4).

For each variant (default, swap, pane-last):
  1. export the test card from Blender and build it (build_level_binary.sh), report textile's
     `Translucent` column for pane.tga;
  2. run wf_game `-rate20 --capture-frame=30` → <out>/phase0-<variant>.png   (the real engine);
  3. run wf_game again and, over the debug bridge (TCP 7777), hot-swap the fragment shader for a
     copy of the stock one that keeps the texture's alpha (the pre-23e632ec output), then
     screenshot → <out>/phase0-<variant>-alphadiag.png. This is a *diagnostic*: it shows what the
     engine's depth/draw order does to a pane once its alpha reaches the blender. No engine file
     is changed; the shader lives only in the running process;
  4. sample pixels at projected world points and print them.

Usage:  python3 wflevels/aquarium_spike/run_spike.py [variant ...]
Env:    WF_GAME   engine binary   (default <repo>/engine/wf_game, else the main checkout's)
        OUT       output dir      (default ~/tmp/aquarium-spike)
Needs:  DISPLAY (wf_game opens a GL window), Blender with the wf_blender add-on, the Rust level tools.
"""
import math
import os
import re
import socket
import subprocess
import sys
import time
import json

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..'))
MAIN = os.path.expanduser('~/WorldFoundry-wbniv')
WF_GAME = os.environ.get('WF_GAME') or next(
    p for p in (os.path.join(REPO, 'engine', 'wf_game'), os.path.join(MAIN, 'engine', 'wf_game'))
    if os.path.exists(p))
LIBS = os.path.join(os.path.dirname(WF_GAME), 'libs')
GAME_CWD = os.path.join(REPO, 'wfsource', 'source', 'game')       # cd.iff resolves from here
LEVEL = os.path.join(REPO, 'wflevels', 'aquarium_spike-standalone.iff')
OUT = os.environ.get('OUT', os.path.expanduser('~/tmp/aquarium-spike'))
BACKEND = os.path.join(REPO, 'wfsource', 'source', 'gfx', 'glpipeline', 'backend_modern.cc')

# ── Scene constants (mirror blender_create_aquarium_spike.py) ────────────────
CAM = (0.0, -12.0, 2.0)
W, H = 640, 480
FOCAL = (H / 2) / math.tan(math.radians(30.0))   # display.cc SetProjection(60°, aspect, 1, 1000)
FAR_FISH = {'default': (-1.0, 1.5, 2.0), 'swap': (-1.0, 1.5, 2.0), 'pane-last': (-1.0, 1.5, 2.0)}
NEAR_FISH = (1.5, -1.5, 2.0)


def project(x, y, z):
    d = y - CAM[1]
    return int(round(W / 2 + FOCAL * (x - CAM[0]) / d)), int(round(H / 2 - FOCAL * (z - CAM[2]) / d))


def cell_centre(i, j):
    """World point at the centre of checker cell column i (0 = left), row j (0 = bottom)."""
    return (-3.0 + 0.75 * (i + 0.5), 3.0, 0.5 * (j + 0.5))


# ── Shaders for the alpha diagnostic ─────────────────────────────────────────
def _cstr(src, name):
    body = re.search(r'static const char\* ' + name + r' =\n(.*?);\n', src, re.S).group(1)
    return ''.join(eval(line.strip()) for line in body.strip().split('\n'))   # C string literals


def shaders():
    src = open(BACKEND).read()
    vs, fs = _cstr(src, 'kVS'), _cstr(src, 'kFS')
    stock_line = 'c = vec4(mix(v_color, texture(u_tex, v_uv).rgb, is_white) * v_lit, 1.0);'
    assert stock_line in fs, 'kFS changed — re-derive the alpha diagnostic'
    alpha = fs.replace(stock_line, 'vec4 t = texture(u_tex, v_uv); '
                       'c = vec4(mix(v_color, t.rgb, is_white) * v_lit, mix(1.0, t.a, is_white));')
    return vs, alpha


# ── Engine runs ──────────────────────────────────────────────────────────────
def _env():
    return dict(os.environ, LD_LIBRARY_PATH=LIBS + ':' + os.environ.get('LD_LIBRARY_PATH', ''))


def _limit_core():
    import resource
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))   # an engine abort must not dump core


def capture(png, log):
    mp4 = os.path.join(GAME_CWD, 'output.mp4')
    had_mp4 = os.path.exists(mp4)
    subprocess.run([WF_GAME, '--frame-step-smoke=40', '--cycles=1', '-rate20', '-record_video',
                    f'--capture-frame=30={png}', f'-L{LEVEL}'],
                   cwd=GAME_CWD, env=_env(), stdout=open(log, 'w'), stderr=subprocess.STDOUT,
                   timeout=180, check=False, preexec_fn=_limit_core)
    if not had_mp4 and os.path.exists(mp4):
        os.remove(mp4)                                    # -record_video's by-product
    if not os.path.exists(png):
        raise SystemExit(f'no capture written: {png} (see {log})')


def bridge_alpha_screenshot(png, log):
    vs, fs = shaders()
    p = subprocess.Popen([WF_GAME, '--frame-step-smoke=100000', '-rate20', f'-L{LEVEL}'],
                         cwd=GAME_CWD, env=_env(), stdout=open(log, 'w'), stderr=subprocess.STDOUT,
                         preexec_fn=_limit_core)
    try:
        deadline = time.time() + 20
        while True:
            try:
                s = socket.create_connection(('127.0.0.1', 7777), timeout=2)
                break
            except OSError:
                if time.time() > deadline:
                    raise
                time.sleep(0.2)
        s.settimeout(10)
        rf = s.makefile('rb')

        def call(msg, want):
            s.sendall((json.dumps(msg) + '\n').encode())
            while True:
                r = json.loads(rf.readline())
                if r.get('op') in want:
                    return r

        time.sleep(3.0)                                   # camera spring settles well before this
        r = call({'op': 'set_shader', 'vert': vs, 'frag': fs}, ('shader_reloaded', 'error'))
        assert r['op'] == 'shader_reloaded', r
        time.sleep(0.5)
        r = call({'op': 'screenshot', 'filename': png}, ('screenshot_done', 'error'))
        assert r['op'] == 'screenshot_done', r
        s.close()
    finally:
        p.terminate()
        p.wait(10)


# ── Sampling ─────────────────────────────────────────────────────────────────
def load(png):
    from PIL import Image
    return Image.open(png).convert('RGB')


def px(im, xy, r=2):
    """Mean over a (2r+1)² box — robust to the GL_LINEAR filter at texel edges."""
    x0, y0 = xy
    acc = [0, 0, 0]
    n = 0
    for y in range(y0 - r, y0 + r + 1):
        for x in range(x0 - r, x0 + r + 1):
            for c, v in enumerate(im.getpixel((x, y))):
                acc[c] += v
            n += 1
    return tuple(round(a / n) for a in acc)


def is_red(rgb):
    return rgb[0] > rgb[1] + 40


def sample(im):
    """Return a dict of named samples. Screen points come from projected world points."""
    s = {}
    # Unobstructed checker: column 7 (right of the pane's screen edge), rows clear of the near fish.
    for j in (0, 1, 6, 7):
        s[f'checker(7,{j})'] = px(im, project(*cell_centre(7, j)))
    # Pane over checker: cells whose centres project inside the pane and away from both fish.
    fx, fy = project(*FAR_FISH['default'])
    for (i, j) in ((1, 1), (2, 1), (1, 6), (2, 6), (4, 2), (4, 5), (5, 1), (5, 6)):
        xy = project(*cell_centre(i, j))
        if abs(xy[0] - fx) < 30 and abs(xy[1] - fy) < 30:
            continue
        s[f'pane/checker({i},{j})'] = px(im, xy)
    # Pane over the empty background (pane x < -3 overhangs the backdrop's left edge).
    s['pane/void'] = px(im, project(-4.0, 0.0, 2.0))
    s['far-fish centre'] = px(im, (fx, fy))
    s['near-fish centre'] = px(im, project(*NEAR_FISH))
    return s


def report(variant, stock, diag):
    print(f'\n## {variant}')
    print(f'{"sample":22s} {"stock (engine as-is)":>22s} {"alpha diagnostic":>22s}')
    for k in stock:
        print(f'{k:22s} {str(stock[k]):>22s} {str(diag[k]):>22s}')
    # Pane colour as lit: the stock pane is opaque, so its pixel *is* the lit pane colour.
    p_lit = stock['pane/void']
    a_cell = next(v for k, v in stock.items() if k.startswith('checker') and is_red(v))
    b_cell = next(v for k, v in stock.items() if k.startswith('checker') and not is_red(v))
    print(f'lit pane P = {p_lit}; lit checker cells A = {a_cell}, B = {b_cell}')
    for name, img in (('stock', stock), ('alpha diagnostic', diag)):
        worst = 0
        for k, v in img.items():
            if not k.startswith('pane/checker'):
                continue
            # background under this pane point = that cell's colour (classified by index parity)
            i, j = map(int, re.findall(r'\d+', k))
            bg = a_cell if (i + j) % 2 == CELL_A_PARITY else b_cell
            want = tuple(round((p + b) / 2) for p, b in zip(p_lit, bg))
            err = max(abs(a - b) for a, b in zip(v, want))
            worst = max(worst, err)
            print(f'  {name:17s} {k:18s} got {v} want mean(P, bg={bg}) = {want}  max|Δ| = {err}')
        print(f'  {name}: worst channel error {worst} (step 4 tolerance ±8) → {"PASS" if worst <= 8 else "FAIL"}')


CELL_A_PARITY = None   # set from the rendered image: which (i + j) parity is the red cell


def main():
    global CELL_A_PARITY
    variants = sys.argv[1:] or ['default', 'swap', 'pane-last']
    os.makedirs(OUT, exist_ok=True)
    subprocess.run([sys.executable, os.path.join(HERE, 'make_pane_texture.py')], check=True)
    for v in variants:
        args = {'default': [], 'swap': ['swap'], 'pane-last': ['pane-last']}[v]
        r = subprocess.run(['blender', '--background', '--python-exit-code', '1', '--python',
                            os.path.join(HERE, 'blender_create_aquarium_spike.py'), '--', *args],
                           cwd=REPO, capture_output=True, text=True)
        if r.returncode:
            raise SystemExit(r.stdout[-3000:] + r.stderr[-3000:])
        print(next(l for l in r.stdout.splitlines() if 'swap=' in l))
        subprocess.run(['bash', os.path.join(REPO, 'wftools', 'wf_blender', 'build_level_binary.sh'),
                        'aquarium_spike'], cwd=REPO, check=True, stdout=subprocess.DEVNULL)
        log = open(os.path.join(HERE, 'textile.log.htm')).read()
        row = re.search(r'<tr>(?:(?!</tr>).)*>pane\.tga<.*?</tr>', log, re.S)
        print('textile.log.htm pane.tga row:', re.sub(r'<[^>]+>', ' ', row.group(0)).split() if row else 'MISSING')
        order = re.findall(r"\{ 'NAME' \"(fish-a|fish-b|pane|backdrop)\" \}",
                           open(os.path.join(HERE, 'aquarium_spike.lev')).read())
        print('actor order in .lev:', ' → '.join(order))
        stock_png = os.path.join(OUT, f'phase0-{v}.png')
        diag_png = os.path.join(OUT, f'phase0-{v}-alphadiag.png')
        capture(stock_png, os.path.join(OUT, f'phase0-{v}.log'))
        bridge_alpha_screenshot(diag_png, os.path.join(OUT, f'phase0-{v}-alphadiag.log'))
        stock, diag = sample(load(stock_png)), sample(load(diag_png))
        if CELL_A_PARITY is None:
            CELL_A_PARITY = next((7 + j) % 2 for j in (0, 1, 6, 7) if is_red(stock[f'checker(7,{j})']))
        report(v, stock, diag)


if __name__ == '__main__':
    main()
