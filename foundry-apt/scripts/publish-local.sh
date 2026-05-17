#!/usr/bin/env bash
# Add every .deb in dist/ to the aptly repo, then publish to ./public/.
# After this, `./public/` is a valid apt repo that can be served by any
# static-file host (nginx, GitHub Pages, Cloudflare R2 + R2.dev URL).
#
# Usage:
#   bash scripts/build-all.sh
#   bash scripts/init-repo.sh
#   bash scripts/publish-local.sh
#   # Then `apt-get` against file://$(pwd)/public to verify locally.

set -euo pipefail
cd "$(dirname "$0")/.."

export APTLY_CONFIG="${APTLY_CONFIG:-$(pwd)/aptly/aptly.conf}"
SUITE="${SUITE:-resolute}"
GPG_KEY="${GPG_KEY:-}"   # empty = skip signing (smoke test only — not for production)

if ! command -v aptly &>/dev/null; then
    echo "ERROR: aptly not installed. Run: sudo apt install aptly" >&2
    exit 1
fi

if ! ls dist/*.deb &>/dev/null; then
    echo "ERROR: no .debs in dist/. Run scripts/build-all.sh first." >&2
    exit 1
fi

echo "=== Adding dist/*.deb to repo 'foundry' ==="
aptly -config="$APTLY_CONFIG" repo add -force-replace foundry dist/

echo
echo "=== Dropping previous published snapshot (if any) ==="
aptly -config="$APTLY_CONFIG" publish drop "$SUITE" filesystem:public: 2>/dev/null || true

echo
echo "=== Publishing snapshot to ./public/ ==="
gpg_args=(-skip-signing)
if [[ -n "$GPG_KEY" ]]; then
    gpg_args=(-gpg-key="$GPG_KEY" -batch)
fi
# Map filesystem:public: to our local ./public/ via aptly.conf 'FileSystemPublishEndpoints'
# For a CI build we instead write to a per-arch S3/R2 endpoint.
aptly -config="$APTLY_CONFIG" publish repo \
    "${gpg_args[@]}" \
    -architectures=amd64,arm64,all \
    -distribution="$SUITE" \
    foundry filesystem:public:

echo
echo "=== Published — apt sources line ==="
echo "deb [trusted=yes] file://$(pwd)/public $SUITE main"
