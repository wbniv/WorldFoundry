"""
World Foundry operators:

  WF_OT_attach_schema   — file picker → load OAD, store path, seed defaults
  WF_OT_detach_schema   — remove WF custom properties from object
  WF_OT_set_enum        — set an enum field by item label (used by panel dropdown)
  WF_OT_validate        — range-check all values via Rust
  WF_OT_export_iff_txt  — gather values and write .iff.txt via Rust
  WF_OT_import_iff_txt  — read .iff.txt and populate object properties
  WF_OT_export_iff      — gather values and write binary .iff via Rust
  WF_OT_import_iff      — read binary .iff and populate object properties

Storage convention
------------------
  obj["wf_schema_path"]   — absolute path to the .oad file
  obj["wf_<key>"]         — field value:
    Int   → int
    Float → float (display value, e.g. 50.0; NOT the raw fixed-point int)
    Enum  → string label (e.g. "Physics")
    Str   → string
"""

import bpy
from bpy.props import FloatVectorProperty, StringProperty
from bpy_extras.io_utils import ExportHelper, ImportHelper
import wf_core

# ── constants ─────────────────────────────────────────────────────────────────

SCHEMA_PATH_KEY = "wf_schema_path"


def _prop_key(field_key: str) -> str:
    """Custom property key for a field value."""
    return f"wf_{field_key}"


def _resolve_schema_path(raw: str) -> str:
    """Resolve a stored schema path (possibly //-relative) to an absolute path."""
    return bpy.path.abspath(raw)


def _get_schema(obj):
    """Return a loaded wf_core.Schema or None."""
    path = obj.get(SCHEMA_PATH_KEY)
    if not path:
        return None
    try:
        return wf_core.load_schema(_resolve_schema_path(path))
    except Exception:
        return None


def _collect_values(obj, schema) -> dict:
    """Read all wf_ custom properties into a plain dict (display values)."""
    values = {}
    for field in schema.visible_fields():
        key = _prop_key(field.key)
        val = obj.get(key)
        if val is not None:
            values[field.key] = val
    return values


SECTION_OPEN_PREFIX = "wf__open_"


def _section_key(field_key: str) -> str:
    """Custom property key tracking whether a Section is expanded."""
    return f"{SECTION_OPEN_PREFIX}{field_key}"


def _seed_defaults(obj, schema):
    """Populate default values for all fields not yet set on obj."""
    for field in schema.fields():
        # Section open/closed state (default_raw: 1=open, 0=closed)
        if field.kind == "Section":
            sk = _section_key(field.key)
            if sk not in obj:
                obj[sk] = bool(field.default_raw)
            continue

        # Structural markers — no value to seed
        if field.kind in ("Group", "GroupEnd", "Skip"):
            continue

        # Annotation fields seed as empty string
        if field.kind == "Annotation":
            key = _prop_key(field.key)
            if key not in obj:
                obj[key] = ""
            continue

        # Skip hidden fields
        if field.show_as == 6:
            continue

        key = _prop_key(field.key)
        if key in obj:
            continue
        if field.kind == "Float":
            obj[key] = field.default_display
        elif field.kind == "Bool":
            obj[key] = int(bool(field.default_raw))
        elif field.kind == "Enum":
            items = field.enum_items()
            idx = field.default_raw
            obj[key] = items[idx] if 0 <= idx < len(items) else (items[0] if items else "")
        elif field.kind in ("Str", "ObjRef", "FileRef"):
            obj[key] = ""
        else:
            obj[key] = field.default_raw

        # Register UI properties (soft min/max, description)
        ui = obj.id_properties_ui(key)
        if field.kind == "Float":
            ui.update(
                min=field.min_display,
                max=field.max_display,
                soft_min=field.min_display,
                soft_max=field.max_display,
                description=field.help or field.label,
            )
        elif field.kind == "Int":
            ui.update(
                min=int(field.min_raw),
                max=int(field.max_raw),
                soft_min=int(field.min_raw),
                soft_max=int(field.max_raw),
                description=field.help or field.label,
            )


# ── WF_OT_attach_schema ───────────────────────────────────────────────────────

