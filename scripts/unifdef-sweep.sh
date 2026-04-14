#!/usr/bin/env bash
# unifdef-sweep.sh — run unifdef with the drop-dead-renderers symbol set over
# every .cc/.hp/.hpi/.h under the given directories. Files without matching
# guards are rewritten unchanged. Per the plan, __LINUX__ is intentionally
# neither -D'd nor -U'd, so its guards survive as porting-documentation.
#
# Usage: unifdef-sweep.sh <dir-or-file> [<dir-or-file>...]
# Example: unifdef-sweep.sh wfsource/source/profile wfsource/source/machine.hp

set -u

UNIFDEF_ARGS=(
    -m
    -U__PSX__ -U__WIN__ -U_WIN32 -U__SATURN__ -U__SAT__ -U__DOS__
    -UDOS -U_WINDOWS -UAMIGA -UARM
    -URENDERER_PSX -URENDERER_SOFTWARE -URENDERER_DIRECTX -URENDERER_XWINDOWS
    -DRENDERER_GL
    -URENDERER_PIPELINE_PSX -URENDERER_PIPELINE_SOFTWARE -URENDERER_PIPELINE_DIRECTX
    -DRENDERER_PIPELINE_GL
    -USCALAR_TYPE_FIXED -DSCALAR_TYPE_FLOAT
)

changed=0
unchanged=0
errors=0

sweep_file() {
    local f="$1"
    unifdef "${UNIFDEF_ARGS[@]}" "$f"
    local rc=$?
    case $rc in
        0) ((unchanged++)) ;;
        1) ((changed++)); echo "  CHANGED: $f" ;;
        *) ((errors++)); echo "  ERROR($rc): $f" >&2 ;;
    esac
}

for target in "$@"; do
    if [[ -f "$target" ]]; then
        sweep_file "$target"
    elif [[ -d "$target" ]]; then
        while IFS= read -r -d '' f; do
            sweep_file "$f"
        done < <(find "$target" -type f \( -name '*.cc' -o -name '*.hp' -o -name '*.hpi' -o -name '*.h' -o -name '*.c' \) -print0)
    else
        echo "skip (not found): $target" >&2
    fi
done

echo ""
echo "Summary: $changed changed, $unchanged unchanged, $errors errors"
[[ $errors -eq 0 ]]
