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
    assert count == 6 * 8        # rows 12-19: fire in both frames, a different shade
    assert bbox == (40, 12, 45, 19)
    assert chapter.fire_change(wa, ha, pa, pa) == (0, None)
    mask = bytearray(w * h * 3)
    chapter.fire_change(wa, ha, pa, pb, mask=mask)
    assert mask.count(255) == 3 * 6 * 8       # the reviewer's mask marks exactly those


def test_fire_blob_keeps_a_flame_patch_and_drops_moved_edges():
    w, h = 80, 60
    mask = bytearray(w * h * 3)

    def mark(x, y):
        mask[(y * w + x) * 3:(y * w + x) * 3 + 3] = b"\xff\xff\xff"
    for y in range(40, 54):                 # a speckled 20 x 14 flame patch, about half set
        for x in range(10, 30):
            if (x * 7 + y * 3) % 2 == 0:
                mark(x, y)
    for x in range(40, 80):                 # a moved banner edge: 40 x 3 line
        for y in range(5, 8):
            mark(x, y)
    for x, y in [(60, 30), (62, 31), (64, 32), (66, 33), (68, 34)]:   # a thin diagonal
        mark(x, y)
    count, bbox = chapter.fire_blob(w, h, mask)
    assert count == sum(1 for y in range(40, 54) for x in range(10, 30) if (x * 7 + y * 3) % 2 == 0)
    assert bbox[0] >= 10 and bbox[2] <= 29 and bbox[1] >= 40 and bbox[3] <= 53
    assert chapter.fire_blob(w, h, bytearray(w * h * 3)) == (0, None)


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
            "fps_check": True, "fire_blob_pixels": 60}
    assert chapter.device_ok(good)
    for key, value in [("alive_end", False), ("wf_args", 0), ("room_render", False),
                       ("zforth_errors", ["zforth error"]), ("texture_slot_error", True),
                       ("fps_check", False), ("fire_blob_pixels", 5)]:
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


def parse_touch_script(text):
    """Python mirror of wf_touch::ParseScript (hal/ios/touch_pad.cc)."""
    entries = []
    for entry in text.split(","):
        button, rest = entry.split("@")
        start, duration = rest.split("+")
        entries.append((button, float(start), float(duration)))
    return entries


def test_route_walks_into_the_love_portal_trigger_before_selecting():
    """Regression for run 6ae72785: the iPad stopped at the portal's edge, outside
    the 2.5-unit Select radius (chapter_script.py fy-near), after the Cast1
    route's 4 s of UP. The route now walks 5.2 s, into the portal wall, and
    every press lands inside the screenshots' timeline."""
    entries = parse_touch_script(chapter.TOUCH_SCRIPT)
    ups = [e for e in entries if e[0] == "up"]
    presses = [e for e in entries if e[0] == "a"]
    assert sum(d for _, _, d in ups) >= 5.0
    walk_end = max(s + d for _, s, d in ups)
    card_close, portal_presses = presses[0], presses[1:]
    assert card_close[1] + card_close[2] < chapter.FIRE_AT[0] < ups[0][1]
    assert walk_end < chapter.PORTAL_AT < min(s for _, s, _ in portal_presses)
    assert max(s + d for _, s, d in portal_presses) < chapter.LOVE_AT < chapter.RESUME_AT
    for _, _, d in presses:
        # Long enough to outlast a slow simulator frame (run 6ae73396 lost a
        # 0.3 s press), short of the chapter's 0.65 s hold-to-toggle-camera.
        assert 0.45 <= d < 0.65
    for (_, s1, d1), (_, s2, _) in zip(entries, entries[1:]):
        assert s1 + d1 < s2, "presses must not overlap: a chord is a different input"


# ─── authored frame (finding-your-way docs/plans/2026-11-02-fill-screen-keep-authored-frame.md) ───

