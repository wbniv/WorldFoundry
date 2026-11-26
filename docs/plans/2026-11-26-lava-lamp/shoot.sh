#!/usr/bin/env bash
# shoot.sh: render every mockup page in this bundle to a same-basename PNG (1440x900).
# Waits on the page's own ready flag (window.__ready), never on a fixed delay, and pins
# the displayed time to 21:47 so the PNGs are reproducible.
#   bash docs/plans/2026-11-26-lava-lamp/shoot.sh [page.html ...]
set -euo pipefail
case "${1:-}" in -h|--help) sed -n '2,5p' "$0"; exit 0;; esac
HERE="$(cd "$(dirname "$0")" && pwd)"
SHOT="$HOME/python-tui-lib/scripts/preview-shot.mjs"
cd "$HERE"
pages=("$@"); [ ${#pages[@]} -eq 0 ] && pages=(*.html)
for p in "${pages[@]}"; do
  out="${p%.html}.png"
  node "$SHOT" "$HERE/$p" "$HERE/$out" --width 1440 --height 900 --full --wait 0 \
    --eval "await new Promise(r=>{const c=()=>window.__ready?r():requestAnimationFrame(c);c();}); if(window.setClock)window.setClock('21:47'); await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));"
  # The plan bundle caps each file at 512 KB: quantise to a 256-colour palette when over.
  if [ "$(stat -c %s "$out")" -gt 500000 ]; then
    python3 -c "import sys;from PIL import Image;im=Image.open(sys.argv[1]).convert('RGB');im.quantize(256,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.FLOYDSTEINBERG).save(sys.argv[1],optimize=True)" "$out"
  fi
  echo "$out $(stat -c %s "$out")"
done
