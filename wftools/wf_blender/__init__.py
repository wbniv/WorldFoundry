"""
World Foundry Blender Add-on
============================

Attaches OAD-driven schemas to Blender objects and provides:
  - dynamic property panel (rendered from Rust schema descriptors)
  - validation
  - .iff.txt export

Installation
------------
Copy this directory (wf_blender/) and wf_core.so into your Blender add-ons folder:
  ~/.config/blender/<version>/scripts/addons/wf_blender/

The wf_core.so lives in:
  wftools/wf_py/target/wheels/  (extract from wheel, or build with maturin)

Then enable "World Foundry" in Edit > Preferences > Add-ons.
"""

import sys
import os
import functools

bl_info = {
    "name":        "World Foundry",
    "author":      "World Foundry",
    "version":     (0, 1, 0),
    "blender":     (4, 0, 0),
    "location":    "Properties > Object > World Foundry",
    "description": "OAD schema-driven game object attributes",
    "category":    "Game Engine",
}

# ---------------------------------------------------------------------------
# wf_core import — the compiled Rust extension must live next to this file.
# ---------------------------------------------------------------------------

_addon_dir = os.path.dirname(__file__)
if _addon_dir not in sys.path:
    sys.path.insert(0, _addon_dir)

try:
    import wf_core  # noqa: F401  (used by sub-modules)
    _WF_CORE_OK = True
except ImportError as _e:
    _WF_CORE_OK = False
    _WF_CORE_ERROR = str(_e)

# ---------------------------------------------------------------------------
# Sub-module registration
# ---------------------------------------------------------------------------

import bpy

from . import operators      # noqa: E402
from . import panels         # noqa: E402
from . import export_level   # noqa: E402
from . import debug_bridge   # noqa: E402


class WF_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    repo_root: bpy.props.StringProperty(
        name="Repo Root",
        description="Path to WorldFoundry repo root. Leave blank to auto-detect from .blend location.",
        subtype='DIR_PATH',
        default="",
    )

    debug_host: bpy.props.StringProperty(
        name="Debug Host",
        description="Hostname or IP of the running wf_game instance",
        default="localhost",
    )

    debug_port: bpy.props.IntProperty(
        name="Debug Port",
        description="TCP port for the wf_game debug bridge (--debug-port N)",
        default=7777,
        min=1024,
        max=65535,
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "repo_root")
        layout.separator()
        row = layout.row(align=True)
        row.prop(self, "debug_host")
        row.prop(self, "debug_port")


# Mapping from Blender custom property key → engine "block.field" key.
# Mirrors the engine kPropMap (engine/mutation/kpropmap_generated.inc) — keep in
# sync. Numeric fields push as-is; enum fields (Mobility, MovementClass,
# ModelType) push as their OAD option index (see _coerce_prop_value). The
# unwritable string field common.Script is deliberately excluded (wfmut rejects
# it).
_ENGINE_PROP_KEY: dict[str, str] = {
    "wf_hp":                     "common.hp",
    "wf_NumberOfLocalMailboxes": "common.NumberOfLocalMailboxes",
    "wf_WriteToMailboxOnDeath":  "common.WriteToMailboxOnDeath",
    "wf_Mass":                   "movebloc.Mass",
    "wf_MaxGroundSpeed":         "movebloc.MaxGroundSpeed",
    "wf_RunningAcceleration":    "movebloc.RunningAcceleration",
    "wf_JumpingAcceleration":    "movebloc.JumpingAcceleration",
    "wf_FallingAcceleration":    "movebloc.FallingAcceleration",
    "wf_StepSize":               "movebloc.StepSize",
    "wf_Mobility":               "movebloc.Mobility",
    "wf_MovementClass":          "movebloc.MovementClass",
    "wf_ModelType":              "mesh.ModelType",
    "wf_AnimationMailbox":       "mesh.AnimationMailbox",
    "wf_VisibilityMailbox":      "mesh.VisibilityMailbox",
}


@functools.lru_cache(maxsize=64)
def _enum_items_by_propkey(resolved_schema_path: str) -> dict[str, tuple]:
    """{wf_<field> : (option labels …)} for every Enum field in a schema.

    Keyed on the resolved schema path so the handler doesn't re-parse the schema
    on every depsgraph tick (`_get_schema` is uncached). Schemas are immutable
    files within a session, so caching is safe.
    """
    schema = wf_core.load_schema(resolved_schema_path)
    return {
        operators._prop_key(f.key): tuple(f.enum_items())
        for f in schema.fields()
        if f.kind == "Enum"
    }


