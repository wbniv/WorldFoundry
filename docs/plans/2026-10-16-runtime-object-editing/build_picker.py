#!/usr/bin/env python3
"""Build the 3D object picker mockup and its PNG thumbnail.

Inlines the tank view (cropped from the seahorse plan's tank-scene.png) into
picker.tmpl -> picker.html, then renders picker.png at 1440x900 with the
system Chrome via ~/python-tui-lib/scripts/preview-shot.mjs.

    python3 docs/plans/2026-10-16-runtime-object-editing/build_picker.py [-h]
"""
import base64
import io
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCENE = HERE.parent / '2026-10-16-saltwater-seahorses' / 'tank-scene.png'
SHOT = Path.home() / 'python-tui-lib' / 'scripts' / 'preview-shot.mjs'


def main():
    from PIL import Image
    view = Image.open(SCENE).convert('RGB').crop((12, 68, 1052, 603))   # the tank view minus its HUD strip (1040x535)
    buf = io.BytesIO()
    view.save(buf, 'JPEG', quality=80, optimize=True)
    uri = 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()
    html = (HERE / 'picker.tmpl').read_text().replace('{{SCENE_JPG}}', uri)
    out = HERE / 'picker.html'
    out.write_text(html)
    full = HERE / 'picker-full.png'
    subprocess.run(['node', str(SHOT), str(out), str(full), '--width', '1440', '--height', '1000',
                    '--full', '--wait', '800'], check=True, capture_output=True)
    Image.open(full).crop((0, 0, 1440, 900)).save(HERE / 'picker.png')
    full.unlink()
    print(f'picker.html {out.stat().st_size // 1024} KB, picker.png written')


if __name__ == '__main__':
    if {'-h', '--help'} & set(sys.argv[1:]):
        print(__doc__.strip())
        sys.exit(0)
    main()
