"""A derived level build must not write texture pages into its source level."""
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from level_asset_links import link_source_assets  # noqa: E402


def test_generated_texture_pages_are_local_even_with_stale_symlinks(tmp_path):
    source = tmp_path / "canonical"
    target = tmp_path / "derived"
    source.mkdir()
    target.mkdir()
    pages = ("Perm.tga", "Room0.tga", "palPerm.tga", "pal0.tga")
    for page in pages:
        (source / page).write_bytes(b"canonical " + page.encode())
        (target / page).symlink_to(source / page)
    (target / "Room1.tga").symlink_to(source / "Room0.tga")
    (source / "actor_atlas.tga").write_bytes(b"mesh texture")
    (source / "actor.iff").write_bytes(b"mesh")

    link_source_assets(source, target)

    assert all(not (target / page).is_symlink() for page in pages)
    assert not (target / "Room1.tga").is_symlink()
    assert (target / "actor_atlas.tga").is_symlink()
    assert (target / "actor.iff").is_symlink()
    for page in pages:
        (target / page).write_bytes(b"derived " + page.encode())
        assert (source / page).read_bytes() == b"canonical " + page.encode()
