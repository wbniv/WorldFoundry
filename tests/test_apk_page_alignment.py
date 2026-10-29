import importlib.util
from pathlib import Path
import struct
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "apk_alignment", ROOT / "scripts/check-apk-page-alignment.py")
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


def elf(align):
    data = bytearray(64 + 56)
    data[:6] = b"\x7fELF\x02\x01"
    struct.pack_into("<Q", data, 32, 64)  # program headers
    struct.pack_into("<HH", data, 54, 56, 1)
    struct.pack_into("<I", data, 64, 1)  # PT_LOAD
    struct.pack_into("<QQ", data, 72, 0, 0)
    struct.pack_into("<Q", data, 112, align)
    return bytes(data)


def apk(tmp_path, libraries):
    path = tmp_path / "test.apk"
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in libraries.items():
            archive.writestr(name, data)
    return path


def test_accepts_all_aligned_libraries(tmp_path):
    assert GATE.check(apk(tmp_path, {
        "lib/arm64-v8a/libwf_game.so": elf(16384),
        "lib/armeabi-v7a/libwf_game.so": elf(65536)})) == []


def test_rejects_one_4k_library_among_valid_abis(tmp_path):
    problems = GATE.check(apk(tmp_path, {
        "lib/arm64-v8a/libwf_game.so": elf(16384),
        "lib/armeabi-v7a/libwf_game.so": elf(4096)}))
    assert len(problems) == 1
    assert "armeabi-v7a" in problems[0] and "align=4096" in problems[0]


def test_rejects_missing_or_invalid_native_library(tmp_path):
    assert "no packaged native libraries" in GATE.check(apk(tmp_path, {"assets/a": b"x"}))[0]
    assert "invalid ELF header" in GATE.check(apk(tmp_path, {"lib/arm64-v8a/a.so": b"bad"}))[0]
