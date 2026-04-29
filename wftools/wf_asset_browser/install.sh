#!/usr/bin/env bash
# Install the wf_asset_browser addon (pure Python — no build step needed).
#
# Usage:
#   ./install.sh [/path/to/blender/scripts/addons]
#
# Python files are installed as symlinks so edits to the source tree are
# reflected immediately without re-running this script.
#
# After running this, enable "Asset Browser" in:
#   Blender > Edit > Preferences > Add-ons

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── resolve Blender addons dir ────────────────────────────────────────────────
if [[ $# -ge 1 ]]; then
    ADDONS_DIR="$1"
else
    CONFIG_BASE="${XDG_CONFIG_HOME:-$HOME/.config}/blender"
    if [[ ! -d "$CONFIG_BASE" ]]; then
        echo "Blender config dir not found: $CONFIG_BASE"
        echo "Is Blender installed?  Try: sudo snap install blender --classic"
        exit 1
    fi
    BLENDER_VER=$(ls "$CONFIG_BASE" | sort -V | tail -1)
    ADDONS_DIR="$CONFIG_BASE/$BLENDER_VER/scripts/addons"
fi

DEST="$ADDONS_DIR/wf_asset_browser"
mkdir -p "$DEST"

# ── symlink Python files (edits to source are live immediately) ───────────────
for pyfile in __init__.py asset_browser.py asset_threading.py providers.py; do
    ln -sf "$SCRIPT_DIR/$pyfile" "$DEST/$pyfile"
done

# ── copy static data ──────────────────────────────────────────────────────────
cp "$SCRIPT_DIR/kenney_catalog.json"     "$DEST/kenney_catalog.json"
cp "$SCRIPT_DIR/quaternius_catalog.json" "$DEST/quaternius_catalog.json"

echo ""
echo "Installed to: $DEST"
echo ""
echo "Next steps:"
echo "  1. Open Blender"
echo "  2. Edit > Preferences > Add-ons"
echo "  3. Search 'Asset Browser' and enable it"
echo "  4. Open the 3D Viewport sidebar (N key) > Asset Browser tab"
