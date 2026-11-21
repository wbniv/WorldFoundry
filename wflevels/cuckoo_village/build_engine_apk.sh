#!/usr/bin/env bash
# Build a screensaver flavor APK from this branch's engine (it has the wall-clock mailboxes and the Forth math words).
# FLAVOR defaults to clocks: the WF Clocks package, whose bundle (scripts/pack-clocks-bundle.py) holds Cuckoo Village.
#   [FLAVOR=clocks] bash wflevels/cuckoo_village/build_engine_apk.sh        # about 10 minutes, about 1 GB
set -euo pipefail
case "${1:-}" in
    -h|--help) sed -n '2,5p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
esac
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MAIN=/home/will/WorldFoundry-wbniv
cd "$ROOT"
printf 'sdk.dir=/home/will/android-sdk-local\n' > android/local.properties          # gitignored
[[ -d engine/vendor/jolt-physics-5.5.0 ]] || cp -r "$MAIN/engine/vendor/jolt-physics-5.5.0" engine/vendor/   # gitignored, extracted tree
export ANDROID_HOME=/home/will/android-sdk-local
cd android
FLAVOR="${FLAVOR:-clocks}"
./gradlew --no-daemon ":screensaver:assemble${FLAVOR^}Release"
ls -l "screensaver/build/outputs/apk/${FLAVOR}/release/"*.apk
