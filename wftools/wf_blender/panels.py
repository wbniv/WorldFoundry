"""
World Foundry property panel — dynamic, driven by Rust schema descriptors.

Section rendering
-----------------
PropertySheet → collapsible section (TRIA_DOWN / TRIA_RIGHT toggle).
               Fields up to the next PropertySheet are shown/hidden together.
GroupStart    → non-collapsible box within the current section.
GroupStop     → closes the GroupStart box.
"""

import os
import bpy
import wf_core
from . import debug_bridge as _db_mod
from .operators import (
    SCHEMA_PATH_KEY, SECTION_OPEN_PREFIX,
    _prop_key, _section_key, _get_schema, _seed_defaults,
    _resolve_schema_path,
)


class WF_PT_attributes(bpy.types.Panel):
    bl_label       = "World Foundry"
    bl_idname      = "WF_PT_attributes"
    bl_space_type  = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context     = 'object'

    def draw(self, context):
        layout = self.layout
        obj    = context.active_object
        if obj is None:
            return

        schema_path = obj.get(SCHEMA_PATH_KEY)

        # ── header row ────────────────────────────────────────
        row = layout.row(align=True)
        if schema_path:
            resolved = _resolve_schema_path(schema_path)
            try:
                schema = wf_core.load_schema(resolved)
            except Exception as e:
                row.label(text=f"Schema error: {e}", icon='ERROR')
                row.operator("wf.attach_schema", text="", icon='FILE_FOLDER')
                return
            row.label(text=schema.name, icon='OBJECT_DATA')
        else:
            row.label(text="No schema attached", icon='QUESTION')

        row.operator("wf.attach_schema", text="", icon='FILE_FOLDER')
        row.operator("wf.detach_schema", text="", icon='X')

        if not schema_path:
            return

        # Show the stored path so the user can verify it persisted correctly.
        path_row = layout.row()
        path_row.label(text=resolved, icon='FILE')

        # ── field loop ────────────────────────────────────────
        # State:
        #   section_open  — whether the current PropertySheet is expanded
        #   section_layout — the column inside the section box (or None = top-level)
        #   group_box      — inner box for a GroupStart (None when not inside one)

        section_open   = True   # fields before any PropertySheet are always shown
        section_layout = layout
        group_box      = None

        for field in schema.fields():
            kind = field.kind

            # ── Section (PropertySheet) — collapsible rollup ──
            if kind == "Section":
                sk      = _section_key(field.key)
                is_open = bool(obj.get(sk, True))

                # Always draw at the root layout, not inside any group box
                group_box = None

                box = layout.box()
                row = box.row(align=True)
                icon = 'TRIA_DOWN' if is_open else 'TRIA_RIGHT'
                op = row.operator(
                    "wf.toggle_section",
                    text=field.label,
                    icon=icon,
                    emboss=False,
                )
                op.section_key = sk

                section_open   = is_open
                section_layout = box.column() if is_open else None
                continue

            # ── GroupStart — non-collapsible sub-box ──────────
            if kind == "Group":
                if section_open and section_layout is not None:
                    group_box = section_layout.box()
                    group_box.label(text=field.label, icon='DOWNARROW_HLT')
                continue

            # ── GroupEnd — close sub-box ──────────────────────
            if kind == "GroupEnd":
                group_box = None
                continue

            # ── Skip / hidden fields ──────────────────────────
            if kind == "Skip" or field.show_as == 6:
                continue

            # If section is collapsed, don't draw any fields
            if not section_open or section_layout is None:
                continue

            # Choose target: inside group box or direct in section
            target    = group_box if group_box is not None else section_layout
            prop_key  = _prop_key(field.key)

            if prop_key not in obj:
                target.label(text=f"{field.label}: (not set)", icon='ERROR')
                continue

            self._draw_field(target, obj, field, prop_key)

        # ── footer ────────────────────────────────────────────
        layout.separator()
        row = layout.row(align=True)
        row.operator("wf.validate",       text="Validate",        icon='CHECKMARK')

        row = layout.row(align=True)
        row.operator("wf.export_iff_txt", text="Export .iff.txt", icon='EXPORT')
        row.operator("wf.import_iff_txt", text="Import .iff.txt", icon='IMPORT')

        row = layout.row(align=True)
        row.operator("wf.export_iff",     text="Export .iff",     icon='EXPORT')
        row.operator("wf.import_iff",     text="Import .iff",     icon='IMPORT')

    @staticmethod
    def _draw_field(layout, obj, field, prop_key):
        kind    = field.kind
        show_as = field.show_as

        if kind == "ObjRef":
            # Searchable object picker.  prop_search with a custom string ID
            # property lets the user type or select from all scene objects.
            row = layout.row(align=True)
            row.prop_search(obj, f'["{prop_key}"]', bpy.data, "objects",
                            text=field.label)
            # Warn if the named object doesn't exist in the scene.
            name = obj.get(prop_key, "")
            if name and name not in bpy.data.objects:
                row.label(text="", icon='ERROR')

        elif kind == "Bool":
            is_on = bool(obj.get(prop_key, 0))
            row = layout.row()
            row.label(text=field.label + ":")
            op = row.operator(
                "wf.toggle_bool",
                text="",
                icon='CHECKBOX_HLT' if is_on else 'CHECKBOX_DEHLT',
                depress=is_on,
            )
            op.field_key = field.key

        elif kind == "FileRef":
            # Text field + file-browser button.
            row = layout.row(align=True)
            row.prop(obj, f'["{prop_key}"]', text=field.label)
            op = row.operator("wf.pick_file", text="", icon='FILE_FOLDER')
            op.field_key   = field.key
            op.filter_glob = field.file_filter or "*.iff"

        elif kind == "Int" and show_as == 7:
            # Packed 0x00RRGGBB color — show hex swatch + picker button
            packed = int(obj.get(prop_key, 0))
            row = layout.row(align=True)
            row.label(text=field.label + ":")
            op = row.operator(
                "wf.pick_color",
                text=f"#{packed:06X}",
                icon='COLOR',
            )
            op.field_key = field.key

        elif kind == "Annotation":
            layout.prop(obj, f'["{prop_key}"]', text=field.label)

        elif kind in ("Int", "Float", "Str"):
            layout.prop(obj, f'["{prop_key}"]', text=field.label)

        elif kind == "Enum":
            items   = field.enum_items()
            current = obj.get(prop_key, "")

            if show_as == 8 and len(items) == 2:
                # Checkbox-style toggle: label left, icon button right
                is_true = (current == items[1])
                row = layout.row()
                row.label(text=field.label + ":")
                op = row.operator(
                    "wf.set_enum",
                    text="",
                    icon='CHECKBOX_HLT' if is_true else 'CHECKBOX_DEHLT',
                    depress=is_true,
                )
                op.field_key  = field.key
                op.item_label = items[0] if is_true else items[1]

            elif show_as in (4, 5) and len(items) > 3:
                # Dropmenu / radiobuttons with 4+ items → 2 per row
                layout.label(text=field.label + ":")
                grid = layout.grid_flow(columns=2, align=True)
                for item in items:
                    op = grid.operator(
                        "wf.set_enum",
                        text=item,
                        depress=(item == current),
                    )
                    op.field_key  = field.key
                    op.item_label = item
                # ScriptLanguage gets an autodetect hint button below the grid
                if field.key == "ScriptLanguage":
                    layout.operator(
                        "wf.detect_script_language",
                        text="Detect from script text",
                        icon='SHADERFX',
                    )

            else:
                # ≤4 items or unlisted show_as: horizontal button row
                row = layout.row(align=True)
                row.label(text=field.label + ":")
                sub = row.row(align=True)
                for item in items:
                    op = sub.operator(
                        "wf.set_enum",
                        text=item,
                        depress=(item == current),
                    )
                    op.field_key  = field.key
                    op.item_label = item


