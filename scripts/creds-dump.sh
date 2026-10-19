#!/usr/bin/env bash
set -euo pipefail

# Bundle this machine's locally-cached WorldFoundry setup credentials into a
# single tarball for migrating to a new machine — the AWS wf-terraform
# profile block plus whatever session-cache files scripts/setup.sh currently
# has live under .setup-logs/ (e.g. a Codemagic token from a run that did not
# reach final success yet).
#
# Thin wrapper — the actual logic lives in
# ../../python-tui-lib/scripts/creds-bundle.sh so every project sourcing it
# stays in sync from one place. Requires this repo to live under ~/ alongside
# python-tui-lib.
#
# This does NOT change scripts/setup.sh's own session-cache lifecycle — those
# files are still created and deleted exactly as they always were. This
# script just sweeps up whatever currently exists, at the moment you run it.
#
# Usage:
#   ./scripts/creds-dump.sh                        # writes .setup-logs/wf-creds-<UTC timestamp>.tar
#   ./scripts/creds-dump.sh --output=/path/out.tar # explicit output path
#
# On the new machine: ./scripts/setup.sh --import-creds=/path/to/bundle.tar
#
# THE OUTPUT FILE CONTAINS LIVE SECRETS IN PLAINTEXT — treat it exactly as
# sensitively as your ~/.aws/credentials file. See the printed warning at the
# end of a successful run for safe/unsafe transfer channels.

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

# AWS_PROFILE_NAME is read out of the caller's scope by creds-bundle.sh.
PROJECT="wf"
# shellcheck disable=SC2034
AWS_PROFILE_NAME="wf-terraform"
LOG_DIR="$ROOT_DIR/.setup-logs"
mkdir -p "$LOG_DIR"

OUT="${OUT:-$LOG_DIR/${PROJECT}-creds-$(date -u +%Y%m%dT%H%M%SZ).tar}"
creds_bundle_dump "$OUT"
