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

# Licence IDs that are unambiguously free and CC-licensed.
_CC0_ID = 'CC0-1.0'
_CC_PREFIX = 'CC-'
_PAID_ID = 'royalty-free'
from bpy.types import Operator, Panel, PropertyGroup, UIList

from . import asset_threading

# ── import provider module ────────────────────────────────────────────────────

try:
    from . import providers as _wap
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
    quaternius:  BoolProperty(name="Quaternius",     default=True)
    opengameart: BoolProperty(name="OpenGameArt",    default=True)
    sketchfab:   BoolProperty(name="Sketchfab",      default=False)


# ── Scene-level state ─────────────────────────────────────────────────────────

class WF_AssetBrowserState(PropertyGroup):
    query:           StringProperty(name="Search", default="")
    results:         CollectionProperty(type=WF_AssetResultItem)
    result_index:    IntProperty(default=0)
    is_searching:    BoolProperty(default=False)
    status_text:     StringProperty(default="")
    policy_path:     StringProperty(default="")
    policy_accept:   StringProperty(default="")
    providers:       bpy.props.PointerProperty(type=WF_AssetProviderToggles)
    licence_filter:  EnumProperty(
        name="Licence",
        items=[
            ('ALL',        "All",       "Show all policy-allowed licences"),
            ('CC0',        "CC0 only",  "Only CC0-1.0 (no attribution, no restrictions)"),
            ('CC_FREE',    "CC (free)", "Any CC licence (may require attribution)"),
            ('COMMERCIAL', "Paid RF",   "Royalty-free purchased assets (Sketchfab Standard)"),
        ],
        default='ALL',
    )


# ── Thumbnail preview collection ──────────────────────────────────────────────

_previews: bpy.utils.previews.ImagePreviewCollection | None = None

def _ensure_previews():
    global _previews
    if _previews is None:
        _previews = bpy.utils.previews.new()
    return _previews


def _load_thumbnail(item: WF_AssetResultItem):
    """Trigger async thumbnail download for an item."""
    if item.thumb_loaded or not item.thumbnail_url:
        return

    key = f"{item.provider}:{item.provider_id}"
    previews = _ensure_previews()
    if key in previews:
        return

    def fetch():
        import urllib.request
        try:
            with urllib.request.urlopen(item.thumbnail_url, timeout=15) as resp:
                return resp.read()
        except Exception:
            return None

    def on_result(data):
        if data is None:
            return
        try:
            previews = _ensure_previews()
            previews.load(key, item.thumbnail_url, 'URL')
            item.thumb_loaded = True
            # Trigger a UI redraw
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
        except Exception:
            pass

    asset_threading.submit(fetch, on_result=on_result)


# ── UIList ────────────────────────────────────────────────────────────────────

