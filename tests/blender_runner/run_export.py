"""
run_export.py — invoked inside Blender by the wf_blender test harness.

Usage (you don't invoke this directly; pytest does):

    BLENDER_USER_SCRIPTS=<tempdir>  # tempdir has scripts/addons/wf_blender
    WF_EXPORT_OUT=<path-to-out.lev>
    blender -b <fixture.blend> --python run_export.py

Reads $WF_EXPORT_OUT for the output .lev path. Enables the wf_blender add-on
(Blender finds it via $BLENDER_USER_SCRIPTS), calls bpy.ops.wf.export_level
with the requested path, and exits non-zero if anything goes wrong.

Headless-safe: no UI calls, no operator file dialogs.
"""

import os
import sys
import traceback

import bpy
import addon_utils


def _fail(msg: str, exit_code: int = 1) -> None:
    sys.stderr.write(f"run_export: ERROR: {msg}\n")
    # Blender swallows non-zero exit codes from --python scripts in some
    # configurations; bpy.app.exit is the recommended path.
    sys.exit(exit_code)


def main() -> None:
    out_path = os.environ.get("WF_EXPORT_OUT")
    if not out_path:
        _fail("missing required env var WF_EXPORT_OUT")

    # Blender resolved $BLENDER_USER_SCRIPTS at startup; verify the addon is
    # discoverable from this Blender's perspective.
    if "wf_blender" not in {a.__name__ for a in addon_utils.modules()}:
        _fail(
            "wf_blender not discoverable by addon_utils. Verify the test "
            "harness set $BLENDER_USER_SCRIPTS to a dir containing "
            "scripts/addons/wf_blender/__init__.py before launching Blender."
        )

    # Enable the addon. persistent=False so the user-prefs aren't mutated.
    # addon_utils.enable returns the module on success or None on failure.
    try:
        mod = addon_utils.enable(
            "wf_blender",
            default_set=False,
            persistent=False,
        )
    except Exception as e:
        _fail(f"addon_utils.enable raised: {e}\n{traceback.format_exc()}")
    if mod is None:
        _fail("wf_blender failed to load (addon_utils.enable returned None — "
              "check Blender stdout above for the import-time exception)")

    if not hasattr(bpy.ops.wf, "export_level"):
        _fail("bpy.ops.wf.export_level not registered after enabling wf_blender")

    print(f"run_export: exporting to {out_path}", flush=True)
    try:
        result = bpy.ops.wf.export_level(filepath=out_path)
    except Exception as e:
        _fail(f"bpy.ops.wf.export_level raised: {e}\n{traceback.format_exc()}")

    if result != {"FINISHED"}:
        _fail(f"export operator returned {result}, expected {{'FINISHED'}}")

    if not os.path.exists(out_path):
        _fail(f"operator claimed FINISHED but {out_path} does not exist")

    size = os.path.getsize(out_path)
    print(f"run_export: wrote {out_path} ({size} bytes)", flush=True)


# Blender's --python loader runs the script with __name__ == "__main__"
if __name__ == "__main__":
    main()