# ── WF_PT_level ───────────────────────────────────────────────────────────────

class WF_PT_level(bpy.types.Panel):
    """Scene-level panel for importing / exporting a WF level."""
    bl_label       = "World Foundry Level"
    bl_idname      = "WF_PT_level"
    bl_space_type  = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context     = 'scene'

    def draw(self, context):
        layout = self.layout
        layout.operator("wf.import_level", icon='IMPORT')
        layout.operator("wf.export_level", icon='EXPORT')
        layout.separator()
        scene = context.scene
        layout.prop(scene, "wf_level_name", text="Level Name")
        layout.operator("wf.run_level", icon='PLAY')


# ── WF_PT_live_bridge ─────────────────────────────────────────────────────────

class WF_PT_live_bridge(bpy.types.Panel):
    """Live debug bridge — connects Blender to a running wf_game instance."""
    bl_label       = "WF Live Bridge"
    bl_idname      = "WF_PT_live_bridge"
    bl_space_type  = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context     = 'scene'

    def draw(self, context):
        layout = self.layout
        prefs = context.preferences.addons.get(__package__)
        prefs = prefs.preferences if prefs else None

        bridge = _db_mod.get_bridge()

        if bridge.connected:
            # Status row
            row = layout.row(align=True)
            icon = 'PAUSE' if bridge.is_paused else 'RADIOBUT_ON'
            label = "⏸ PAUSED" if bridge.is_paused else "Connected"
            row.label(text=label, icon=icon)
            host = getattr(prefs, 'debug_host', 'localhost') if prefs else 'localhost'
            port = getattr(prefs, 'debug_port', 7777)        if prefs else 7777
            row.label(text=f"{host}:{port}")
            row.operator("wf.bridge_disconnect", text="", icon='X')

            if bridge.frame_n:
                layout.label(text=f"Frame {bridge.frame_n}  |  {bridge.frame_dt_ms:.1f} ms")

            # Pause / step / resume controls
            row2 = layout.row(align=True)
            if bridge.is_paused:
                row2.operator("wf.bridge_step",   text="Step",   icon='FRAME_NEXT')
                row2.operator("wf.bridge_resume",  text="Resume", icon='PLAY')
            else:
                row2.operator("wf.bridge_pause",   text="Pause",  icon='PAUSE')

            # Object picker
            row3 = layout.row(align=True)
            row3.operator("wf.bridge_pick", text="Pick Object", icon='RESTRICT_SELECT_OFF')
            if bridge.last_picked_idx >= 0:
                name = bridge.idx_to_name.get(bridge.last_picked_idx, f"idx {bridge.last_picked_idx}")
                row3.label(text=name)

            # Undo / revert (Phase 3)
            n = len(bridge.change_log)
            if n > 0:
                layout.separator()
                row4 = layout.row(align=True)
                row4.label(text=f"Changes: {n}", icon='TRACKING_BACKWARDS')
                row4.operator("wf.bridge_undo",       text="↩ Undo",      icon='LOOP_BACK')
                row4.operator("wf.bridge_revert_all", text="✕ Revert all", icon='X')
        else:
            row = layout.row(align=True)
            row.label(text="Not connected", icon='RADIOBUT_OFF')
            if bridge.error:
                layout.label(text=bridge.error, icon='ERROR')
            if prefs:
                layout.prop(prefs, "debug_host", text="Host")
                layout.prop(prefs, "debug_port", text="Port")
            row2 = layout.row()
            row2.operator("wf.bridge_connect", text="Connect", icon='LINKED')

        layout.separator()
        layout.prop(context.scene, "wf_bridge_sync_transforms", text="Sync transforms (10 Hz)")


# ── registration ──────────────────────────────────────────────────────────────

_CLASSES = [WF_PT_attributes, WF_PT_level, WF_PT_live_bridge]


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
