"""
WF Asset Browser — search, preview, and import CC0 assets from online providers.

Operators:
  WF_OT_browse_assets   Open / refresh the search panel
  WF_OT_import_asset    Download and import the selected asset into the scene
  WF_OT_cancel_search   Abort an in-progress search

Panel:
  WF_PT_asset_browser   Sidebar panel in the 3D Viewport's WF category
"""

import os
import bpy
import bpy.utils.previews
from bpy.props import (
    BoolProperty, CollectionProperty, EnumProperty,
    IntProperty, StringProperty,
)
from bpy.types import Operator, Panel, PropertyGroup, UIList

from . import asset_threading

# ── attempt to import Rust extension ─────────────────────────────────────────

try:
    import wf_asset_provider as _wap
    _WAP_OK = True
except ImportError as _e:
    _WAP_OK = False
    _WAP_ERROR = str(_e)

# ── Default schema to attach on import ───────────────────────────────────────

_DEFAULT_SCHEMA = "wfsource/source/oas/statplat.oad"

# ── Property group for one result row ────────────────────────────────────────

class WF_AssetResultItem(PropertyGroup):
    provider_id:   StringProperty()
    provider:      StringProperty()
    title:         StringProperty()
    thumbnail_url: StringProperty()
    licence_id:    StringProperty()
    download_url:  StringProperty()
    original_url:  StringProperty()
    lower_trust:   BoolProperty(default=False)
    thumb_loaded:  BoolProperty(default=False)


# ── Provider toggle property group ───────────────────────────────────────────

class WF_AssetProviderToggles(PropertyGroup):
    polyhaven:   BoolProperty(name="Poly Haven",    default=True)
    kenney:      BoolProperty(name="Kenney",         default=True)
    ambientcg:   BoolProperty(name="AmbientCG",      default=True)
    opengameart: BoolProperty(name="OpenGameArt",    default=True)


# ── Scene-level state ─────────────────────────────────────────────────────────

class WF_AssetBrowserState(PropertyGroup):
    query:           StringProperty(name="Search", default="")
    results:         CollectionProperty(type=WF_AssetResultItem)
    result_index:    IntProperty(default=0)
    is_searching:    BoolProperty(default=False)
    is_importing:    BoolProperty(default=False)
    status_text:     StringProperty(default="")
    policy_path:     StringProperty(default="")
    policy_accept:   StringProperty(default="")
    providers:       bpy.props.PointerProperty(type=WF_AssetProviderToggles)


# ── Thumbnail preview collection ──────────────────────────────────────────────

_previews: bpy.utils.previews.ImagePreviewCollection | None = None
_pending_thumbs: set = set()   # keys currently in-flight; prevents duplicate fetches
_icon_ids: dict = {}           # key → icon_id; populated by on_result, read by draw_item

def _ensure_previews():
    global _previews
    if _previews is None:
        _previews = bpy.utils.previews.new()
    return _previews


def _thumb_cache_path(provider: str, provider_id: str, suffix: str = '.png') -> str:
    import os
    cache_dir = os.path.join(os.path.expanduser('~'), '.cache', 'wf_asset_provider', 'thumbs')
    os.makedirs(cache_dir, exist_ok=True)
    safe_id = provider_id.replace('/', '_')
    return os.path.join(cache_dir, f"{provider}__{safe_id}{suffix}")


def _redraw_3d():
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    for region in area.regions:
                        region.tag_redraw()
    except Exception:
        pass


def _load_thumbnail(item: WF_AssetResultItem):
    """Load thumbnail from disk cache, or fetch and cache it. One fetch per key."""
    if not item.thumbnail_url:
        return

    key = f"{item.provider}:{item.provider_id}"
    if key in _icon_ids or key in _pending_thumbs:
        return

    # Mark in-flight before submitting so concurrent draw calls don't re-submit
    _pending_thumbs.add(key)

    import os
    url       = item.thumbnail_url
    thumb_key = key
    suffix    = os.path.splitext(url.split('?')[0])[-1] or '.png'
    dst       = _thumb_cache_path(item.provider, item.provider_id, suffix)

    def fetch():
        import urllib.request, os
        # Serve from disk cache — skip network entirely
        if os.path.exists(dst):
            return dst
        try:
            with urllib.request.urlopen(url, timeout=15) as resp:
                data = resp.read()
            with open(dst, 'wb') as f:
                f.write(data)
            return dst
        except Exception as e:
            print(f"[wf_blender] thumb fetch failed {thumb_key}: {e}")
            return None

    def on_result(path):
        _pending_thumbs.discard(thumb_key)
        if not path:
            return
        try:
            p = _ensure_previews()
            if thumb_key not in p:
                p.load(thumb_key, path, 'IMAGE')
            _icon_ids[thumb_key] = p[thumb_key].icon_id
            _redraw_3d()
        except Exception as e:
            import sys
            print(f"[wf_blender] thumb load failed {thumb_key}: {e}", file=sys.stderr)

    asset_threading.submit(fetch, on_result=on_result)