def _coerce_prop_value(current, enum_items):
    """Blender property value → number for scene:set_prop, or None to skip.

    Mirrors wf-edit's TranslateField (engine_bridge.cc): prefer a numeric value
    (covers numeric-string enums like MovementClass='17'); otherwise resolve an
    enum label to its option index — `enum_items` comes from the same wf_core
    schema as the panel, so the index equals the engine's enum value. An unknown
    label (stale option) returns None so the caller skips it.
    """
    try:
        return float(current)
    except (TypeError, ValueError):
        pass
    if enum_items and isinstance(current, str):
        try:
            return float(enum_items.index(current))
        except ValueError:
            return None
    return None


def _depsgraph_handler(scene, depsgraph):
    """Push transform/property deltas to the debug bridge on scene update."""
    bridge = debug_bridge.get_bridge()
    if not bridge.connected:
        return
    if not scene.wf_bridge_sync_transforms:
        return
    for update in depsgraph.updates:
        obj = update.id
        if not isinstance(obj, bpy.types.Object):
            continue
        if not obj.get("wf_schema_path"):
            continue
        idx = bridge.name_to_idx.get(obj.name)
        if idx is None:
            continue
        if update.is_updated_transform:
            p = obj.location
            bridge.set_transform(idx, [p.x, p.y, p.z])
        # Enum option lists for this object's schema (cached), so enum-label
        # fields can be translated to their engine index.
        try:
            enum_map = _enum_items_by_propkey(
                operators._resolve_schema_path(obj["wf_schema_path"]))
        except Exception:
            enum_map = {}
        # Detect WF property changes by comparing against per-object snapshot.
        snap = bridge.prop_snapshots.setdefault(obj.name, {})
        for prop_key, engine_key in _ENGINE_PROP_KEY.items():
            current = obj.get(prop_key)
            if current is None:
                continue
            if snap.get(prop_key) != current:
                snap[prop_key] = current
                value = _coerce_prop_value(current, enum_map.get(prop_key))
                if value is None:
                    # Unresolvable (non-numeric non-enum, or stale enum label).
                    # Snapshot is updated so we don't retry every depsgraph tick.
                    continue
                bridge.set_prop(idx, engine_key, value)


def register():
    if not _WF_CORE_OK:
        def draw_error(self, context):
            self.layout.label(
                text=f"wf_core not found — copy wf_core.so into add-on folder: {_WF_CORE_ERROR}",
                icon='ERROR',
            )
        bpy.app.timers.register(
            lambda: bpy.context.window_manager.popup_menu(draw_error, title="World Foundry"),
            first_interval=0.1,
        )
        return

    bpy.utils.register_class(WF_AddonPreferences)
    bpy.types.Scene.wf_level_name = bpy.props.StringProperty(
        name="Level Name",
        description="Level directory name under wflevels/ (defaults to .blend filename stem)",
        default="",
    )
    bpy.types.Scene.wf_bridge_sync_transforms = bpy.props.BoolProperty(
        name="Sync Transforms",
        description="Send object moves to the running engine via the debug bridge",
        default=True,
    )
    bpy.types.Scene.wf_watch_mailbox_idx = bpy.props.IntProperty(
        name="Mailbox Index",
        description="Mailbox number to watch (2000-2099 local user, 3000+ local system)",
        default=2000,
        min=0,
        max=9999,
    )
    operators.register()
    panels.register()
    export_level.register()
    bpy.app.handlers.depsgraph_update_post.append(_depsgraph_handler)


def unregister():
    if _WF_CORE_OK:
        if _depsgraph_handler in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.remove(_depsgraph_handler)
        export_level.unregister()
        panels.unregister()
        operators.unregister()
        del bpy.types.Scene.wf_watch_mailbox_idx
        del bpy.types.Scene.wf_bridge_sync_transforms
        del bpy.types.Scene.wf_level_name
        bpy.utils.unregister_class(WF_AddonPreferences)
        debug_bridge.get_bridge().disconnect()
