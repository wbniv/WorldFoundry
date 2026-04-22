#!/usr/bin/env bash
# Fetch Codemagic build artifacts for the iOS port.
#
# Usage:
#   codemagic-fetch-latest.sh                  # newest finished build on current branch
#   codemagic-fetch-latest.sh --branch master  # newest finished build on <branch>
#   codemagic-fetch-latest.sh --index 26       # build #26 (per-app index)
#   codemagic-fetch-latest.sh --build-id <_id> # specific build by Codemagic _id
#   codemagic-fetch-latest.sh --watch          # poll until HEAD commit's build finishes, then fetch
#   codemagic-fetch-latest.sh --watch --commit <SHA>   # watch a specific commit
#   codemagic-fetch-latest.sh --help
#
# Requires:
#   - ~/.config/codemagic/token  (mode 600; see docs/codemagic-setup.md Step 5)
#   - curl, python3, unzip
#
# Output:
#   Extracts the build's "bundle" artefact (WorldFoundry_<N>_artifacts.zip) into
#   /tmp/wf<N>/ and prints what's inside.  Also prints the URLs of the .app and
#   .dSYM artefacts for optional separate download.

set -euo pipefail

APP_ID="${CM_APP_ID:-69e86667c563ac927a0fbcba}"   # wbniv/WorldFoundry on Codemagic
TOKEN_FILE="${CM_TOKEN_FILE:-$HOME/.config/codemagic/token}"
API="https://api.codemagic.io"

BRANCH=""
BUILD_INDEX=""
BUILD_ID=""
WATCH=0
COMMIT=""

while [ $# -gt 0 ]; do
    case "$1" in
        --branch)   BRANCH="$2"; shift 2;;
        --index)    BUILD_INDEX="$2"; shift 2;;
        --build-id) BUILD_ID="$2"; shift 2;;
        --commit)   COMMIT="$2"; shift 2;;
        --watch)    WATCH=1; shift;;
        -h|--help)
            sed -n '2,20p' "$0"; exit 0;;
        *) echo "unknown arg: $1" >&2; exit 2;;
    esac
done

if [ ! -r "$TOKEN_FILE" ]; then
    echo "error: token file not readable: $TOKEN_FILE" >&2
    echo "       see docs/codemagic-setup.md Step 5" >&2
    exit 1
fi
TOKEN="$(tr -d '\n' < "$TOKEN_FILE")"

if [ -z "$BRANCH" ] && [ -z "$BUILD_INDEX" ] && [ -z "$BUILD_ID" ]; then
    BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
    [ -z "$BRANCH" ] && { echo "error: not in a git repo and no --branch given" >&2; exit 2; }
fi

if [ -z "$COMMIT" ] && [ "$WATCH" -eq 1 ]; then
    COMMIT="$(git rev-parse HEAD 2>/dev/null || true)"
    [ -z "$COMMIT" ] && { echo "error: --watch needs a commit; pass --commit <SHA>" >&2; exit 2; }
fi

_api() {
    curl -sSf -H "x-auth-token: $TOKEN" "$API$1"
}

# -------- resolve build --------
resolve_build_json() {
    if [ -n "$BUILD_ID" ]; then
        _api "/builds/$BUILD_ID" | python3 -c 'import json,sys; d=json.load(sys.stdin); b=d.get("build",d); print(json.dumps(b))'
        return
    fi
    local qs="appId=$APP_ID&limit=50"
    [ -n "$BRANCH" ] && qs="$qs&branch=$BRANCH"
    _api "/builds?$qs" | python3 -c '
import json, sys, os
d = json.load(sys.stdin)
builds = d.get("builds", [])
want_idx = os.environ.get("BUILD_INDEX", "").strip()
want_commit = os.environ.get("COMMIT", "").strip()
if want_idx:
    builds = [b for b in builds if str(b.get("index")) == want_idx]
elif want_commit:
    # find the newest build for this commit (any status)
    builds = [b for b in builds if (b.get("commit") or {}).get("hash","").startswith(want_commit[:40])]
else:
    builds = [b for b in builds if b.get("status") == "finished"]
if not builds:
    sys.stderr.write("no matching build\n"); sys.exit(1)
print(json.dumps(builds[0]))
'
}