class WF_OT_attach_schema(bpy.types.Operator):
    """Load an OAD schema and attach it to the active object"""
    bl_idname  = "wf.attach_schema"
    bl_label   = "Attach Schema"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default="*.oad", options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        obj = context.active_object
        if obj is None:
            self.report({'ERROR'}, "No active object")
            return {'CANCELLED'}

        try:
            schema = wf_core.load_schema(self.filepath)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to load schema: {e}")
            return {'CANCELLED'}

        # Store a //-relative path when the blend file has been saved so the
        # association survives the blend file moving to a new location.
        # Fall back to absolute when the blend file is still unsaved.
        stored_path = (
            bpy.path.relpath(self.filepath)
            if bpy.data.is_saved
            else self.filepath
        )
        obj[SCHEMA_PATH_KEY] = stored_path
        _seed_defaults(obj, schema)

        visible = list(schema.visible_fields())
        self.report({'INFO'}, f"Attached '{schema.name}' — {len(visible)} fields")
        return {'FINISHED'}


# ── WF_OT_detach_schema ───────────────────────────────────────────────────────

class WF_OT_detach_schema(bpy.types.Operator):
    """Remove all World Foundry custom properties from the active object"""
    bl_idname  = "wf.detach_schema"
    bl_label   = "Detach Schema"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if obj is None:
            self.report({'ERROR'}, "No active object")
            return {'CANCELLED'}
        keys = [k for k in obj.keys() if k.startswith("wf_")]
        for k in keys:
            del obj[k]
        self.report({'INFO'}, f"Removed {len(keys)} World Foundry properties")
        return {'FINISHED'}


# ── WF_OT_toggle_section ─────────────────────────────────────────────────────

class WF_OT_toggle_section(bpy.types.Operator):
    """Expand or collapse a property-sheet section"""
    bl_idname  = "wf.toggle_section"
    bl_label   = "Toggle Section"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    section_key: StringProperty(options={'HIDDEN'})

    def execute(self, context):
        obj = context.active_object
        if obj is None:
            return {'CANCELLED'}
        current = bool(obj.get(self.section_key, True))
        obj[self.section_key] = not current
        for area in context.screen.areas:
            if area.type == 'PROPERTIES':
                area.tag_redraw()
        return {'FINISHED'}


# ── WF_OT_set_enum ────────────────────────────────────────────────────────────

class WF_OT_set_enum(bpy.types.Operator):
    """Set an enum field to a specific item label"""
    bl_idname  = "wf.set_enum"
    bl_label   = "Set Enum Value"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    field_key:  StringProperty(options={'HIDDEN'})
    item_label: StringProperty(options={'HIDDEN'})

    def execute(self, context):
        obj = context.active_object
        if obj is None:
            return {'CANCELLED'}
        obj[_prop_key(self.field_key)] = self.item_label
        # Force panel redraw
        for area in context.screen.areas:
            if area.type == 'PROPERTIES':
                area.tag_redraw()
        return {'FINISHED'}


# ── WF_OT_validate ────────────────────────────────────────────────────────────

class WF_OT_validate(bpy.types.Operator):
    """Validate attribute values against the attached schema"""
    bl_idname  = "wf.validate"
    bl_label   = "Validate"
    bl_options = {'REGISTER'}

    def execute(self, context):
        obj = context.active_object
        if obj is None:
            self.report({'ERROR'}, "No active object")
            return {'CANCELLED'}
        schema = _get_schema(obj)
        if schema is None:
            self.report({'ERROR'}, "No schema attached")
            return {'CANCELLED'}

        values = _collect_values(obj, schema)
        issues = wf_core.validate(schema, values)

        if not issues:
            self.report({'INFO'}, "Validation passed — no issues")
        else:
            for issue in issues:
                level = 'ERROR' if issue.is_error else 'WARNING'
                self.report({level}, f"{issue.key}: {issue.message}")

        return {'FINISHED'}


# ── WF_OT_export_iff_txt ──────────────────────────────────────────────────────

