#!/usr/bin/env bash
set -euo pipefail

# Write a GPG-encrypted credential bundle to secrets/creds-bundle.tar.gpg —
# safe to commit to git (unlike scripts/creds-dump.sh's plaintext tarball,
# which you move yourself and delete after use). Same contents: the AWS
# wf-terraform profile block plus any live scripts/setup.sh session caches.
#
# Thin wrapper — the actual logic lives in
# ../../python-tui-lib/scripts/creds-bundle.sh, same as creds-dump.sh.
#
# This script does NOT run `git add`/`git commit` for you — review the file,
# then commit it yourself.
#
# Tradeoff vs scripts/creds-dump.sh: once committed, this file's history
# lives in the repo for as long as the repo does — not just until you delete
# a transferred copy. Encryption strength aside, pair this with periodic AWS
# key rotation as a backstop.
#
# Usage:
#   ./scripts/creds-commit.sh                          # writes secrets/creds-bundle.tar.gpg
#   ./scripts/creds-commit.sh --output=/path/out.gpg   # explicit output path
#
# On a new machine (after git clone):
#   ./scripts/setup.sh --import-creds=secrets/creds-bundle.tar.gpg
#   (gpg prompts for the passphrase you set when you ran this script)

usage() {
  awk '
    /^[^#]/ && started { exit }
    /^#( |$)/ { started = 1; sub(/^# ?/, ""); print }
  ' "$0"
  exit 0
}
case "${1:-}" in -h|--help) usage ;; esac

OUT=""
for arg in "$@"; do
  case "$arg" in
    --output=*) OUT="${arg#*=}" ;;
    *) echo "ERROR: unknown argument '$arg' (try --help)" >&2; exit 2 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

# shellcheck source=/dev/null
source "$SCRIPT_DIR/cleanup-stack.sh"

CREDS_BUNDLE_LIB="$SCRIPT_DIR/../../python-tui-lib/scripts/creds-bundle.sh"
if [[ ! -f "$CREDS_BUNDLE_LIB" ]]; then
  echo "✗ Shared library not found: $CREDS_BUNDLE_LIB" >&2
  echo "  Clone python-tui-lib as a sibling of this repo first:" >&2
  echo "    cd \"$(dirname "$ROOT_DIR")\" && git clone git@github.com:wbniv/python-tui-lib.git" >&2
  exit 1
fi
# shellcheck source=/dev/null
source "$CREDS_BUNDLE_LIB"
umask 077

# PROJECT and AWS_PROFILE_NAME are read out of the caller's scope by
# creds-bundle.sh.
# shellcheck disable=SC2034
PROJECT="wf"
# shellcheck disable=SC2034
AWS_PROFILE_NAME="wf-terraform"
LOG_DIR="$ROOT_DIR/.setup-logs"
mkdir -p "$LOG_DIR"

mkdir -p "$ROOT_DIR/secrets"
OUT="${OUT:-$ROOT_DIR/secrets/creds-bundle.tar.gpg}"
creds_bundle_dump_encrypted "$OUT"

echo ""
echo "Review, then commit it yourself:"
echo "  git status $OUT"
echo "  git add $OUT && git commit -m 'Update encrypted setup credential bundle'"
