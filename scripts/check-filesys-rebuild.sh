#!/usr/bin/env bash
# Rebuild filesys from a committed Git revision without touching the checkout.
set -euo pipefail
root="$(git rev-parse --show-toplevel)"
revision="${1:-HEAD}"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/source" "$tmp/expected"
git -C "$root" archive "$revision" \
    wflevels/filesys wflevels/filesys.iff wflevels/filesys-standalone.iff \
    wfsource/source/oas wftools/wf_blender/build_level_binary.sh \
    wftools/iffcomp-rs wftools/levcomp-rs wftools/textile-rs \
    wftools/wf_iff wftools/wf_oad | tar -x -C "$tmp/source"
for name in filesys/filesys.lvl filesys.iff filesys-standalone.iff; do
    mkdir -p "$tmp/expected/$(dirname "$name")"
    cp "$tmp/source/wflevels/$name" "$tmp/expected/$name"
done
for crate in iffcomp-rs levcomp-rs textile-rs; do
    cargo build --locked --release --manifest-path "$tmp/source/wftools/$crate/Cargo.toml"
done
bash "$tmp/source/wftools/wf_blender/build_level_binary.sh" filesys
for name in filesys/filesys.lvl filesys.iff filesys-standalone.iff; do
    if ! cmp -s "$tmp/expected/$name" "$tmp/source/wflevels/$name"; then
        echo "MISMATCH: wflevels/$name" >&2
        exit 1
    fi
    echo "MATCH: wflevels/$name"
done