class WF_OT_export_iff_txt(bpy.types.Operator, ExportHelper):
    """Export object attributes as .iff.txt"""
    bl_idname  = "wf.export_iff_txt"
    bl_label   = "Export .iff.txt"
    bl_options = {'REGISTER'}

    filename_ext = ".iff.txt"
    filter_glob: StringProperty(default="*.iff.txt", options={'HIDDEN'})

    def execute(self, context):
        obj = context.active_object
        if obj is None:
            self.report({'ERROR'}, "No active object")
            return {'CANCELLED'}
        schema = _get_schema(obj)
        if schema is None:
            self.report({'ERROR'}, "No schema attached")
            return {'CANCELLED'}

        values = _collect_values(obj, schema)

        # Reject on validation errors
        issues = wf_core.validate(schema, values)
        errors = [i for i in issues if i.is_error]
        if errors:
            for e in errors:
                self.report({'ERROR'}, f"{e.key}: {e.message}")
            return {'CANCELLED'}

        text = wf_core.export_iff_txt(schema, values)
        with open(self.filepath, 'w', encoding='utf-8') as f:
            f.write(text)
        self.report({'INFO'}, f"Exported to {self.filepath}")
        return {'FINISHED'}


# ── WF_OT_import_iff_txt ─────────────────────────────────────────────────────

class WF_OT_import_iff_txt(bpy.types.Operator, ImportHelper):
    """Import attribute values from a .iff.txt file into this object"""
    bl_idname  = "wf.import_iff_txt"
    bl_label   = "Import .iff.txt"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".iff.txt"
    filter_glob: StringProperty(default="*.iff.txt", options={'HIDDEN'})

    def execute(self, context):
        obj = context.active_object
        if obj is None:
            self.report({'ERROR'}, "No active object")
            return {'CANCELLED'}
        schema = _get_schema(obj)
        if schema is None:
            self.report({'ERROR'}, "No schema attached — attach a schema first")
            return {'CANCELLED'}

        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                text = f.read()
        except OSError as e:
            self.report({'ERROR'}, f"Could not read file: {e}")
            return {'CANCELLED'}

        try:
            imported = wf_core.import_iff_txt(schema, text)
        except Exception as e:
            self.report({'ERROR'}, f"Parse error: {e}")
            return {'CANCELLED'}

        # Seed defaults first so every field exists, then overwrite with
        # imported values.
        _seed_defaults(obj, schema)
        count = 0
        for key, val in imported.items():
            prop_key = _prop_key(key)
            if prop_key in obj:
                obj[prop_key] = val
                count += 1

        self.report({'INFO'}, f"Imported {count} fields from {self.filepath}")
        return {'FINISHED'}


# ── WF_OT_export_iff ─────────────────────────────────────────────────────────

class WF_OT_export_iff(bpy.types.Operator, ExportHelper):
    """Export object attributes as binary .iff"""
    bl_idname  = "wf.export_iff"
    bl_label   = "Export .iff"
    bl_options = {'REGISTER'}

    filename_ext = ".iff"
    filter_glob: StringProperty(default="*.iff", options={'HIDDEN'})

    def execute(self, context):
        obj = context.active_object
        if obj is None:
            self.report({'ERROR'}, "No active object")
            return {'CANCELLED'}
        schema = _get_schema(obj)
        if schema is None:
            self.report({'ERROR'}, "No schema attached")
            return {'CANCELLED'}

        values = _collect_values(obj, schema)

        # Reject on validation errors
        issues = wf_core.validate(schema, values)
        errors = [i for i in issues if i.is_error]
        if errors:
            for e in errors:
                self.report({'ERROR'}, f"{e.key}: {e.message}")
            return {'CANCELLED'}

        data = wf_core.export_iff(schema, values)
        with open(self.filepath, 'wb') as f:
            f.write(data)
        self.report({'INFO'}, f"Exported {len(data)} bytes to {self.filepath}")
        return {'FINISHED'}


# ── WF_OT_import_iff ─────────────────────────────────────────────────────────

