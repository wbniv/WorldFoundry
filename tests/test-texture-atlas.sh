#!/usr/bin/env bash
# Run the actual material/primitive regression with the canonical desktop build.
set -euo pipefail
test_root="$(cd "$(dirname "$0")/.." && pwd)"
export WF_ENABLE_FENNEL=0 WF_JS_ENGINE=none WF_WASM_ENGINE=none WF_ENABLE_WREN=0
export WF_FORTH_ENGINE=zforth WF_PILOT_ENGINE=builtin WF_PHYSICS_ENGINE=jolt
# Supply build_game.sh as $0 so its normal path discovery stays correct when
# sourced. Reuse its exact active objects/flags, replacing only the thin main.
bash -c '
    source "$0" > /tmp/wf-texture-atlas-build.log 2>&1
    probe="$OUT/texture_atlas_address_test"
    g++ "${CXXFLAGS[@]}" -c "$REPO_ROOT/tests/texture_atlas_address_test.cc" -o "$OUT/texture_atlas_address_test.o"
    test_objects=()
    if [ -n "${WF_ATLAS_MATERIAL_SOURCE:-}" ]; then
        g++ "${CXXFLAGS[@]}" -c "$WF_ATLAS_MATERIAL_SOURCE" -o "$OUT/texture_atlas_baseline.o"
    fi
    for object in "${OBJS[@]}"; do
        case "$object" in
            *__platform_main.cc.o) ;;
            *__material.cc.o)
                if [ -n "${WF_ATLAS_MATERIAL_SOURCE:-}" ]; then
                    test_objects+=("$OUT/texture_atlas_baseline.o")
                else
                    test_objects+=("$object")
                fi
                ;;
            *) test_objects+=("$object");;
        esac
    done
    g++ "${SANITIZE_LINK[@]}" "$OUT/texture_atlas_address_test.o" "${test_objects[@]}" "${JS_LINK_EXTRA[@]}" "${JOLT_LINK_EXTRA[@]}" "${STEAM_LINK_EXTRA[@]}" -lGL -lGLU -lX11 -lm -lpthread -ldl -Wl,-z,noexecstack -o "$probe"
    "$probe"
' "$test_root/engine/build_game.sh"