# ── UIList ────────────────────────────────────────────────────────────────────

class WF_UL_AssetResults(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type not in {'DEFAULT', 'COMPACT'}:
            return

        key = f"{item.provider}:{item.provider_id}"
        icon_id = _icon_ids.get(key, 0)

        row = layout.row(align=True)
        if icon_id:
            row.label(text="", icon_value=icon_id)
        else:
            row.label(text="", icon='IMAGE_ALPHA')
        trust = "  ⚠" if item.lower_trust else ""
        row.label(text=f"{item.title}  [{item.provider}{trust}]")

        _load_thumbnail(item)


# ── Browse operator ───────────────────────────────────────────────────────────

class WF_OT_browse_assets(Operator):
    bl_idname  = "wf.browse_assets"
    bl_label   = "Search"
    bl_options = {'REGISTER'}

    def execute(self, context):
        if not _WAP_OK:
            self.report({'ERROR'}, f"wf_asset_provider not loaded: {_WAP_ERROR}")
            return {'CANCELLED'}

        state = context.scene.wf_asset_browser
        query = state.query.strip()
        if not query:
            self.report({'WARNING'}, "Enter a search term first")
            return {'CANCELLED'}

        state.is_searching = True
        state.status_text = f'Querying providers for "{query}"…'
        state.results.clear()
        state.result_index = 0
        _pending_thumbs.clear()
        _icon_ids.clear()

        # Resolve policy
        blend_dir = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else os.getcwd()
        policy = _wap.load_policy(blend_dir)
        state.policy_path = policy.policy_path or "(fallback — no licence_policy.toml found)"
        state.policy_accept = ", ".join(sorted(policy.accept_ids))

        # Collect enabled providers
        toggles = state.providers
        enabled = [
            p for p, enabled in [
                ("polyhaven",   toggles.polyhaven),
                ("kenney",      toggles.kenney),
                ("ambientcg",   toggles.ambientcg),
                ("opengameart", toggles.opengameart),
            ]
            if enabled
        ]

        def do_search():
            return _wap.search(query, policy, providers=enabled, limit=50)

        def on_results(candidates):
            state.is_searching = False
            state.results.clear()
            for c in candidates:
                item = state.results.add()
                item.provider_id   = c.provider_id
                item.provider      = c.provider
                item.title         = c.title
                item.thumbnail_url = c.thumbnail_url
                item.licence_id    = c.licence_id
                item.download_url  = c.download_url
                item.original_url  = c.original_url
                item.lower_trust   = c.lower_trust
                item.thumb_loaded  = False
            count = len(state.results)
            state.status_text = f"{count} result{'s' if count != 1 else ''} from {len(enabled)} providers"

            def _finish_search():
                state.is_searching = False
                try:
                    ctx = bpy.context
                    if ctx and ctx.screen:
                        for area in ctx.screen.areas:
                            if area.type == 'VIEW_3D':
                                area.tag_redraw()
                except Exception:
                    pass
                return None

            bpy.app.timers.register(_finish_search, first_interval=0.4)

        def on_error(exc):
            state.is_searching = False
            state.status_text = f"Search failed: {exc}"
            try:
                for area in context.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()
            except Exception:
                pass

        asset_threading.submit(do_search, on_result=on_results, on_error=on_error)

        # Pulse redraws while searching so the spinner animates.
        # Runs only as long as is_searching is True.
        def _redraw_pulse():
            try:
                scene = bpy.context.scene
                if not scene or not scene.wf_asset_browser.is_searching:
                    return None
                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'VIEW_3D':
                            area.tag_redraw()
            except Exception:
                return None
            return 0.15

        bpy.app.timers.register(_redraw_pulse, first_interval=0.15)
        return {'FINISHED'}


# ── Cancel operator ───────────────────────────────────────────────────────────

class WF_OT_cancel_search(Operator):
    bl_idname = "wf.cancel_asset_search"
    bl_label  = "Cancel"

    def execute(self, context):
        context.scene.wf_asset_browser.is_searching = False
        context.scene.wf_asset_browser.status_text  = "Cancelled"
        return {'FINISHED'}


# ── Import operator ───────────────────────────────────────────────────────────

class WF_OT_import_asset(Operator):
    bl_idname  = "wf.import_asset"
    bl_label   = "Import Selected"
    bl_options = {'REGISTER', 'UNDO'}

    _future_done: bool = False
    _result_path: str  = ""
    _error_msg: str    = ""

    def invoke(self, context, event):
        if not _WAP_OK:
            self.report({'ERROR'}, f"wf_asset_provider not loaded: {_WAP_ERROR}")
            return {'CANCELLED'}

        state = context.scene.wf_asset_browser
        if not state.results or state.result_index < 0:
            self.report({'WARNING'}, "No asset selected")
            return {'CANCELLED'}

        item = state.results[state.result_index]
        blend_dir = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else os.getcwd()
        dest_dir = os.path.join(blend_dir, "assets")

        # Reconstruct a minimal AssetCandidate dict for pybind
        # We pass the provider+id; the Rust layer re-looks-up the provider.
        self._future_done = False
        self._result_path = ""
        self._error_msg   = ""

        # Capture item values (PropertyGroup items can't be closed over safely)
        provider_id = item.provider_id
        provider    = item.provider
        title       = item.title
        licence_id  = item.licence_id
        download_url = item.download_url
        original_url = item.original_url

        # Build a PyAssetCandidate via search to get a proper typed object
        policy = _wap.load_policy(blend_dir)

        def do_download():
            candidates = _wap.search(provider_id, policy, providers=[provider], limit=5)
            candidate = next((c for c in candidates if c.provider_id == provider_id), None)
            if candidate is None:
                raise RuntimeError(f"Could not resolve {provider}/{provider_id} for download")
            return _wap.download(candidate, dest_dir)

        def on_done(result):
            asset_path, manifest = result
            self._result_path = asset_path
            self._future_done = True

        def on_fail(exc):
            self._error_msg   = str(exc)
            self._future_done = True

        asset_threading.submit(do_download, on_result=on_done, on_error=on_fail)
        context.window_manager.modal_handler_add(self)
        state.status_text = f'Downloading "{title}"…'
        state.is_importing = True

        def _import_pulse():
            try:
                scene = bpy.context.scene
                if not scene or not scene.wf_asset_browser.is_importing:
                    return None
                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'VIEW_3D':
                            area.tag_redraw()
            except Exception:
                return None
            return 0.15

        bpy.app.timers.register(_import_pulse, first_interval=0.15)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if not self._future_done:
            return {'PASS_THROUGH'}

        context.scene.wf_asset_browser.is_importing = False

        if self._error_msg:
            self.report({'ERROR'}, self._error_msg)
            context.scene.wf_asset_browser.status_text = f"Download failed: {self._error_msg}"
            return {'CANCELLED'}

        self._finish_import(context, self._result_path)
        return {'FINISHED'}

    def _finish_import(self, context, asset_path: str):
        state = context.scene.wf_asset_browser
        item  = state.results[state.result_index]

        # Import the asset — detect format by extension
        ext = os.path.splitext(asset_path)[1].lower()
        if ext in ('.glb', '.gltf'):
            bpy.ops.import_scene.gltf(filepath=asset_path)
        elif ext == '.obj':
            bpy.ops.wm.obj_import(filepath=asset_path)
        else:
            self.report({'WARNING'}, f"Unknown format {ext!r}; trying glTF importer")
            bpy.ops.import_scene.gltf(filepath=asset_path)

        # Attach default OAD schema to all newly imported objects
        imported = [o for o in context.selected_objects]
        for obj in imported:
            obj["wf_schema_path"] = _DEFAULT_SCHEMA

        # Generate a Blender preview for assets that have no provider thumbnail
        key = f"{item.provider}:{item.provider_id}"
        if key not in _ensure_previews():
            for obj in imported:
                if obj.type == 'MESH':
                    try:
                        obj.asset_mark()
                        with context.temp_override(id=obj):
                            bpy.ops.ed.lib_id_generate_preview()
                        obj_name = obj.name

                        def _try_load_preview(obj_name=obj_name, k=key,
                                              prov=item.provider, pid=item.provider_id):
                            o = bpy.data.objects.get(obj_name)
                            if o is None:
                                return None
                            preview = o.preview  # ImagePreview — do NOT bool-test it
                            if preview is not None:
                                w, h = preview.image_size
                                pixels = list(preview.image_pixels_float)
                                if w > 0 and h > 0 and any(pixels):
                                    cache_path = _thumb_cache_path(prov, pid, '.png')
                                    img = bpy.data.images.new("_wf_thumb_tmp", w, h)
                                    img.pixels[:] = pixels
                                    img.filepath_raw = cache_path
                                    img.file_format = 'PNG'
                                    img.save()
                                    bpy.data.images.remove(img)
                                    p = _ensure_previews()
                                    if k not in p:
                                        p.load(k, cache_path, 'IMAGE')
                                    _icon_ids[k] = p[k].icon_id
                                    _redraw_3d()
                            return None

                        bpy.app.timers.register(_try_load_preview, first_interval=2.5)
                    except Exception:
                        pass
                    break

        self.report(
            {'INFO'},
            f'Imported "{item.title}" ({item.licence_id}) from {item.provider}; '
            f"manifest written alongside asset",
        )
        state.status_text = f'Imported "{item.title}"'


# ── Panel ─────────────────────────────────────────────────────────────────────

class WF_PT_asset_browser(Panel):
    bl_label       = "WF Asset Browser"
    bl_idname      = "WF_PT_asset_browser"
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category    = 'WF'

    def draw(self, context):
        layout = self.layout
        if not context.scene:
            return
        state  = context.scene.wf_asset_browser

        if not _WAP_OK:
            layout.label(text="wf_asset_provider not loaded", icon='ERROR')
            layout.label(text=f"  {_WAP_ERROR}")
            return

        # Search bar
        row = layout.row(align=True)
        row.prop(state, "query", text="", icon='VIEWZOOM')
        if state.is_searching:
            row.operator("wf.cancel_asset_search", text="", icon='X')
        else:
            row.operator("wf.browse_assets", text="", icon='VIEWZOOM')

        # Provider toggles
        box = layout.box()
        box.label(text="Providers:", icon='NETWORK_DRIVE')
        toggles = state.providers
        row = box.row()
        row.prop(toggles, "polyhaven",   toggle=True)
        row.prop(toggles, "kenney",      toggle=True)
        row.prop(toggles, "ambientcg",   toggle=True)
        row.prop(toggles, "opengameart", toggle=True)

        # Policy info
        if state.policy_path:
            col = layout.column(align=True)
            col.scale_y = 0.7
            col.label(text="Policy:", icon='LOCKED')
            col.label(text=f"  {state.policy_path}")
            if state.policy_accept:
                col.label(text=f"  Accept: {state.policy_accept}")

        # In-progress indicator
        if state.is_searching or state.is_importing:
            import time
            factor = (time.time() % 1.0)
            layout.progress(
                text=state.status_text or ("Importing…" if state.is_importing else "Searching…"),
                factor=factor,
                type='BAR',
            )
        elif state.status_text:
            layout.label(text=state.status_text, icon='INFO')

        # Results list
        if state.results:
            layout.template_list(
                "WF_UL_AssetResults", "",
                state, "results",
                state, "result_index",
                rows=12, maxrows=20,
            )

            # Large preview + metadata for selected item
            idx = state.result_index
            if 0 <= idx < len(state.results):
                sel = state.results[idx]
                key = f"{sel.provider}:{sel.provider_id}"
                box = layout.box()
                if key in _icon_ids:
                    box.template_icon(_icon_ids[key], scale=9.0)
                else:
                    col = box.column()
                    col.scale_y = 3.0
                    col.label(text="No preview available", icon='IMAGE_ALPHA')
                box.label(text=sel.title)
                sub = box.row()
                sub.scale_y = 0.7
                licence_txt = sel.licence_id + ("  ⚠ lower trust" if sel.lower_trust else "")
                sub.label(text=f"{sel.provider}  ·  {licence_txt}")

            layout.operator("wf.import_asset", icon='IMPORT')


# ── Registration ──────────────────────────────────────────────────────────────

_CLASSES = [
    WF_AssetResultItem,
    WF_AssetProviderToggles,
    WF_AssetBrowserState,
    WF_UL_AssetResults,
    WF_OT_browse_assets,
    WF_OT_cancel_search,
    WF_OT_import_asset,
    WF_PT_asset_browser,
]


def _menu_import(self, context):
    self.layout.operator("wf.browse_assets", text="WF Asset Browser")


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.wf_asset_browser = bpy.props.PointerProperty(type=WF_AssetBrowserState)
    bpy.types.TOPBAR_MT_file_import.append(_menu_import)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(_menu_import)
    del bpy.types.Scene.wf_asset_browser
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
    asset_threading.shutdown()
    global _previews
    if _previews is not None:
        bpy.utils.previews.remove(_previews)
        _previews = None
