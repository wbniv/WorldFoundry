"""End-to-end tests for Phase B1 (set_shader).

Pushes new GLSL to the live engine and asserts the bridge replies with
either shader_reloaded or an error containing the GL info-log.
"""
from __future__ import annotations

import time

# Same shader header + uniforms as backend_modern.cc kVS / kFS — must match
# what the renderer expects to find via glGetUniformLocation.
GOOD_VS = (
    "layout(location=0) in vec3 a_pos;\n"
    "layout(location=1) in vec3 a_color;\n"
    "layout(location=2) in vec2 a_uv;\n"
    "layout(location=3) in vec3 a_normal;\n"
    "out vec3  v_color;\n"
    "out vec2  v_uv;\n"
    "out vec3  v_lit;\n"
    "out float v_fog_factor;\n"
    "uniform mat4 u_mvp;\n"
    "uniform mat4 u_mv;\n"
    "uniform int  u_lighting;\n"
    "uniform vec3 u_ambient;\n"
    "uniform vec3 u_light_dir[3];\n"
    "uniform vec3 u_light_color[3];\n"
    "uniform int   u_fog;\n"
    "uniform float u_fog_start;\n"
    "uniform float u_fog_end;\n"
    "void main() {\n"
    "    gl_Position = u_mvp * vec4(a_pos, 1.0);\n"
    "    v_color = a_color; v_uv = a_uv;\n"
    "    v_lit = vec3(1.0); v_fog_factor = 1.0;\n"
    "}\n"
)

# Tints everything red — visually distinct from the original shader.
GOOD_FS_RED = (
    "in vec3  v_color;\n"
    "in vec2  v_uv;\n"
    "in vec3  v_lit;\n"
    "in float v_fog_factor;\n"
    "out vec4 frag;\n"
    "uniform sampler2D u_tex;\n"
    "uniform int u_use_tex;\n"
    "uniform int u_fog;\n"
    "uniform vec3 u_fog_color;\n"
    "void main() { frag = vec4(1.0, 0.0, 0.0, 1.0); }\n"
)

BROKEN_FS = (
    "in vec3  v_color;\n"
    "out vec4 frag;\n"
    "void main() { frag = nope_this_doesnt_compile; }\n"
)


def _send_set_shader(bridge, vert: str, frag: str):
    bridge.send({"op": "set_shader", "vert": vert, "frag": frag})


def test_set_shader_happy_path(bridge):
    _send_set_shader(bridge, GOOD_VS, GOOD_FS_RED)
    msg = bridge.wait_for(lambda m: m.get("op") in ("shader_reloaded", "error"),
                          timeout=5.0)
    assert msg is not None, "no reply to set_shader"
    assert msg.get("op") == "shader_reloaded", \
        f"expected shader_reloaded, got: {msg}"


def test_set_shader_compile_error_keeps_old_shader(bridge):
    # First, ensure we're back to a known-good state.
    _send_set_shader(bridge, GOOD_VS, GOOD_FS_RED)
    bridge.wait_for(lambda m: m.get("op") == "shader_reloaded", timeout=5.0)
    # Now push junk.
    _send_set_shader(bridge, GOOD_VS, BROKEN_FS)
    msg = bridge.wait_for(lambda m: m.get("op") in ("shader_reloaded", "error")
                          and (m.get("op") == "shader_reloaded"
                               or m.get("what") == "shader_compile"),
                          timeout=5.0)
    assert msg is not None, "no reply to broken set_shader"
    assert msg.get("op") == "error", f"broken GLSL reported success: {msg}"
    assert msg.get("what") == "shader_compile"
    # The log should contain something — GL drivers always emit *some* text.
    assert isinstance(msg.get("log"), str) and len(msg["log"]) > 0, \
        f"expected non-empty log, got: {msg}"
    # Engine should still be alive — push the good shader again and expect success.
    _send_set_shader(bridge, GOOD_VS, GOOD_FS_RED)
    follow = bridge.wait_for(lambda m: m.get("op") == "shader_reloaded", timeout=5.0)
    assert follow is not None, "engine appears dead after broken shader push"