class WF_UL_AssetResults(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type not in {'DEFAULT', 'COMPACT'}:
            return

        key = f"{item.provider}:{item.provider_id}"
        previews = _ensure_previews()
        thumb_icon = previews[key].icon_id if key in previews else 'FILE_IMAGE'

        row = layout.row(align=True)
        row.label(text="", icon_value=thumb_icon)
        col = row.column()
        col.label(text=item.title)
        sub = col.row()
        sub.scale_y = 0.6
        licence_txt = item.licence_id
        if item.lower_trust:
            licence_txt += "  ⚠"
        # Icon hints at licence category at a glance.
        lid = item.licence_id
        if lid == _CC0_ID:
            lic_icon = 'FUND'
        elif lid == _PAID_ID:
            lic_icon = 'SOLO_ON'
        elif lid in ('editorial-only', 'unknown'):
            lic_icon = 'ERROR'
        elif lid.startswith(_CC_PREFIX):
            lic_icon = 'FAKE_USER_ON'
        else:
            lic_icon = 'QUESTION'
        sub.label(text=f"{item.provider}  ·  {licence_txt}", icon=lic_icon)

        # Trigger thumbnail load when item is drawn
        _load_thumbnail(item)


# ── Browse operator ───────────────────────────────────────────────────────────

class WF_OT_browse_assets(Operator):
    bl_idname  = "wf.browse_assets"
    bl_label   = "Search"
    bl_options = {'REGISTER'}

    def execute(self, context):
        if not _WAP_OK:
            self.report({'ERROR'}, f"providers module not loaded: {_WAP_ERROR}")
            return {'CANCELLED'}

        state = context.scene.wf_asset_browser
        query = state.query.strip()
        if not query:
            self.report({'WARNING'}, "Enter a search term first")
            return {'CANCELLED'}

        state.is_searching = True
        state.status_text = f'Searching for "{query}"…'
        state.results.clear()
        state.result_index = 0

        # Resolve policy
        blend_dir = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else os.getcwd()
        policy = _wap.load_policy(blend_dir)
        state.policy_path = policy.policy_path or "(fallback — no licence_policy.toml found)"
        state.policy_accept = ", ".join(sorted(policy.accept_ids))

        # Build credentials from addon preferences.
        addon_prefs = context.preferences.addons.get(__name__.split('.')[0])
        sketchfab_key = addon_prefs.preferences.sketchfab_api_key if addon_prefs else ""
        credentials = _wap.Credentials(sketchfab_api_key=sketchfab_key or None)

        # Collect enabled providers
        toggles = state.providers
        enabled = [
            p for p, on in [
                ("polyhaven",   toggles.polyhaven),
                ("kenney",      toggles.kenney),
                ("ambientcg",   toggles.ambientcg),
                ("quaternius",  toggles.quaternius),
                ("opengameart", toggles.opengameart),
                ("sketchfab",   toggles.sketchfab),
            ]
            if on
        ]

        licence_filter = state.licence_filter

        def do_search():
            results = _wap.search(query, policy, credentials=credentials,
                                  providers=enabled, limit=50)
            if licence_filter == 'CC0':
                results = [r for r in results if r.licence_id == _CC0_ID]
            elif licence_filter == 'CC_FREE':
                results = [r for r in results if r.licence_id.startswith(_CC_PREFIX)]
            elif licence_filter == 'COMMERCIAL':
                results = [r for r in results if r.licence_id == _PAID_ID]
            return results

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
            state.status_text = f"{count} result{'s' if count != 1 else ''} after policy filter"
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()

        def on_error(exc):
            state.is_searching = False
            state.status_text = f"Search failed: {exc}"
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()

        asset_threading.submit(do_search, on_result=on_results, on_error=on_error)
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
            self.report({'ERROR'}, f"providers module not loaded: {_WAP_ERROR}")
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

        addon_prefs = context.preferences.addons.get(__name__.split('.')[0])
        sketchfab_key = addon_prefs.preferences.sketchfab_api_key if addon_prefs else ""
        credentials = _wap.Credentials(sketchfab_api_key=sketchfab_key or None)

        def do_download():
            candidates = _wap.search(provider_id, policy, credentials=credentials,
                                     providers=[provider], limit=5)
            candidate = next((c for c in candidates if c.provider_id == provider_id), None)
            if candidate is None:
                raise RuntimeError(f"Could not resolve {provider}/{provider_id} for download")
            return _wap.download(candidate, dest_dir, credentials=credentials)

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
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if not self._future_done:
            return {'PASS_THROUGH'}

        if self._error_msg:
            self.report({'ERROR'}, self._error_msg)
            context.scene.wf_asset_browser.status_text = f"Download failed: {self._error_msg}"
            return {'CANCELLED'}

        self._finish_import(context, self._result_path)
        return {'FINISHED'}

    def _finish_import(self, context, asset_path: str):
        state = context.scene.wf_asset_browser
        item  = state.results[state.result_index]

        # Import the glTF at the 3D cursor
        bpy.ops.import_scene.gltf(filepath=asset_path)

        # Attach default OAD schema to all newly imported objects
        imported = [o for o in context.selected_objects]
        for obj in imported:
            obj["wf_schema_path"] = _DEFAULT_SCHEMA

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
        state  = context.scene.wf_asset_browser

        if not _WAP_OK:
            layout.label(text="providers module not loaded", icon='ERROR')
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
        row2 = box.row()
        row2.prop(toggles, "quaternius",  toggle=True)
        row2.prop(toggles, "opengameart", toggle=True)
        row3 = box.row()
        row3.prop(toggles, "sketchfab",   toggle=True)

        # Warn when Sketchfab is enabled but no API key is configured.
        if toggles.sketchfab:
            addon_prefs = context.preferences.addons.get(__name__.split('.')[0])
            has_key = bool(addon_prefs and addon_prefs.preferences.sketchfab_api_key)
            if not has_key:
                warn_col = box.column(align=True)
                warn_col.scale_y = 0.8
                warn_col.label(text="No API key — search works, download won't.", icon='INFO')
                warn_col.label(text="Set key in Edit › Preferences › Add-ons › World Foundry.")

        # Licence group filter
        layout.prop(state, "licence_filter", text="Filter")

        # Policy info
        if state.policy_path:
            col = layout.column(align=True)
            col.scale_y = 0.7
            col.label(text="Policy:", icon='LOCKED')
            col.label(text=f"  {state.policy_path}")
            if state.policy_accept:
                col.label(text=f"  Accept: {state.policy_accept}")

        # Status / result count
        if state.status_text:
            layout.label(text=state.status_text, icon='INFO')

        # Results list
        if state.results:
            layout.template_list(
                "WF_UL_AssetResults", "",
                state, "results",
                state, "result_index",
                rows=6,
            )
            layout.operator("wf.import_asset", icon='IMPORT')
        elif not state.is_searching:
            layout.label(text="No results", icon='OUTLINER_OB_MESH')


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