export BUILD_INDEX COMMIT

if [ "$WATCH" -eq 1 ]; then
    printf "watching for build of commit %s on %s...\n" "${COMMIT:0:12}" "${BRANCH:-<any>}" >&2
    while true; do
        if build_json="$(resolve_build_json 2>/dev/null)"; then
            status=$(printf '%s' "$build_json" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("status"))')
            idx=$(printf '%s' "$build_json" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("index"))')
            case "$status" in
                finished) echo "build #$idx finished — fetching" >&2; break;;
                canceled|failed|timeout|skipped)
                    echo "build #$idx ended with status=$status — fetching what's there" >&2
                    break;;
                *) printf "  build #%s status=%s — sleeping 20s\n" "$idx" "$status" >&2; sleep 20;;
            esac
        else
            echo "  no build yet for commit — sleeping 20s" >&2
            sleep 20
        fi
    done
else
    build_json="$(resolve_build_json)"
fi

build_idx=$(printf '%s' "$build_json" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("index"))')
build_id=$(printf '%s' "$build_json" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("_id"))')
status=$(printf '%s' "$build_json" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("status"))')
commit=$(printf '%s' "$build_json" | python3 -c 'import json,sys; d=json.load(sys.stdin); print((d.get("commit") or {}).get("hash","")[:12])')
branch_r=$(printf '%s' "$build_json" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("branch"))')
printf 'build #%s  id=%s  branch=%s  commit=%s  status=%s\n' "$build_idx" "$build_id" "$branch_r" "$commit" "$status"

# -------- pick + download the bundle artifact --------
bundle_url=$(printf '%s' "$build_json" | python3 -c '
import json, sys, re
b = json.load(sys.stdin)
arts = b.get("artefacts") or []
# Prefer the explicit "bundle" type (sim-artifacts zip).
for a in arts:
    if a.get("type") == "bundle":
        print(a.get("url")); sys.exit(0)
# Fall back to anything named like *_artifacts.zip
for a in arts:
    n = a.get("name") or ""
    if re.search(r"_artifacts\.zip$", n):
        print(a.get("url")); sys.exit(0)
sys.stderr.write("no bundle artefact on this build\n"); sys.exit(1)
')

if [ -z "$bundle_url" ]; then
    echo "error: could not find a bundle artefact" >&2
    echo "all artefacts on this build:" >&2
    printf '%s' "$build_json" | python3 -c '
import json, sys
for a in (json.load(sys.stdin).get("artefacts") or []):
    print("  ", a.get("type"), a.get("name"), a.get("size"))' >&2
    exit 1
fi

outdir="/tmp/wf${build_idx}"
mkdir -p "$outdir"
zipfile="$outdir/artifacts.zip"
echo "→ $zipfile"
curl -sSfL -H "x-auth-token: $TOKEN" -o "$zipfile" "$bundle_url"

unzip -oq "$zipfile" -d "$outdir"
echo "extracted to: $outdir"
echo
echo "--- contents ---"
find "$outdir" -maxdepth 3 -type f -printf '%P  (%s bytes)\n' | sort

# --- helpful post-fetch summary ---
if [ -f "$outdir/sim-artifacts/wf.log" ]; then
    echo
    echo "--- wf.log tail (40 lines) ---"
    tail -40 "$outdir/sim-artifacts/wf.log"
fi

# Surface the .app / dSYM URLs so the caller can grab them if needed
printf '%s' "$build_json" | python3 -c '
import json, sys
arts = (json.load(sys.stdin).get("artefacts") or [])
extra = [a for a in arts if a.get("type") in ("app", "dsym")]
if extra:
    print()
    print("other artefacts (pass name via curl to download):")
    for a in extra:
        print("  %-5s %-30s %10d bytes  %s" % (
            a.get("type") or "",
            a.get("name") or "",
            a.get("size") or 0,
            a.get("url") or "",
        ))
'
