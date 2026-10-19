"""
Asset Browser — licence-aware 3D asset browser with provenance tracking.

Searches Sketchfab, Polyhaven, Kenney, Quaternius; records a provenance
manifest.json for every imported asset; filters by licence_policy.toml.

Installation: Edit > Preferences > Add-ons > Install from Disk
No build step required — pure Python.
"""

import bpy
from bpy.props import StringProperty

bl_info = {
    "name":        "Asset Browser",
    "author":      "World Foundry",
    "version":     (0, 2, 0),
    "blender":     (4, 2, 0),
    "location":    "3D Viewport > Sidebar > Asset Browser",
    "description": "Licence-aware asset browser with provenance tracking",
    "category":    "Import-Export",
}

from . import asset_browser  # noqa: E402


class WFAssetBrowserPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    sketchfab_api_key: StringProperty(
        name="Sketchfab API Key",
        description="Bearer token from sketchfab.com/settings#api-token. Required for downloading Sketchfab assets.",
        subtype='PASSWORD',
        default="",
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "sketchfab_api_key")
        layout.label(text="Get your token at: sketchfab.com/settings#api-token", icon='URL')


def register():
    bpy.utils.register_class(WFAssetBrowserPreferences)
    asset_browser.register()


def unregister():
    asset_browser.unregister()
    bpy.utils.unregister_class(WFAssetBrowserPreferences)
