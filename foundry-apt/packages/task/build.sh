#!/usr/bin/env bash
# Repackage the upstream `task` binary from github.com/go-task/task as
# Debian .debs for amd64 and arm64.
#
# Pinned version + sha256 — bump together. Verify on a release page like
# https://github.com/go-task/task/releases/tag/v3.39.2
#
# Builds: dist/task_<VERSION>_amd64.deb, dist/task_<VERSION>_arm64.deb

set -euo pipefail

VERSION="${TASK_VERSION:-3.51.1}"
# sha256 of the binary tarballs from the upstream release (verified once at pin time)
SHA256_AMD64="${TASK_SHA256_AMD64:-da7e92f0ff961ef2aae7cfecbad8d1fd2a08d7b09ba968673adf7ff389b243b5}"
SHA256_ARM64="${TASK_SHA256_ARM64:-49c58bb00eff2449a5553f3b3e694fc424e0dc04d5c669d8831126daee1000f8}"

cd "$(dirname "$0")"
SCRIPT_DIR="$(pwd)"
REPO_ROOT="$(cd ../.. && pwd)"
mkdir -p "$REPO_ROOT/dist"

build_one() {
    local arch="$1" sha="$2" upstream_arch="$3"
    local tag="task_${VERSION}_${arch}"
    local workdir
    workdir=$(mktemp -d)
    trap 'rm -rf "$workdir"' RETURN

    echo "=== Building $tag ==="

    local url="https://github.com/go-task/task/releases/download/v${VERSION}/task_linux_${upstream_arch}.tar.gz"
    echo "Fetching $url"
    curl -fsSL -o "$workdir/task.tar.gz" "$url"

    echo "Verifying sha256..."
    echo "$sha  $workdir/task.tar.gz" | sha256sum -c -

    local stage="$workdir/stage"
    mkdir -p "$stage/usr/bin" "$stage/usr/share/doc/task" "$stage/DEBIAN"

    tar -xzf "$workdir/task.tar.gz" -C "$workdir" task LICENSE README.md
    install -m 0755 "$workdir/task" "$stage/usr/bin/task"
    install -m 0644 "$workdir/LICENSE" "$stage/usr/share/doc/task/copyright"
    install -m 0644 "$workdir/README.md" "$stage/usr/share/doc/task/README.md"

    cat > "$stage/DEBIAN/control" <<EOF
Package: task
Version: ${VERSION}
Architecture: ${arch}
Maintainer: World Foundry <packages@worldfoundry.org>
Section: devel
Priority: optional
Homepage: https://taskfile.dev/
Description: task — a task runner / build tool written in Go
 Task is a task runner / build tool that aims to be simpler and easier
 to use than e.g. GNU Make. It uses a simple YAML schema (Taskfile.yml).
 .
 Repackaged from the upstream release binary at
 https://github.com/go-task/task/releases/tag/v${VERSION}
 for inclusion in the Foundry Linux APT repo, because go-task is not
 in the Ubuntu archive. The upstream MIT licence applies (see
 /usr/share/doc/task/copyright).
EOF

    local out="$REPO_ROOT/dist/${tag}.deb"
    dpkg-deb --build "$stage" "$out" >/dev/null
    echo "OK   $out  ($(stat -c%s "$out") bytes)"
}

# Skip if upstream auth blocks us (e.g. in an offline test) — fail loudly otherwise.
if ! curl -fsI -o /dev/null https://github.com/; then
    echo "ERROR: cannot reach github.com — skipping task package build" >&2
    exit 1
fi

build_one amd64 "$SHA256_AMD64" amd64
build_one arm64 "$SHA256_ARM64" arm64
