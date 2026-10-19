# Plan: "Run in Engine" Blender operator

**Status:** OPEN — design documented; the export+build+launch Blender operator is not wired.

## Goal

Add a "Run in Engine" button to the WF Blender addon's scene panel that does:

1. Export the current scene to `.lev` (text IFF)
2. Build the level binary via `build_level_binary.sh` (four-tool Rust chain → `.iff`)
3. Launch `wf_game -L<level>.iff` as a detached process

This collapses three terminal commands into one Blender button and closes 80% of the BGE "Press P" gap.

---

## Context

**Current workflow:**

1. Properties > Scene > Export Level → save `.lev` somewhere
2. `bash wftools/wf_blender/build_level_binary.sh <level-name>` — Rust chain → `.iff`
3. `task run-level -- wflevels/<level-name>.iff` — launches `engine/wf_game`

**Target workflow:**

1. Click "Run in Engine" in Properties > Scene > World Foundry Level panel

---

## Design decisions

**Repo root detection:** Walk up from `bpy.data.filepath` looking for `Taskfile.yml`. If the blend file is not under the repo (e.g., a scratch file), fall back to an addon preference. The scene panel shows the detected/configured root so the user can verify it.

**Level name:** Derived from the `.blend` filename stem by default. Stored as a scene property `wf_level_name` so the user can override it when the blend file has a different name from the level directory (e.g., `snowgoons_v2.blend` → level name `snowgoons`).

**Blocking vs background:** The build step is blocking (`subprocess.run`) — Blender's UI freezes for the few seconds it takes. This is acceptable for a level build. `wf_game` is launched as a detached `subprocess.Popen` so Blender stays open and interactive while the game runs.

**Progress:** Use `context.window_manager.progress_begin/update/end` for the status-bar progress bar and `self.report({'INFO'}, ...)` for step labels.

**Export path:** Call `export_scene_to_lev(context, filepath)` directly (a new module-level helper in `export_level.py`, extracted from `WF_OT_export_level.execute`) rather than invoking `bpy.ops.wf.export_level`, which requires file-browser operator context.

**Output paths (conventional):**

```
wflevels/<level-name>/<level-name>.lev    ← export target
wflevels/<level-name>.iff                 ← build output
engine/wf_game                            ← game binary
engine/libs/                              ← LD_LIBRARY_PATH
```

---

## Implementation

### 1. Scene property + addon preferences (`__init__.py`)

Add a `wf_level_name` scene property and a `WFAddonPreferences` class.

```python
class WFAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    repo_root: bpy.props.StringProperty(
        name="Repo Root",
        description="Path to WorldFoundry repo root. Leave blank to auto-detect from .blend location.",
        subtype='DIR_PATH',
        default="",
    )

    def draw(self, context):
        self.layout.prop(self, "repo_root")
```

In `register()`:
```python
bpy.utils.register_class(WFAddonPreferences)
bpy.types.Scene.wf_level_name = bpy.props.StringProperty(
    name="Level Name",
    description="Level directory name under wflevels/ (defaults to .blend filename stem)",
    default="",
)
```

In `unregister()`:
```python
del bpy.types.Scene.wf_level_name
bpy.utils.unregister_class(WFAddonPreferences)
```

### 2. Repo root detection helper (`operators.py`)

```python
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
```

### 3. Export helper (`export_level.py`)

Extract the core of `WF_OT_export_level.execute` into a standalone function:

```python
def export_scene_to_lev(context, filepath: str) -> tuple[bool, str]:
    """Write the current Blender scene to a .lev text IFF. Returns (ok, message)."""
    import os
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    try:
        # ... (existing export logic from WF_OT_export_level.execute) ...
        return True, f"Exported to {filepath}"
    except Exception as e:
        return False, str(e)
```

`WF_OT_export_level.execute` becomes a thin wrapper calling `export_scene_to_lev`.

### 4. New operator (`operators.py`)

