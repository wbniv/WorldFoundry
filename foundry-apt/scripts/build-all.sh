#!/usr/bin/env bash
# Build every package under packages/ into dist/.
#
# Two layouts supported:
#   1. Pure metapackages: packages/<name>/DEBIAN/control only — built directly
#      with dpkg-deb --build.
#   2. Vendored upstream packages: packages/<name>/build.sh — runs the script,
#      which is responsible for producing dist/<name>_<ver>_<arch>.deb itself
#      (it typically fetches an upstream binary, stages it, and runs dpkg-deb).

set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p dist
rm -f dist/*.deb

fail=0
for pkgdir in packages/*/; do
    name=$(basename "$pkgdir")

    if [[ -x "$pkgdir/build.sh" ]]; then
        echo "=== Running $name/build.sh ==="
        if ! bash "$pkgdir/build.sh"; then
            echo "FAIL $name (build.sh exited non-zero)"
            fail=1
        fi
        continue
    fi

    if [[ ! -f "$pkgdir/DEBIAN/control" ]]; then
        echo "SKIP $name (no DEBIAN/control and no build.sh)"
        continue
    fi

    version=$(awk -F': ' '/^Version:/ {print $2; exit}' "$pkgdir/DEBIAN/control")
    arch=$(awk -F': ' '/^Architecture:/ {print $2; exit}' "$pkgdir/DEBIAN/control")
    out="dist/${name}_${version}_${arch}.deb"
    if ! dpkg-deb --build "$pkgdir" "$out" >/dev/null; then
        echo "FAIL $name"
        fail=1
        continue
    fi
    echo "OK   $out  ($(stat -c%s "$out") bytes)"
done

if (( fail )); then
    echo "ERROR: one or more builds failed" >&2
    exit 1
fi

echo
echo "=== dist/ ==="
ls -lh dist/