class WF_OT_import_iff(bpy.types.Operator, ImportHelper):
    """Import attribute values from a binary .iff file into this object"""
    bl_idname  = "wf.import_iff"
    bl_label   = "Import .iff"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".iff"
    filter_glob: StringProperty(default="*.iff", options={'HIDDEN'})

    def execute(self, context):
        obj = context.active_object
        if obj is None:
            self.report({'ERROR'}, "No active object")
            return {'CANCELLED'}
        schema = _get_schema(obj)
        if schema is None:
            self.report({'ERROR'}, "No schema attached — attach a schema first")
            return {'CANCELLED'}

        try:
            with open(self.filepath, 'rb') as f:
                data = f.read()
        except OSError as e:
            self.report({'ERROR'}, f"Could not read file: {e}")
            return {'CANCELLED'}

        try:
            imported = wf_core.import_iff(schema, bytes(data))
        except Exception as e:
            self.report({'ERROR'}, f"Parse error: {e}")
            return {'CANCELLED'}

        # Seed defaults first so every field exists, then overwrite with
        # imported values.
        _seed_defaults(obj, schema)
        count = 0
        for key, val in imported.items():
            prop_key = _prop_key(key)
            if prop_key in obj:
                obj[prop_key] = val
                count += 1

        self.report({'INFO'}, f"Imported {count} fields from {self.filepath}")
        return {'FINISHED'}


# ── WF_OT_toggle_bool ────────────────────────────────────────────────────────

class WF_OT_toggle_bool(bpy.types.Operator):
    """Toggle a Bool (levelcon flag) field between 0 and 1"""
    bl_idname  = "wf.toggle_bool"
    bl_label   = "Toggle Bool"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    field_key: StringProperty(options={'HIDDEN'})

    def execute(self, context):
        obj = context.active_object
        if obj is None:
            return {'CANCELLED'}
        pk = _prop_key(self.field_key)
        obj[pk] = 0 if obj.get(pk, 0) else 1
        for area in context.screen.areas:
            if area.type == 'PROPERTIES':
                area.tag_redraw()
        return {'FINISHED'}


# ── WF_OT_pick_file ──────────────────────────────────────────────────────────

class WF_OT_pick_file(bpy.types.Operator):
    """Browse for a file and store its path in a FileRef field"""
    bl_idname  = "wf.pick_file"
    bl_label   = "Pick File"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    field_key:   StringProperty(options={'HIDDEN'})
    filter_glob: StringProperty(default="*.iff", options={'HIDDEN'})
    filepath:    StringProperty(subtype='FILE_PATH')

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        obj = context.active_object
        if obj is None:
            return {'CANCELLED'}
        prop_key = _prop_key(self.field_key)
        # Store //-relative path when the blend file is saved.
        stored = (
            bpy.path.relpath(self.filepath)
            if bpy.data.is_saved else self.filepath
        )
        obj[prop_key] = stored
        for area in context.screen.areas:
            if area.type == 'PROPERTIES':
                area.tag_redraw()
        return {'FINISHED'}


# ── WF_OT_pick_color ─────────────────────────────────────────────────────────

class WF_OT_pick_color(bpy.types.Operator):
    """Open a color picker for a packed-RGB integer field (show_as=7)"""
    bl_idname  = "wf.pick_color"
    bl_label   = "Pick Color"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    field_key: StringProperty(options={'HIDDEN'})
    color: FloatVectorProperty(
        name="Color",
        subtype='COLOR',
        size=3,
        min=0.0, max=1.0,
        default=(1.0, 1.0, 1.0),
    )

    def invoke(self, context, event):
        obj = context.active_object
        if obj is None:
            return {'CANCELLED'}
        packed = int(obj.get(_prop_key(self.field_key), 0))
        self.color = (
            ((packed >> 16) & 0xFF) / 255.0,
            ((packed >>  8) & 0xFF) / 255.0,
            ( packed        & 0xFF) / 255.0,
        )
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, "color", text="")

    def execute(self, context):
        obj = context.active_object
        if obj is None:
            return {'CANCELLED'}
        r = int(round(self.color[0] * 255))
        g = int(round(self.color[1] * 255))
        b = int(round(self.color[2] * 255))
        obj[_prop_key(self.field_key)] = (r << 16) | (g << 8) | b
        for area in context.screen.areas:
            if area.type == 'PROPERTIES':
                area.tag_redraw()
        return {'FINISHED'}


