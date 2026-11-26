#!/usr/bin/env bash
# Build the throwaway lava lamp device APK (package org.worldfoundry.lavaspike, the tidespike activities): pack the
# standalone level as level 0 of a bundle and run Gradle offline. docs/plans/2026-11-26-lava-lamp.md, Phase 0 and 6.
set -euo pipefail
case "${1:-}" in
    -h|--help) echo "Usage: bash wflevels/lava_lamp/device_apk.sh   (build the level first; output: android/screensaver/build/outputs/apk/lavaspike/release/)"; exit 0 ;;
esac
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
mkdir -p android/screensaver/build/lavaspike-assets build-docker/lava-lamp
scripts/in-linux-container.sh bash -c 'set -euo pipefail; cargo build --release --quiet --manifest-path wftools/cdpack-rs/Cargo.toml
  wftools/cdpack-rs/target/release/cdpack wfsource/source/game/shell.fth wflevels/lava_lamp-standalone.iff -o /build/lava-lamp/lavaspike-cd.iff'
cp build-docker/lava-lamp/lavaspike-cd.iff android/screensaver/build/lavaspike-assets/cd.iff
cd android
ANDROID_HOME="${ANDROID_HOME:-/home/will/android-sdk-local}" ./gradlew :screensaver:assembleLavaspikeRelease --offline
unzip -l screensaver/build/outputs/apk/lavaspike/release/screensaver-lavaspike-release.apk | grep -E 'lib/armeabi-v7a/libwf_dream.so|assets/cd.iff'
