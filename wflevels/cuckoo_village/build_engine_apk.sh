#!/usr/bin/env bash
# Build the Minute Machine flavor APK from this branch's current engine (it has the wall-clock mailboxes and the
# Forth math words), as the host for the Cuckoo Village test APK (build_device_apk.sh swaps in the level).
#   bash wflevels/cuckoo_village/build_engine_apk.sh        # about 10 minutes, about 1 GB
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
./gradlew --no-daemon :screensaver:assembleMinutemachineRelease
ls -l screensaver/build/outputs/apk/minutemachine/release/*.apk
