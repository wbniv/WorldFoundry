"""Host tests for scripts/ios_sim_chapter.py, the ios-simulator-chapter run.

The simulator half needs a Mac; what runs here is everything a red Codemagic
run would otherwise be the first to exercise: the APK and level SHA-256 gate,
the .app copy that carries cd.iff and wf_args.txt, the brazier frame
comparison, and the log checks (wf_args.txt, ROOM-RENDER, zForth errors).
"""
from __future__ import annotations

import hashlib
import importlib.util
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("ios_sim_chapter", REPO / "scripts" / "ios_sim_chapter.py")
chapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chapter)

ARGS = (b"--vram-width=5120\n--vram-height=2048\n--vram-slot-width=1024\n--vram-slot-height=512\n"
        b"--vram-perm-width=2048\n--vram-perm-height=1024\n--static-mesh=1\n--static-mesh-shared-index=1\n")


def frame(w, h, background, patches):
    px = bytearray(bytes(background) * (w * h))
    for (x0, y0, x1, y1), colour in patches:
        for y in range(y0, y1):
            for x in range(x0, x1):
                px[(y * w + x) * 3:(y * w + x) * 3 + 3] = bytes(colour)
    return bytes(px)


def test_fire_change_counts_only_fire_coloured_changes(tmp_path):
    w, h, stone = 64, 48, (120, 110, 100)
    a = frame(w, h, stone, [((40, 10, 46, 20), (255, 120, 20)),    # flame, frame 1
                            ((5, 5, 10, 10), (230, 190, 70))])     # gold trim, same in both
    b = frame(w, h, stone, [((40, 12, 46, 22), (250, 200, 60)),    # flame moved and brightened
                            ((5, 5, 10, 10), (230, 190, 70)),
                            ((20, 30, 30, 40), (60, 60, 200))])    # a blue change: not fire
    chapter.write_png(tmp_path / "a.png", w, h, a)
    chapter.write_png(tmp_path / "b.png", w, h, b)
    wa, ha, pa = chapter.read_png(tmp_path / "a.png")
    wb, hb, pb = chapter.read_png(tmp_path / "b.png")
    count, bbox = chapter.fire_change(wa, ha, pa, pb)
    assert count == 6 * 12       # rows 10-21 of the 6-wide flame column change
    assert bbox == (40, 10, 45, 21)
    assert chapter.fire_change(wa, ha, pa, pa) == (0, None)
    mask = bytearray(w * h * 3)
    chapter.fire_change(wa, ha, pa, pb, mask=mask)
    assert mask.count(255) == 3 * 6 * 12       # the reviewer's mask marks exactly those


def test_fire_palette_excludes_hud_and_trim():
    for stop in [(220, 65, 8), (240, 90, 12), (255, 120, 18), (255, 160, 30), (255, 205, 70)]:
        assert chapter.is_fire(*stop), stop       # doom_fire.hp palette stops
    assert not chapter.is_fire(204, 64, 64)       # the HUD's A button, full alpha
    assert not chapter.is_fire(153, 153, 153)     # HUD D-pad gray
    assert not chapter.is_fire(160, 130, 60)      # dull gold
    assert not chapter.is_fire(200, 170, 120)     # Temple floor tan


def test_log_findings():
    text = "\n".join([
        "wf_game: wf_args.txt found, gave 8 argument(s); 0 launch argument(s)",
        "ROOM-RENDER scope=current-only source=RPRP",
        "zforth: INDEXOF_CAMSHOT = 1921 (expect 1921)",
        "wf_game: touch buttons 0x0001",
    ])
    f = chapter.log_findings(text)
    assert f == {"room_render": True, "zforth_errors": [], "texture_slot_error": False,
                 "wf_args": 8, "touch_a": True, "touch_up": False}
    bad = chapter.log_findings("zforth unknown token: doom-fire-frame\n"
                               "zforth compile error 3 (defs): : x ;\n"
                               "LoadTexture: 2048x1024 texture does not fit its 256x256 VRAM slot\n"
                               "ROOM-RENDER scope=all-active source=default\n"
                               "wf_game: wf_args.txt absent, gave 0 argument(s); 0 launch argument(s)")
    assert len(bad["zforth_errors"]) == 2 and bad["texture_slot_error"]
    assert not bad["room_render"] and bad["wf_args"] == 0


def test_device_ok_needs_every_check():
    good = {"install": True, "launch": True, "alive_20s": True, "alive_end": True, "wf_args": 8,
            "room_render": True, "zforth_errors": [], "texture_slot_error": False,
            "fps_check": True, "fire_pixels": 120}
    assert chapter.device_ok(good)
    for key, value in [("alive_end", False), ("wf_args", 0), ("room_render", False),
                       ("zforth_errors", ["zforth error"]), ("texture_slot_error", True),
                       ("fps_check", False), ("fire_pixels", 3)]:
        assert not chapter.device_ok(good | {key: value}), key


def make_apk(path: Path, level: bytes) -> str:
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("assets/cd.iff", level)
        z.writestr("assets/wf_args.txt", ARGS)
        z.writestr("lib/arm64-v8a/libwf_game.so", b"elf")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_bundle_copies_level_and_arguments_into_the_app(tmp_path):
    level = b"IFF level" * 100
    apk_sha = make_apk(tmp_path / "chapter.apk", level)
    app = tmp_path / "engine" / "Release" / "wf_game.app"
    app.mkdir(parents=True)
    (app / "cd.iff").write_bytes(b"engine sample scene")
    (app / "wf_game").write_bytes(b"binary")
    assert chapter.find_app(tmp_path) == app
    out = chapter.bundle(tmp_path / "chapter.apk", apk_sha, hashlib.sha256(level).hexdigest(),
                         app, tmp_path / "chapter-app")
    assert (out / "cd.iff").read_bytes() == level
    assert (out / "wf_args.txt").read_bytes() == ARGS
    assert (out / "wf_game").read_bytes() == b"binary"
    assert (app / "cd.iff").read_bytes() == b"engine sample scene"   # the built app is untouched


def test_bundle_refuses_a_different_apk_or_level(tmp_path):
    level = b"IFF level"
    apk_sha = make_apk(tmp_path / "chapter.apk", level)
    app = tmp_path / "wf_game.app"
    app.mkdir()
    with pytest.raises(SystemExit, match="APK SHA-256 mismatch"):
        chapter.bundle(tmp_path / "chapter.apk", "0" * 64, hashlib.sha256(level).hexdigest(), app, tmp_path / "o")
    with pytest.raises(SystemExit, match="cd.iff SHA-256 mismatch"):
        chapter.bundle(tmp_path / "chapter.apk", apk_sha, "0" * 64, app, tmp_path / "o")
