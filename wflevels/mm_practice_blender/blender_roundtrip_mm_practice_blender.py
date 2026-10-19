"""
blender_roundtrip_mm_practice_blender.py — import mm_practice_blender.lev, re-export as _rt.lev.

Run headlessly:
  blender --background --python blender_roundtrip_mm_practice_blender.py
"""

import bpy
import os
import addon_utils

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
IN_LEV  = os.path.join(SCRIPT_DIR, 'mm_practice_blender.lev')
OUT_LEV = os.path.join(SCRIPT_DIR, 'mm_practice_blender_rt.lev')

bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("wf_blender", default_set=False, persistent=False)

print(f"[rt] Importing {IN_LEV}")
bpy.ops.wf.import_level(filepath=IN_LEV)

print(f"[rt] Objects after import: {[o.name for o in bpy.data.objects]}")

print(f"[rt] Exporting to {OUT_LEV}")
bpy.ops.wf.export_level(filepath=OUT_LEV)

print(f"[rt] Done — {OUT_LEV}")
