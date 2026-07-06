#!/usr/bin/env bash
# install-blender.sh — download + verify + unpack a specific Blender release
# from download.blender.org. Idempotent.
#
# Used by:
#   - the wf_blender add-on test matrix (tests/test_blender_addon_export.py)
#   - GitHub Actions blender-addon-tests matrix workflow

set -euo pipefail

usage() {
    cat <<'EOF'
install-blender.sh — download + verify + unpack a Blender release

Usage: install-blender.sh <BL_VERSION> <TARGET_DIR>
       install-blender.sh -h | --help

Examples:
  install-blender.sh 4.0.2 /tmp/blender-4.0.2
  install-blender.sh 4.5.0 /opt/blender-4.5.0

After success, the Blender binary lives at <TARGET_DIR>/blender.

Behaviour:
  - Downloads blender-<version>-linux-x64.tar.xz from download.blender.org
  - Verifies SHA256 against the official .sha256 manifest published by
    blender.org for that release.
  - Extracts to <TARGET_DIR>.
  - Idempotent: skips download/extract if <TARGET_DIR>/blender already
    reports the requested version via --version.

Exit codes:
  0  success (already installed, or freshly installed)
  2  bad argument
  3  download/checksum failure
EOF
}

case "${1:-}" in
    -h|--help|"") usage; exit 0 ;;
esac

if [[ $# -ne 2 ]]; then
    echo "ERROR: expected 2 arguments (BL_VERSION TARGET_DIR), got $#" >&2
    usage
    exit 2
fi

BL_VERSION="$1"
TARGET_DIR="$2"

# Parse major.minor from the version string (e.g. "4.0.2" -> "4.0")
if [[ ! "$BL_VERSION" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
    echo "ERROR: BL_VERSION must be MAJOR.MINOR.PATCH (got: $BL_VERSION)" >&2
    exit 2
fi
MAJOR_MINOR="${BASH_REMATCH[1]}.${BASH_REMATCH[2]}"

TARBALL="blender-${BL_VERSION}-linux-x64.tar.xz"
URL="https://download.blender.org/release/Blender${MAJOR_MINOR}/${TARBALL}"
SHA_URL="https://download.blender.org/release/Blender${MAJOR_MINOR}/blender-${BL_VERSION}.sha256"

# Idempotency: if Blender is already installed at TARGET_DIR/blender and
# reports the requested version, skip.
if [[ -x "${TARGET_DIR}/blender" ]]; then
    if INSTALLED_VERSION=$("${TARGET_DIR}/blender" --version 2>/dev/null | head -1 | awk '{print $2}') \
       && [[ "$INSTALLED_VERSION" == "$BL_VERSION" ]]; then
        echo "install-blender: ${TARGET_DIR}/blender already at $BL_VERSION — skipping"
        exit 0
    fi
fi

# Stage download into a tempdir, then move into place
WORK=$(mktemp -d)
# shellcheck disable=SC2064  # WORK fixed at trap-set time, this is the intent
trap "rm -rf '$WORK'" EXIT

echo "install-blender: downloading $URL"
if ! curl -fsSL -o "$WORK/$TARBALL" "$URL"; then
    echo "ERROR: failed to download $URL" >&2
    exit 3
fi

echo "install-blender: fetching SHA256 manifest"
SHA_FILE="$WORK/checksums.sha256"
if ! curl -fsSL -o "$SHA_FILE" "$SHA_URL"; then
    echo "ERROR: failed to download $SHA_URL" >&2
    exit 3
fi

# Grep the line for the tarball and verify
EXPECTED_SHA=$(awk -v f="$TARBALL" '$2 == f {print $1}' "$SHA_FILE")
if [[ -z "$EXPECTED_SHA" ]]; then
    echo "ERROR: $TARBALL not listed in $SHA_URL manifest" >&2
    exit 3
fi

echo "install-blender: verifying SHA256"
ACTUAL_SHA=$(sha256sum "$WORK/$TARBALL" | awk '{print $1}')
if [[ "$ACTUAL_SHA" != "$EXPECTED_SHA" ]]; then
    echo "ERROR: SHA256 mismatch for $TARBALL" >&2
    echo "  expected: $EXPECTED_SHA" >&2
    echo "  actual:   $ACTUAL_SHA" >&2
    exit 3
fi

echo "install-blender: extracting to $TARGET_DIR"
mkdir -p "$TARGET_DIR"
# Strip the top-level "blender-<version>-linux-x64" directory in the tarball
# so the binary lands at $TARGET_DIR/blender
tar -xf "$WORK/$TARBALL" -C "$TARGET_DIR" --strip-components=1

# Sanity check: the binary should exist and run
if [[ ! -x "${TARGET_DIR}/blender" ]]; then
    echo "ERROR: ${TARGET_DIR}/blender missing or not executable after extract" >&2
    exit 3
fi

INSTALLED_VERSION=$("${TARGET_DIR}/blender" --version 2>/dev/null | head -1 | awk '{print $2}')
echo "install-blender: ${TARGET_DIR}/blender is Blender $INSTALLED_VERSION"
