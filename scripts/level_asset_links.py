"""Share level build inputs without linking another level's writable outputs."""
from __future__ import annotations

from pathlib import Path
import re


# textile-rs creates these pages inside the level being built. A symlink here
# would send its writes into the canonical level's texture atlas.
GENERATED_TEXTURE_PAGE = re.compile(r"(?:Perm|Room\d+|palPerm|pal\d+)\.(?:tga|ruv|cyc)\Z")


def link_source_assets(source: Path, target: Path) -> None:
    """Link mesh inputs and source textures, removing old output-page links."""
    for output in target.iterdir():
        if output.is_symlink() and GENERATED_TEXTURE_PAGE.fullmatch(output.name):
            output.unlink()
    for asset in source.iterdir():
        if GENERATED_TEXTURE_PAGE.fullmatch(asset.name):
            continue
        if asset.suffix not in {".iff", ".tga", ".flags"}:
            continue
        link = target / asset.name
        if not link.is_symlink() and not link.exists():
            link.symlink_to(asset.resolve())
