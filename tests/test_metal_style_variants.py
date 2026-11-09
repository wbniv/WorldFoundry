"""The Metal backend's style-off program must be the pre-style shader, token for token.

Reef plan step 14 (2026-11-09): with every style field at 0, Metal moved 3 pixels by
1/255 against the pre-style engine (macos-style-metal runs 6af14d47 and 6af1a232).
A probe without the style work in wf_vs was pixel-identical (run 6af1ade1), so the
unused style arithmetic changed fast-math code generation. The fix compiles kMSL
twice, with and without WF_STYLE, like GL's #ifdef WF_STYLE. This test keeps the
style-off text equal to fd9349c8's shader (tests/fixtures/renderer/
metal-prestyle-functions.msl) and checks the host builds and selects both programs.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "wfsource/source/gfx/metal/backend_metal.mm"
FIXTURE = ROOT / "tests/fixtures/renderer/metal-prestyle-functions.msl"
TOKEN = re.compile(r"[A-Za-z_]\w*|\d+\.\d*|\.\d+|\d+|\S")


def kmsl():
    return BACKEND.read_text().split('R"MSL(', 1)[1].split(')MSL"', 1)[0]


def preprocess(text, defined):
    """The subset kMSL uses: #ifdef/#ifndef/#else/#endif and object-like #define."""
    macros, stack, out = {}, [], []
    for line in text.splitlines():
        directive = line.strip()
        if directive.startswith(("#ifdef", "#ifndef")):
            name = directive.split()[1]
            stack.append((name in defined) == directive.startswith("#ifdef"))
        elif directive.startswith("#else"):
            stack[-1] = not stack[-1]
        elif directive.startswith("#endif"):
            stack.pop()
        elif not all(stack):
            continue
        elif directive.startswith("#define"):
            _, name, value = directive.split(None, 2)
            macros[name] = value
        else:
            out.append(line)
    assert not stack, "unbalanced #ifdef in kMSL"
    tokens = []
    for token in TOKEN.findall(re.sub(r"//[^\n]*", "", "\n".join(out))):
        tokens.extend(TOKEN.findall(macros[token]) if token in macros else [token])
    return tokens


def section(tokens, start, end_marker=None):
    i = next(n for n in range(len(tokens)) if tokens[n:n + len(start)] == start)
    if end_marker is None:
        return tokens[i:]
    j = next(n for n in range(i, len(tokens)) if tokens[n:n + len(end_marker)] == end_marker)
    return tokens[i:j]


def test_style_off_shader_is_the_pre_style_shader():
    expected = preprocess(FIXTURE.read_text(), set())
    actual = preprocess(kmsl(), set())
    vertex_out = ["struct", "VertexOut"]
    assert section(actual, vertex_out, ["}", ";"]) == section(expected, vertex_out, ["}", ";"])
    functions = ["vertex", "VertexOut", "wf_vs"]
    assert section(actual, functions) == section(expected, functions), (
        "kMSL without WF_STYLE differs from the pre-style wf_vs/wf_fs; keep every style "
        "addition inside #ifdef WF_STYLE")


def test_style_program_keeps_the_style_math():
    tokens = preprocess(kmsl(), {"WF_STYLE"})
    text = " ".join(tokens)
    for needle in ("style_absorb", "style_caustic", "exp", "floor", "v . absorb", "v . caustic"):
        assert needle in text, f"style program lost {needle!r}"


def test_host_builds_and_selects_both_programs():
    source = BACKEND.read_text()
    assert '@"WF_STYLE"' in source and "preprocessorMacros" in source
    for name in ("_stylePipeline", "_styleBlendPipeline"):
        assert f"{name} = [_device newRenderPipelineStateWithDescriptor" in source
    selection = re.search(r"setRenderPipelineState:\(_bitmapPass[^;]+;", source, re.S)
    assert selection and "RBStyleShadingActive" in source[selection.start() - 200:selection.start()]
    assert "_styleBlendPipeline" in selection.group(0) and "_stylePipeline" in selection.group(0)