# ── registration ──────────────────────────────────────────────────────────────

def _detect_script_language(script_text: str) -> str:
    """
    Heuristic scan of script text → ScriptLanguage label.

    Checks for unambiguous syntactic markers anywhere in the body.
    Returns one of the enum strings from common.oad ScriptLanguage field.
    Does NOT look at leading sigils — those are legacy and may be stripped.
    """
    t = script_text

    # WebAssembly: base64-only content or WAT s-expression opener
    import re
    stripped = t.strip()
    if stripped.startswith('(module') or re.fullmatch(r'[A-Za-z0-9+/=\s]+', stripped):
        return "WebAssembly"

    # Fennel: Lisp s-expression keywords
    if any(kw in t for kw in ('(defn ', '(defn\t', '(let [', '(fn ', '(var ', '(local ')):
        return "Fennel"

    # Wren: class-based OO keywords or Fiber
    if any(kw in t for kw in ('class ', 'Fiber.', '.new()', 'import "')):
        return "Wren"

    # Forth: colon definitions, stack comments, typical Forth words
    if any(kw in t for kw in (': ', 'VARIABLE ', 'CREATE ', 'CONSTANT ', ': ?')):
        return "Forth"

    # JavaScript: ES keywords not valid in Lua
    if any(kw in t for kw in ('function ', 'const ', 'let ', '=>', 'var ', 'console.')):
        return "JavaScript"

    return "Lua"


class WF_OT_detect_script_language(bpy.types.Operator):
    """Scan the object's Script text and pre-fill ScriptLanguage."""
    bl_idname = "wf.detect_script_language"
    bl_label  = "Detect Script Language"

    def execute(self, context):
        obj = context.active_object
        if obj is None:
            self.report({'WARNING'}, "No active object")
            return {'CANCELLED'}

        script_key   = _prop_key("Script")
        language_key = _prop_key("ScriptLanguage")

        script_text = obj.get(script_key, "")
        if not script_text:
            self.report({'INFO'}, "No script text on object — defaulting to Lua")
            obj[language_key] = "Lua"
            return {'FINISHED'}

        lang = _detect_script_language(str(script_text))
        obj[language_key] = lang
        self.report({'INFO'}, f"Detected: {lang}")
        return {'FINISHED'}


# ── repo-root detection ───────────────────────────────────────────────────────

