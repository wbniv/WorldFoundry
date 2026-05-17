#!/usr/bin/env bash
# Build every metapackage under packages/ into dist/.
# Reads version from the package's DEBIAN/control file.

set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p dist
rm -f dist/*.deb

fail=0
for pkgdir in packages/*/; do
    name=$(basename "$pkgdir")
    if [[ ! -f "$pkgdir/DEBIAN/control" ]]; then
        echo "SKIP $name (no DEBIAN/control)"
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
