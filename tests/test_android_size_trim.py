"""Regression guard for the Android release size trim (iterations 1 and 2).

Plan: docs/plans/2026-04-18-android-size-trim-iter-2.md
Results: docs/investigations/2026-10-01-android-size-trim-iter-2-results.md

Static checks (no build needed):

  * miniaudio is compiled WAV-only (MA_NO_VORBIS / FLAC / MP3 / GENERATION / ENCODING), and both
    SoundBuffer::play() decoder inits name the WAV format instead of probing every format.
  * the Clang Release compile options of wfengine, wf_game and Jolt carry -fno-exceptions and
    -fvisibility=hidden, and no engine source compiled for Android has a live try/throw.
  * every WF_ANDROID_EXPORT in the sources is in EXPORTS below, and the Android link hides the
    static archives (C++ runtime, builtins, zForth) by name, never with ALL.

With a built release APK's stripped libwf_game.so (cd android && ./gradlew :app:assembleCondoRelease):

  * its defined dynamic symbols are exactly EXPORTS, android_main and ANativeActivity_onCreate
    among them, for both ABIs; its NEEDED libraries are the expected system set.

    python3 -m pytest tests/test_android_size_trim.py -v
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "wfsource" / "source"
CMAKE = REPO / "CMakeLists.txt"

RELEASE_TRIM = ("-fvisibility=hidden", "-fno-exceptions", "-fno-unwind-tables",
                "-fno-asynchronous-unwind-tables")


def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def test_miniaudio_is_wav_only():
    impl = _strip_comments((SRC / "audio" / "linux" / "miniaudio_impl.cc").read_text())
    for flag in ("MA_NO_VORBIS", "MA_NO_FLAC", "MA_NO_MP3", "MA_NO_GENERATION", "MA_NO_ENCODING"):
        assert re.search(rf"^#define {flag}\b", impl, re.M), flag
    # Each define must come before the implementation include, or it does nothing.
    assert impl.index("#define MA_NO_VORBIS") < impl.index("#include <miniaudio/miniaudio.h>")


def test_sfx_decoder_init_names_the_wav_format():
    buf = _strip_comments((SRC / "audio" / "linux" / "buffer.cc").read_text())
    assert re.search(r"\.encodingFormat\s*=\s*ma_encoding_format_wav\s*;", buf)
    inits = re.findall(r"ma_decoder_config\s+(\w+)\s*=\s*(\w+)\(\)", buf)
    play_inits = [fn for var, fn in inits if var == "dcfg" and fn != "ma_decoder_config_init_default"]
    assert play_inits == ["make_wav_decoder_config"] * 2, inits
    assert buf.count("ma_decoder_init_memory(") == 2


def test_wav_decoder_init_decodes_exactly_like_the_generic_init(tmp_path):
    """Both inits give the same frames for PCM WAV and IMA ADPCM WAV, and both refuse non-WAV."""
    cxx = shutil.which("c++")
    ffmpeg = shutil.which("ffmpeg")
    if not cxx or not ffmpeg:
        pytest.skip("needs c++ and ffmpeg on PATH")
    exe = tmp_path / "wav_decoder_init_test"
    subprocess.run([cxx, "-O1", "-w", "-std=c++17", f"-I{REPO / 'engine/vendor/miniaudio-0.11.25'}",
                    str(REPO / "tests" / "wav_decoder_init_test.cc"), "-o", str(exe),
                    "-lpthread", "-ldl", "-lm"], check=True)
    pcm = tmp_path / "pcm.wav"
    adpcm = tmp_path / "adpcm.wav"
    ogg = tmp_path / "tone.ogg"
    junk = tmp_path / "junk.bin"
    tone = ["-f", "lavfi", "-i", "sine=frequency=440:duration=0.5:sample_rate=22050"]
    for out, codec in ((pcm, ["-c:a", "pcm_s16le"]), (adpcm, ["-c:a", "adpcm_ima_wav"]),
                       (ogg, ["-c:a", "libvorbis"])):
        r = subprocess.run([ffmpeg, "-v", "error", "-y", *tone, *codec, str(out)], capture_output=True)
        if r.returncode and out == ogg:
            ogg = None  # ffmpeg without libvorbis: the junk file still covers "not a WAV"
        else:
            assert r.returncode == 0, r.stderr
    junk.write_bytes(bytes(range(256)) * 16)
    files = [pcm, adpcm, junk] + ([ogg] if ogg else [])
    out = subprocess.run([str(exe), *map(str, files)], capture_output=True, text=True, check=True).stdout
    lines = dict(line.split(" ", 1) for line in out.strip().splitlines())
    for f in files:
        generic, wav = (part.split("=", 1)[1] for part in lines[str(f)].split())
        if generic.startswith("0:") or wav.startswith("0:"):
            assert generic == wav, (f.name, generic, wav)
        # On a non-WAV the error code differs (generic: the last stock decoder's error, -10;
        # wav: MA_NO_BACKEND, -203) but buffer.cc only tests != MA_SUCCESS: both fail the same.
    assert lines[str(pcm)].split()[0].startswith("generic=0:11025:")
    assert lines[str(adpcm)].split()[0].startswith("generic=0:"), lines[str(adpcm)]
    assert not lines[str(junk)].split()[0].startswith("generic=0:")
    if ogg:  # MA_NO_VORBIS: an Ogg Vorbis SFX does not decode either way
        assert not lines[str(ogg)].split()[0].startswith("generic=0:")


def _release_options(target: str) -> list[str]:
    """Every Clang-Release generator expression in target_compile_options(<target> ...)."""
    text = CMAKE.read_text()
    found = []
    for m in re.finditer(rf"target_compile_options\(\s*{target}\s+PRIVATE", text):
        # Scan to the matching ")", skipping "# comments" and "quoted strings".
        i, depth, args = m.end(), 1, []
        while depth:
            c = text[i]
            if c == "#":
                i = text.index("\n", i)
                continue
            if c == '"':
                j = text.index('"', i + 1)
                args.append(text[i + 1:j])
                i = j + 1
                continue
            depth += {"(": 1, ")": -1}.get(c, 0)
            i += 1
        for a in args:
            found += re.findall(r"^\$<\$<AND:\$<CONFIG:Release>,\$<CXX_COMPILER_ID:Clang>>:([^>]*)>$", a)
    return found


def test_release_compile_options_trim_exceptions_and_visibility():
    for target in ("wfengine", "wf_game", "Jolt"):
        opts = _release_options(target)
        assert opts, f"no Clang Release options for {target}"
        flags = set(";".join(opts).split(";"))
        for flag in RELEASE_TRIM:
            assert flag in flags, (target, flag)


def test_no_live_exception_code_in_android_sources():
    # The Android Release build is -fno-exceptions: a try or throw there does not compile.
    # Allowed: the Emscripten EM_JS JavaScript block, and fatal.cc's terminate handler, which
    # sits behind #if defined(__cpp_exceptions) || defined(__EXCEPTIONS).
    allowed = {SRC / "hal" / "emscripten" / "platform_main.cc", SRC / "pigsys" / "fatal.cc"}
    offenders = []
    for p in SRC.rglob("*"):
        if p.suffix not in {".cc", ".cpp", ".c", ".hp", ".hpp", ".h"} or p in allowed:
            continue
        code = _strip_comments(p.read_text(errors="replace"))
        code = re.sub(r'"(?:\\.|[^"\\\n])*"', '""', code)  # string literals
        if re.search(r"\bthrow\b|\btry\s*\{|\bcatch\s*\(", code):
            offenders.append(str(p.relative_to(REPO)))
    assert offenders == []
    fatal = (SRC / "pigsys" / "fatal.cc").read_text()
    assert "#if defined(__cpp_exceptions) || defined(__EXCEPTIONS)" in fatal


# The defined dynamic symbols of the release libwf_game.so: nothing more, nothing less.
# Only ANativeActivity_onCreate is looked up by name (the framework's NativeActivity dlsym()s it,
# AndroidManifest android.app.lib_name=wf_game). android_main is called directly by
# android_native_app_glue.c; the other 18 are the plan's WF_ANDROID_EXPORT HAL calls, kept
# visible as the plan specifies (cheap: 20 symbols, ~0.5 KB of .dynsym).
EXPORTS = {
    "ANativeActivity_onCreate", "android_main",
    "WFAndroidEglInit", "WFAndroidEglTerm", "WFAndroidSetHudEnabled",
    "WFAndroidGetAssetManager", "WFAndroidHasWindow", "WFAndroidPumpEvents",
    "WFAndroidPhoneOverlayRects", "HALCreateAAssetAccessor",
    "HALNotifySuspend", "HALNotifyResume", "HALIsSuspended", "HALPumpSuspendedEvents",
    "HALWindowCloseRequested", "HALCloseWindow", "HALRequestClose",
    "SetHostGLContext", "GetHostGLContext", "ClearHostGLContext",
}
NEEDED = {"libEGL.so", "libGLESv3.so", "libandroid.so", "liblog.so", "libm.so", "libdl.so", "libc.so",
          "libOpenSLES.so"}


def test_source_exports_match_the_list():
    marked = set()
    for p in SRC.rglob("*.cc"):
        marked |= set(re.findall(r"WF_ANDROID_EXPORT\s+[\w\s\*]*?\b(\w+)\s*\(", p.read_text(errors="replace")))
    assert marked | {"ANativeActivity_onCreate"} == EXPORTS


def test_android_link_hides_static_archives_by_name():
    text = CMAKE.read_text()
    excluded = set(re.findall(r"--exclude-libs,([\w.+-]+)", text))
    assert {"libc++_static.a", "libc++abi.a", "libunwind.a", "libzforth.a",
            "libclang_rt.builtins-aarch64-android.a", "libclang_rt.builtins-arm-android.a"} <= excluded
    # ALL would also hide the WF_ANDROID_EXPORT functions that live in libwfengine.a.
    assert "ALL" not in excluded and "libwfengine.a" not in excluded
    assert "--export-dynamic-symbol=ANativeActivity_onCreate" in text


def _ndk_tool(name: str) -> str | None:
    for sdk in (Path.home() / "android-sdk-local", Path("/usr/lib/android-sdk")):
        for tool in sorted(sdk.glob(f"ndk/*/toolchains/llvm/prebuilt/linux-x86_64/bin/{name}")):
            return str(tool)
    return shutil.which(name)


def _built_release_libs() -> list[Path]:
    base = REPO / "android" / "app" / "build" / "intermediates" / "stripped_native_libs"
    return sorted(base.glob("*Release/*/out/lib/*/libwf_game.so"))


@pytest.mark.parametrize("abi", ["arm64-v8a", "armeabi-v7a"])
def test_built_release_so_exports_exactly_the_list(abi):
    libs = [p for p in _built_release_libs() if p.parent.name == abi]
    if not libs:
        pytest.skip(f"no release libwf_game.so for {abi} (cd android && ./gradlew :app:assembleCondoRelease)")
    nm, readelf = _ndk_tool("llvm-nm"), _ndk_tool("llvm-readelf")
    if not nm or not readelf:
        pytest.skip("llvm-nm / llvm-readelf not found (NDK or PATH)")
    lib = max(libs, key=lambda p: p.stat().st_mtime)  # the newest release flavor build
    out = subprocess.run([nm, "-D", "--defined-only", str(lib)], capture_output=True, text=True,
                         check=True).stdout
    exported = {line.split()[-1] for line in out.splitlines() if line.strip()}
    assert "android_main" in exported and "ANativeActivity_onCreate" in exported
    assert exported == EXPORTS, (sorted(exported - EXPORTS)[:20], sorted(EXPORTS - exported))
    dyn = subprocess.run([readelf, "-d", str(lib)], capture_output=True, text=True, check=True).stdout
    assert set(re.findall(r"\(NEEDED\)\s+Shared library: \[([^\]]+)\]", dyn)) == NEEDED