def test_expected_view_matches_the_plan_table():
    for (w, h), (hfov, vfov) in {(1920, 1080): (91.5, 60.0), (2131, 1008): (101.3, 60.0),
                                 (2622, 1206): (102.9, 60.0), (2752, 2064): (91.5, 75.2)}.items():
        got = chapter.expected_view(w, h, 1.778, 2.25)
        assert (round(got[0], 1), round(got[1], 1)) == (hfov, vfov), (w, h, got)
    assert round(chapter.expected_view(2752, 2064, 0, 0)[1], 1) == 60.0      # off: today's 60 degrees
    # over the cap: the 2.25 picture
    assert [round(x, 1) for x in chapter.expected_view(3840, 1080, 1.778, 2.25)] == \
        [round(x, 1) for x in chapter.expected_view(2250, 1000, 1.778, 2.25)]


def test_last_view_line_is_the_settled_view():
    # Codemagic build 6ae7e5ed (iPhone 17 Pro): the level logged iOS's 800x600 fallback
    # before UIKit laid out the view. The engine now logs each change; the last one counts.
    log = ("VIEW authored=1.778 screen=1.333 hfov=91.5 vfov=75.2 maximum=2.250 surface=800x600 "
           "viewport=0,0,800x600 pillarbox=0 source=argument\n"
           "ROOM-RENDER scope=all-active source=default\n"
           "VIEW authored=1.778 screen=2.174 hfov=102.9 vfov=60.0 maximum=2.250 surface=2622x1206 "
           "viewport=0,0,2622x1206 pillarbox=0 source=argument\n")
    m = chapter.last_view_line(log)
    assert m and m.group(2) == "2.174" and m.group(3) == "102.9"
    assert chapter.last_view_line("no view here") is None


def test_launch_aspects():
    assert chapter.launch_aspects(["--authored-aspect=1.778", "--maximum-aspect=2.25"]) == (1.778, 2.25)
    assert chapter.launch_aspects([]) == (0.0, 0.0)


def test_app_placement_ipad_band_and_iphone_rotation():
    # Both screenshots have the surface's size transposed; the letterbox tells them apart.
    assert chapter.app_placement(2064, 2752, 2752, 2064, True) == ("band", (0, 602, 2064, 1548))
    assert chapter.app_placement(1206, 2622, 2622, 1206, False) == ("rotate", (0, 0, 2622, 1206))
    assert chapter.app_placement(1920, 1080, 1920, 1080, False) == ("same", (0, 0, 1920, 1080))


def test_rotate_ccw_turns_the_sideways_iphone_frame_upright():
    # 2 x 1: A (red) left, B (blue) right. Counter-clockwise: B on top, A below.
    w, h, px = chapter.rotate_ccw(2, 1, bytes([255, 0, 0, 0, 0, 255]))
    assert (w, h) == (1, 2) and bytes(px) == bytes([0, 0, 255, 255, 0, 0])


def test_authored_band_and_resize():
    assert chapter.authored_band(2752, 2064, 1.778) == (0, 258, 2752, 1548)
    assert chapter.authored_band(2622, 1206, 1.778) == (239, 0, 2144, 1206)
    px = bytes([10, 20, 30]) * (4 * 4)
    assert bytes(chapter.resize_box(4, 4, px, 2, 2)) == bytes([10, 20, 30]) * 4


def test_hud_rects_mirror_the_touch_layout():
    # iPhone: "touch layout 874x402 pt, safe {0,62,20,62}" with the shared layout
    # (hal/touch_controls.h): cell 54, joystick square 2.4 cells, A to D block 2.4 cells.
    cell, pad, block = chapter.touch_layout(874, 402, 0, 62, 20, 62)
    assert cell == pytest.approx(54.0)
    assert pad == pytest.approx((74.0, 242.4, 203.6, 372.0))
    assert block == pytest.approx((670.4, 242.4, 800.0, 372.0))
    stick, ab = chapter.hud_rects(874, 402, 0, 62, 20, 62, 54.0, 3.0)
    assert stick == pytest.approx(tuple(c * 3 for c in pad))
    assert ab == pytest.approx(tuple(c * 3 for c in block))
    # iPad: the 64 pt cap; portrait iPhone: the top inset is reserved, the cap holds.
    assert chapter.touch_layout(1376, 1032, 0, 0, 25, 0)[0] == pytest.approx(64.0)
    cell, pad, block = chapter.touch_layout(402, 874, 62, 0, 34, 0)
    assert cell == pytest.approx(64.0) and pad[3] == pytest.approx(874 - 34 - 6)
    assert pad[2] < block[0]
    assert chapter.touch_layout(100, 100, 0, 60, 0, 60) is None
    assert chapter.hud_rects(100, 100, 0, 60, 0, 60, 0.0, 1.0) == []


