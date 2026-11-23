#!/usr/bin/env bash
# Test APK: the Minute Machine APK (it carries the wall-clock engine) with assets/cd.iff replaced by the
# Cuckoo Village level, re-aligned and signed with the debug key. Not a release; see the plan for the real package.
#   bash wflevels/cuckoo_village/build_device_apk.sh
set -euo pipefail
case "${1:-}" in
    -h|--help) sed -n '2,4p' "$0" | sed 's/^# \{0,1\}//'; echo "Env: BASE_APK, OUT_DIR, WF_CDPACK, ANDROID_BUILD_TOOLS"; exit 0 ;;
esac
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
MAIN=/home/will/WorldFoundry-wbniv
TOOLS="${ANDROID_BUILD_TOOLS:-/home/will/android-sdk-local/build-tools/34.0.0}"
BASE_APK="${BASE_APK:-$MAIN/build/coordinator-artifacts/minute-machine-2026-11-21/minute-machine-cardfix.apk}"
OUT_DIR="${OUT_DIR:-$MAIN/build/coordinator-artifacts/cuckoo-village-2026-11-21}"
CDPACK="${WF_CDPACK:-$MAIN/wftools/cdpack-rs/target/release/cdpack}"
LEVEL="$ROOT/wflevels/cuckoo_village-standalone.iff"
WORK="$(mktemp -d)"
mkdir -p "$OUT_DIR"
"$CDPACK" wfsource/source/game/shell.fth "$LEVEL" -o "$WORK/cd.iff"
python3 -I - "$BASE_APK" "$WORK" <<'PY'
from pathlib import Path
from zipfile import ZipFile
import sys
src = Path(sys.argv[1]); out = Path(sys.argv[2]); level = (out / 'cd.iff').read_bytes(); count = 0
with ZipFile(src) as a, ZipFile(out / 'unsigned.apk', 'w') as b:
    for entry in a.infolist():
        if entry.filename.startswith('META-INF/') and entry.filename.upper().endswith(('.RSA', '.DSA', '.EC', '.SF', 'MANIFEST.MF')):
            continue
        if entry.filename == 'assets/cd.iff':
            count += 1; payload = level
        else:
            payload = a.read(entry.filename)
        b.writestr(entry, payload)
assert count == 1, count
PY
"$TOOLS/zipalign" -p -f 4 "$WORK/unsigned.apk" "$WORK/aligned.apk"
"$TOOLS/apksigner" sign --ks "$HOME/.android/debug.keystore" --ks-key-alias androiddebugkey --ks-pass pass:android --key-pass pass:android --out "$OUT_DIR/cuckoo-village.apk" "$WORK/aligned.apk"
"$TOOLS/apksigner" verify "$OUT_DIR/cuckoo-village.apk"
sha256sum "$OUT_DIR/cuckoo-village.apk" "$BASE_APK"
rm -rf "$WORK"
