#!/usr/bin/env bash
set -euo pipefail
# usage: step2.sh REV — build the aquarium APK (armeabi-v7a, versionCode 70, not testOnly) at REV in
# ~/wf-bisect and make that revision's own pair6 fixture from it (its own cd.iff and wf_args).
W=/home/will/wf-bisect; B=/home/will/WorldFoundry-wbniv/build-docker/bisect
git -C "$W" checkout -q --detach "$1"
rev=$(git -C "$W" rev-parse --short=8 HEAD)
sed -i 's/versionCode   = 7 /versionCode   = 70 /' "$W/android/app/build.gradle.kts"
# PATCH=nosel: disable the no-palette program selection (a86f420b) so a second bisect sees only later costs.
F=$W/wfsource/source/gfx/glpipeline/backend_modern.cc
if [ "${PATCH:-}" = nosel ]; then
    sed -i 's/const bool noPalette = opaqueTex \&\& _batchPaletteKinds == kBatchOrdinary;/const bool noPalette = false \&\& opaqueTex \&\& _batchPaletteKinds == kBatchOrdinary;/' "$F"
fi
status=0
skip=()
# Later trees check the APK's page alignment at outputs/apk/, which an injected-ABI build does not write.
grep -q PageAlignment "$W/android/app/build.gradle.kts" && skip=(-x verifyAquariumReleaseApkPageAlignment)
( cd "$W/android" && ./gradlew :app:assembleAquariumRelease -Pandroid.injected.build.abi=armeabi-v7a \
    -Pandroid.injected.testOnly=false "${skip[@]}" --offline -q ) > "$B/build-$rev.log" 2>&1 || status=$?
git -C "$W" checkout -q -- android/app/build.gradle.kts wfsource/source/gfx/glpipeline/backend_modern.cc
[ "$status" = 0 ] || { echo "build failed at $rev (see $B/build-$rev.log)" >&2; exit 1; }
apk=$W/android/app/build/intermediates/apk/aquarium/release/worldfoundry-aquarium-release.apk
rm -rf "$B/p6-$rev"
( cd "$W" && python3 scripts/build-planted-seahorse-variants.py --base-apk "$apk" --out "$B/p6-$rev" --variants pair6 ) >> "$B/build-$rev.log" 2>&1
echo "$B/p6-$rev/pair6.apk"