TOUR_GOOD = """\
wf_game: touch layout 874x402 pt, safe {0,62,20,62}, cell 54.0 pt
wf_game: touch reading on
wf_game: touch buttons 0x0004
wf_game: touch reading off
wf_game: touch buttons 0x0000
wf_game: touch buttons 0x2000
wf_game: touch buttons 0x200a
wf_game: touch buttons 0x0000
"""


def test_tour_verdict_passes_the_scripted_tour():
    v = chapter.tour_verdict(TOUR_GOOD)
    assert v["ok"] and v["reading_first"] and v["hidden_ignored"] and v["c_closes"] and v["chord"]


def test_tour_verdict_fails_each_parity_defect():
    # Today's iOS HUD: never narrows over a card.
    assert not chapter.tour_verdict(TOUR_GOOD.replace("wf_game: touch reading on\n", ""))["ok"]
    # B (hidden over a card) still sends its bit.
    leak = TOUR_GOOD.replace("touch reading on\n", "touch reading on\nwf_game: touch buttons 0x0002\nwf_game: touch buttons 0x0000\n")
    v = chapter.tour_verdict(leak)
    assert not v["ok"] and not v["hidden_ignored"]
    # LEFT on the joystick still works over a card (it would close the card).
    v = chapter.tour_verdict(TOUR_GOOD.replace("touch reading on\n", "touch reading on\nwf_game: touch buttons 0x4000\n"))
    assert not v["ok"] and not v["hidden_ignored"]
    # C pressed but the card stayed open.
    v = chapter.tour_verdict(TOUR_GOOD.replace("wf_game: touch reading off\n", ""))
    assert not v["ok"] and not v["c_closes"]
    # No C or D on the HUD: the chord never comes through.
    v = chapter.tour_verdict(TOUR_GOOD.replace("0x200a", "0x2002"))
    assert not v["ok"] and not v["chord"]
    assert not chapter.tour_verdict("")["ok"]


def test_tour_script_parses_and_presses_what_the_verdict_expects():
    entries = [e.split("@")[0] for e in chapter.TOUR_SCRIPT.split(",")]
    assert entries == ["b", "left", "c", "right", "b", "d"]
    assert chapter.TOUR_CHORD == 0x200a
    assert chapter.ORIENTATION_PIN == ["-WFOrientation", "landscape"]