def _find_repo_root(start: str) -> str | None:
    """Walk up from start looking for Taskfile.yml; return its directory or None."""
    import os
    d = os.path.abspath(start)
    for _ in range(10):
        if os.path.isfile(os.path.join(d, "Taskfile.yml")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


# ── WF_OT_run_level ───────────────────────────────────────────────────────────

class WF_OT_run_level(bpy.types.Operator):
    """Export current scene, build level binary, and launch wf_game"""
    bl_idname  = "wf.run_level"
    bl_label   = "Run in Engine"
    bl_options = {'REGISTER'}

    def execute(self, context):
        import subprocess
        import os
        from pathlib import Path
        from . import export_level as _el

        blend_path = bpy.data.filepath
        if not blend_path:
            self.report({'ERROR'}, "Save the .blend file first")
            return {'CANCELLED'}

        scene      = context.scene
        level_name = scene.wf_level_name or Path(blend_path).stem

        prefs     = context.preferences.addons[__package__].preferences
        repo_root = prefs.repo_root or _find_repo_root(os.path.dirname(blend_path))
        if not repo_root:
            self.report({'ERROR'},
                "Cannot find repo root (Taskfile.yml). "
                "Set it in Edit > Preferences > Add-ons > World Foundry.")
            return {'CANCELLED'}

        lev_path  = os.path.join(repo_root, "wflevels", level_name, f"{level_name}.lev")
        iff_path  = os.path.join(repo_root, "wflevels", f"{level_name}.iff")
        build_sh  = os.path.join(repo_root, "wftools", "wf_blender", "build_level_binary.sh")
        game_bin  = os.path.join(repo_root, "engine", "wf_game")
        libs_path = os.path.join(repo_root, "engine", "libs")

        for path, label in [(build_sh, "build_level_binary.sh"), (game_bin, "engine/wf_game")]:
            if not os.path.isfile(path):
                self.report({'ERROR'}, f"Not found: {label} ({path})")
                return {'CANCELLED'}

        wm = context.window_manager
        wm.progress_begin(0, 3)

        self.report({'INFO'}, f"[1/3] Exporting {level_name}.lev ...")
        wm.progress_update(1)
        ok, msg = _el.export_scene_to_lev(context, lev_path)
        if not ok:
            self.report({'ERROR'}, f"Export failed: {msg}")
            wm.progress_end()
            return {'CANCELLED'}

        # Capture the authoritative actor-index map for the live bridge: the
        # objects just written define the engine's 1-based actor indices.
        from . import debug_bridge as _db
        _db.get_bridge().update_index_map(_el.scene_index_map(context))

        self.report({'INFO'}, f"[2/3] Building {level_name}.iff ...")
        wm.progress_update(2)
        result = subprocess.run(
            ["bash", build_sh, level_name],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            self.report({'ERROR'}, f"Build failed: {result.stderr[-400:]}")
            wm.progress_end()
            return {'CANCELLED'}

        self.report({'INFO'}, f"[3/3] Launching wf_game ...")
        wm.progress_update(3)
        env = os.environ.copy()
        env["LD_LIBRARY_PATH"] = libs_path
        env.setdefault("DISPLAY", ":0")
        debug_port = int(getattr(prefs, "debug_port", 7777))
        subprocess.Popen(
            [game_bin, f"-L{iff_path}", "--debug-port", str(debug_port)],
            cwd=repo_root,
            env=env,
            start_new_session=True,
        )

        wm.progress_end()
        self.report(
            {'INFO'},
            f"Launched {level_name} (debug bridge :{debug_port}) — "
            f"click Connect to push live edits",
        )
        return {'FINISHED'}


class WF_OT_bridge_connect(bpy.types.Operator):
    """Connect to a running wf_game debug bridge"""
    bl_idname = "wf.bridge_connect"
    bl_label  = "Connect to Engine"

    def execute(self, context):
        from . import debug_bridge as _db
        prefs = context.preferences.addons.get(__package__)
        prefs = prefs.preferences if prefs else None
        host = getattr(prefs, 'debug_host', 'localhost') if prefs else 'localhost'
        port = int(getattr(prefs, 'debug_port', 7777))    if prefs else 7777
        bridge = _db.get_bridge()
        bridge.connect(host, port)
        if bridge.connected:
            # Rebuild the name↔idx map from the current scene so connecting to an
            # already-running engine (without re-running this session) still
            # resolves object→actor — valid as long as the schema-bearing object
            # set is unchanged since the level was exported.
            from . import export_level as _el
            bridge.update_index_map(_el.scene_index_map(context))
            self.report({'INFO'}, f"Connected to {host}:{port}")
        else:
            self.report({'WARNING'}, f"Connection failed: {bridge.error}")
        return {'FINISHED'}


class WF_OT_bridge_disconnect(bpy.types.Operator):
    """Disconnect from the wf_game debug bridge"""
    bl_idname = "wf.bridge_disconnect"
    bl_label  = "Disconnect from Engine"

    def execute(self, context):
        from . import debug_bridge as _db
        _db.get_bridge().disconnect()
        self.report({'INFO'}, "Disconnected")
        return {'FINISHED'}


class WF_OT_bridge_pause(bpy.types.Operator):
    """Pause the running wf_game simulation"""
    bl_idname = "wf.bridge_pause"
    bl_label  = "Pause"

    def execute(self, context):
        from . import debug_bridge as _db
        _db.get_bridge().pause()
        return {'FINISHED'}


class WF_OT_bridge_resume(bpy.types.Operator):
    """Resume the paused wf_game simulation"""
    bl_idname = "wf.bridge_resume"
    bl_label  = "Resume"

    def execute(self, context):
        from . import debug_bridge as _db
        _db.get_bridge().resume()
        return {'FINISHED'}


class WF_OT_bridge_step(bpy.types.Operator):
    """Step the simulation forward one frame"""
    bl_idname = "wf.bridge_step"
    bl_label  = "Step"

    frames: bpy.props.IntProperty(name="Frames", default=1, min=1)

    def execute(self, context):
        from . import debug_bridge as _db
        _db.get_bridge().step(self.frames)
        return {'FINISHED'}


class WF_OT_bridge_undo(bpy.types.Operator):
    """Undo the last bridge change in the running engine"""
    bl_idname = "wf.bridge_undo"
    bl_label  = "Undo Last Change"

    def execute(self, context):
        from . import debug_bridge as _db
        _db.get_bridge().undo_step()
        return {'FINISHED'}


class WF_OT_bridge_revert_all(bpy.types.Operator):
    """Revert all bridge changes — restore every actor to its pre-session state"""
    bl_idname = "wf.bridge_revert_all"
    bl_label  = "Revert All Changes"

    def execute(self, context):
        from . import debug_bridge as _db
        _db.get_bridge().revert_all()
        return {'FINISHED'}


class WF_OT_bridge_pick(bpy.types.Operator):
    """Click in the 3D viewport to select the closest engine actor"""
    bl_idname   = "wf.bridge_pick"
    bl_label    = "Pick Object"
    bl_options  = {'REGISTER'}

    def modal(self, context, event):
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            region = context.region
            rv3d   = context.region_data
            if region and rv3d:
                from bpy_extras.view3d_utils import region_2d_to_ray_3d
                coord = (event.mouse_region_x, event.mouse_region_y)
                origin, direction = region_2d_to_ray_3d(region, rv3d, coord)
                from . import debug_bridge as _db
                _db.get_bridge().scene_pick(list(origin), list(direction))
            return {'FINISHED'}
        if event.type in {'RIGHTMOUSE', 'ESC'}:
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        if context.area and context.area.type == 'VIEW_3D':
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        self.report({'WARNING'}, "Must be invoked from the 3D viewport")
        return {'CANCELLED'}


class WF_OT_bridge_watch_mailbox(bpy.types.Operator):
    """Start watching a mailbox value in the running engine"""
    bl_idname = "wf.bridge_watch_mailbox"
    bl_label  = "Watch Mailbox"

    actor_idx:   bpy.props.IntProperty()
    mailbox_idx: bpy.props.IntProperty()

    def execute(self, context):
        from . import debug_bridge as _db
        _db.get_bridge().watch_mailbox(self.actor_idx, self.mailbox_idx)
        return {'FINISHED'}


class WF_OT_bridge_unwatch_mailbox(bpy.types.Operator):
    """Stop watching a mailbox value"""
    bl_idname = "wf.bridge_unwatch_mailbox"
    bl_label  = "Unwatch Mailbox"

    actor_idx:   bpy.props.IntProperty()
    mailbox_idx: bpy.props.IntProperty()

    def execute(self, context):
        from . import debug_bridge as _db
        _db.get_bridge().unwatch_mailbox(self.actor_idx, self.mailbox_idx)
        return {'FINISHED'}


_CLASSES = [
    WF_OT_attach_schema,
    WF_OT_detach_schema,
    WF_OT_toggle_section,
    WF_OT_set_enum,
    WF_OT_toggle_bool,
    WF_OT_pick_color,
    WF_OT_pick_file,
    WF_OT_validate,
    WF_OT_detect_script_language,
    WF_OT_export_iff_txt,
    WF_OT_import_iff_txt,
    WF_OT_export_iff,
    WF_OT_import_iff,
    WF_OT_run_level,
    WF_OT_bridge_connect,
    WF_OT_bridge_disconnect,
    WF_OT_bridge_pause,
    WF_OT_bridge_resume,
    WF_OT_bridge_step,
    WF_OT_bridge_pick,
    WF_OT_bridge_undo,
    WF_OT_bridge_revert_all,
    WF_OT_bridge_watch_mailbox,
    WF_OT_bridge_unwatch_mailbox,
]


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
