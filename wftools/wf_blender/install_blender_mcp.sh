#!/usr/bin/env bash
# install_blender_mcp.sh — headless install of the blender-mcp addon
#
# The community blender-mcp addon (Blender 3.0+, works with 4.0.2) connects
# Blender to Claude Code via the `uvx blender-mcp` MCP server.
#
# Usage:
#   bash wftools/wf_blender/install_blender_mcp.sh
#
# After running, open Blender → N panel → BlenderMCP → Connect to Claude.

set -euo pipefail

ADDON_URL="https://raw.githubusercontent.com/ahujasid/blender-mcp/main/addon.py"
TMP_ADDON="/tmp/blender_mcp_addon.py"

echo "[1/3] Downloading blender-mcp addon..."
curl -fsSL "$ADDON_URL" -o "$TMP_ADDON"
echo "      $(wc -l < "$TMP_ADDON") lines downloaded"

echo "[2/3] Installing into Blender (headless)..."
blender --background --python-expr "
import bpy, sys

result = bpy.ops.preferences.addon_install(filepath='$TMP_ADDON', overwrite=True)
if 'FINISHED' not in result:
    print('ERROR: addon_install returned', result, file=sys.stderr)
    sys.exit(1)

# The installed module name is the filename stem: blender_mcp_addon
bpy.ops.preferences.addon_enable(module='blender_mcp_addon')
bpy.ops.wm.save_userpref()
print('blender_mcp_addon: installed and enabled')
" 2>&1 | grep -v "^$\|^Blender \|^Read prefs\|Warning:"

echo "[3/3] Verifying..."
blender --background --python-expr "
import bpy, sys
enabled = 'blender_mcp_addon' in bpy.context.preferences.addons
print('addon enabled:', enabled)
if not enabled:
    sys.exit(1)
" 2>&1 | grep "addon enabled:"

echo
echo "Done. Open Blender, press N in the 3D Viewport → BlenderMCP tab → Connect to Claude."