def test_frame_check_passes_the_authored_frame_and_fails_a_cut_one(tmp_path):
    fw, fh, ref = chapter.read_png(chapter.FIXTURE)
    assert (fw, fh) == chapter.FIXTURE_SIZE
    # An "iPad after" frame: the fixture with extra rows above and below (4:3 overall).
    extra = (round(fw / (4 / 3)) - fh) // 2
    w, h = fw, fh + 2 * extra
    px = bytearray([40, 40, 40]) * (w * extra) + bytearray(ref) + bytearray([40, 40, 40]) * (w * extra)
    band = chapter.authored_band(w, h, 1.778)
    bw, bh, bpx = chapter.crop(w, h, px, *band)
    small = chapter.resize_box(bw, bh, bpx, fw, fh)
    keep = chapter.band_mask(band, [], (fw, fh))
    assert chapter.frame_diff_pct(small, ref, keep) <= 1.0
    # An "iPad today" frame: the middle three quarters of the width, stretched back: a crop.
    cw = round(fw * 0.75)
    cw_, ch_, cut = chapter.crop(fw, fh, ref, (fw - cw) // 2, 0, cw, fh)
    zoomed = chapter.resize_box(cw_, ch_, cut, fw, fh)
    assert chapter.frame_diff_pct(zoomed, ref, keep) > 5 * chapter.FRAME_CHECK_MAX_PCT


def _shift(px, w, h, dx, dy, fill=(40, 40, 40)):
    """px moved by (dx, dy): out[x, y] = px[x - dx, y - dy]; uncovered pixels get `fill`."""
    out = bytearray(bytes(fill) * (w * h))
    for y in range(h):
        sy = y - dy
        if not 0 <= sy < h:
            continue
        for x in range(w):
            sx = x - dx
            if 0 <= sx < w:
                out[(y * w + x) * 3:(y * w + x) * 3 + 3] = px[(sy * w + sx) * 3:(sy * w + sx) * 3 + 3]
    return out


def test_frame_alignment_absorbs_one_pixel_and_hides_no_real_mismatch():
    fw, fh, ref = chapter.read_png(chapter.FIXTURE)
    keep = chapter.band_mask((0, 0, fw, fh), [], (fw, fh))
    limit = chapter.FRAME_CHECK_MAX_PCT
    # One pixel off (the harness registration of run 6ae806b1's iPad band): edges light up
    # unaligned; the search finds the offset back and the frame matches.
    one = _shift(ref, fw, fh, 1, -1)
    assert chapter.frame_diff_pct(one, ref, keep) > 1.0
    pct, offset = chapter.frame_diff_aligned(one, ref, keep, (fw, fh))
    assert pct <= 0.5 and offset == (1, -1)
    # The same frame needs no offset.
    assert chapter.frame_diff_aligned(ref, ref, keep, (fw, fh)) == (0.0, (0, 0))
    # Real mismatches stay far above the limit with the search.
    for dx, dy in ((10, 0), (0, 10), (-10, 0), (7, 7)):
        pct, _ = chapter.frame_diff_aligned(_shift(ref, fw, fh, dx, dy), ref, keep, (fw, fh))
        assert pct > limit, (dx, dy, pct)
    cw = round(fw * 0.75)                                  # the 4:3 frame with its sides cut
    cw_, ch_, cut = chapter.crop(fw, fh, ref, (fw - cw) // 2, 0, cw, fh)
    pct, _ = chapter.frame_diff_aligned(chapter.resize_box(cw_, ch_, cut, fw, fh), ref, keep, (fw, fh))
    assert pct > 5 * limit
    flipped = bytearray()                                  # another picture: the frame upside down
    for y in reversed(range(fh)):
        flipped += ref[y * fw * 3:(y + 1) * fw * 3]
    assert chapter.frame_diff_aligned(flipped, ref, keep, (fw, fh))[0] > 5 * limit
    grey = bytearray([90, 90, 90]) * (fw * fh)             # nothing drawn
    assert chapter.frame_diff_aligned(grey, ref, keep, (fw, fh))[0] > 5 * limit


def test_band_mask_drops_the_hud_and_the_frame_counter():
    keep = chapter.band_mask((0, 0, 480, 270), [(0, 200, 60, 260)], (480, 270))
    assert not keep[230 * 480 + 30] and not keep[269 * 480 + 479] and keep[100 * 480 + 240]


def test_letterbox_survives_a_system_banner_and_rotate_never_verifies_a_letterbox():
    # The iPad at a third: 688 x 917, the app band at rows 200..716 (602 // 3, 1548 // 3).
    w, h, y3, ch3 = 688, 917, 200, 516
    def frame(banner: bool):
        px = bytearray(w * h * 3)                                # black bars
        px[y3 * w * 3:(y3 + ch3) * w * 3] = bytes([120, 110, 100]) * (w * ch3)   # the picture
        if banner:   # run 6ae806b1's iPad portal frame: a light banner in the top bar's upper part
            for y in range(6, 40):
                px[(y * w + 150) * 3:(y * w + 540) * 3] = bytes([230, 230, 230]) * 390
        return px
    assert chapter.letterbox_state(w, h, frame(False), y3, ch3) == (True, True)
    assert chapter.letterbox_state(w, h, frame(True), y3, ch3) == (True, True)
    # The iPhone's sideways frame fills the screenshot: no dark bars, so rotate may verify.
    full = bytearray([120, 110, 100]) * (402 * 874)
    assert chapter.letterbox_state(402, 874, full, 343, 185) == (False, False)


def test_row_mean_and_outline():
    px = bytearray(3 * 4 * 4)
    out = chapter.outline(4, 4, px, (0, 0, 4, 4), colour=(255, 255, 255), width=1)
    assert chapter.row_mean(4, out, 0, 1) == 255 and chapter.row_mean(4, out, 1, 3) < 255