```python
class WF_OT_run_level(bpy.types.Operator):
    """Export current scene, build level binary, and launch wf_game"""
    bl_idname  = "wf.run_level"
    bl_label   = "Run in Engine"
    bl_options = {'REGISTER'}

    def execute(self, context):
        import subprocess, os
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

        # step 1: export
        self.report({'INFO'}, f"[1/3] Exporting {level_name}.lev ...")
        wm.progress_update(1)
        ok, msg = _el.export_scene_to_lev(context, lev_path)
        if not ok:
            self.report({'ERROR'}, f"Export failed: {msg}")
            wm.progress_end()
            return {'CANCELLED'}

        # step 2: build
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

        # step 3: launch
        self.report({'INFO'}, f"[3/3] Launching wf_game ...")
        wm.progress_update(3)
        env = os.environ.copy()
        env["LD_LIBRARY_PATH"] = libs_path
        env.setdefault("DISPLAY", ":0")
        subprocess.Popen(
            [game_bin, f"-L{iff_path}"],
            cwd=repo_root,
            env=env,
            start_new_session=True,
        )

        wm.progress_end()
        self.report({'INFO'}, f"Launched {level_name} — Blender stays open")
        return {'FINISHED'}
```

Add `WF_OT_run_level` to `_CLASSES` in `operators.py`.

### 5. Panel addition (`panels.py`, `WF_PT_level.draw`)

After the existing Import/Export buttons:

```python
layout.separator()
scene = context.scene
layout.prop(scene, "wf_level_name", text="Level Name")
layout.operator("wf.run_level", icon='PLAY')
```

The level name field shows the override (empty = auto from .blend filename). The "Run in Engine" button is one click.

---

## Files Modified

| Action | Path |
|--------|------|
| Modify | `wftools/wf_blender/__init__.py` — add `WFAddonPreferences`, register `wf_level_name` scene prop |
| Modify | `wftools/wf_blender/export_level.py` — extract `export_scene_to_lev()` helper; make `WF_OT_export_level` call it |
| Modify | `wftools/wf_blender/operators.py` — add `_find_repo_root()`, `WF_OT_run_level` |
| Modify | `wftools/wf_blender/panels.py` — add level name field + "Run in Engine" button to `WF_PT_level` |

No new files.

---

## Status: IMPLEMENTED (2026-04-29)

All four files modified as designed. Key implementation notes:

- `WFAddonPreferences` already existed in `__init__.py`; added `repo_root` field to it rather than creating a new class.
- Per-object warnings (`mesh export failed`, `OAD export error`) are silently dropped in `export_scene_to_lev` — they still log to `/tmp/wf_export_errors.log` for the OAD case. The file-browser operator path (`WF_OT_export_level`) is unaffected.
- `WF_OT_run_level` uses `__package__` to look up addon prefs, consistent with Blender's addon preference access pattern.

## Verification

1. Open any saved `.blend` under `wflevels/` (e.g., `wflevels/snowgoons/snowgoons.blend`)
2. Properties > Scene > World Foundry Level — "Run in Engine" button and "Level Name" field appear
3. Click "Run in Engine" — progress bar advances 1→2→3 in the status bar
4. `wflevels/snowgoons.iff` is rebuilt on disk
5. A `wf_game` window opens showing the level
6. Blender remains open and interactive while the game runs

---

## What this does NOT do (deliberate scope)

- **Engine rebuild**: if `engine/wf_game` itself needs recompiling, run `task build` separately. The button builds the *level*, not the engine.
- **Hot-reload (the remaining 20%)**: BGE let you move objects with the mouse during playback and see physics respond immediately — no stop/edit/relaunch cycle. With the operator, you still have to stop the game, edit in Blender, and click Run again (re-export + rebuild + relaunch, a few seconds). Closing this gap requires:
  1. Engine-side IFF watching — the engine detects that `level.iff` changed on disk and reloads it without restarting.
  2. A live-reload path through the level/object system — tear down and reconstruct objects while physics and scripting are running.

  This is a separate, larger workstream — wanted but not planned yet. For most practical iteration the one-button relaunch is good enough; hot-reload eliminates the round-trip latency for the tightest edit loops.
