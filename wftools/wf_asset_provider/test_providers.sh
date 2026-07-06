#!/usr/bin/env bash
# End-to-end smoke test: search + download one asset from each provider.
# Requires network access.  Run from wf_asset_provider/ directory.
#
# Usage: ./test_providers.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$SCRIPT_DIR/target/debug/wf-asset"
DEST="$(mktemp -d /tmp/wf_asset_e2e_XXXXXX)"
PASS=0
FAIL=0

cleanup() { rm -rf "$DEST"; }
trap cleanup EXIT

if [[ ! -x "$BIN" ]]; then
    echo "Building wf-asset CLI..."
    cargo build --bin wf-asset 2>&1 | tail -3
fi

# ── Test one provider ─────────────────────────────────────────────────────────
# $1 = provider name  $2 = search query  $3 = optional expected asset_id substring
test_provider() {
    local provider="$1" query="$2"
    echo ""
    echo "── $provider ──────────────────────────────────────────────────────────"

    # Search
    local search_out
    search_out=$("$BIN" search "$query" --provider "$provider" --limit 5 2>&1) || true
    echo "$search_out" | grep -v "^  searching\|^policy:" || true

    # Extract first result's provider/id
    local first
    first=$(echo "$search_out" | grep -oP '\['"$provider"'/[^\]]+\]' | head -1 | tr -d '[]')
    if [[ -z "$first" ]]; then
        echo "FAIL: no results for '$query' from $provider"
        FAIL=$((FAIL + 1))
        return
    fi

    local asset_id="${first#*/}"
    echo "Downloading: $first"

    # Download
    local dl_out dest_dir="$DEST/$provider/$asset_id"
    if dl_out=$("$BIN" download "$first" --dest "$DEST" 2>&1); then
        local downloaded
        downloaded=$(echo "$dl_out" | grep "^downloaded:" | head -1)
        local path="${downloaded#downloaded: }"
        if [[ -f "$path" ]]; then
            local size
            size=$(stat -c%s "$path")
            echo "PASS: $path ($size bytes)"
            # For .gltf, check that companion files were also fetched
            if [[ "$path" == *.gltf ]]; then
                local companions
                companions=$(find "$dest_dir" -not -name "*.gltf" -not -name "manifest.json" -type f | wc -l)
                if [[ "$companions" -eq 0 ]]; then
                    echo "  WARN: .gltf downloaded but no companion files found in $dest_dir"
                else
                    echo "  companions: $companions file(s)"
                fi
            fi
            PASS=$((PASS + 1))
        else
            echo "FAIL: CLI reported success but file not found: $path"
            FAIL=$((FAIL + 1))
        fi
    else
        echo "FAIL: download error:"
        echo "$dl_out" | sed 's/^/  /'
        FAIL=$((FAIL + 1))
    fi
}

# ── Run each provider ─────────────────────────────────────────────────────────
# AmbientCG only has ~30 3D models, all in food categories (bread, fruit, etc.)
test_provider "polyhaven"   "barrel"
test_provider "kenney"      "nature"
test_provider "ambientcg"   "bread"
test_provider "quaternius"  "nature"
test_provider "opengameart" "old-oak-tree"

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════"
echo "Results: $PASS passed, $FAIL failed"
echo "══════════════════════════════════════════"
[[ $FAIL -eq 0 ]]
