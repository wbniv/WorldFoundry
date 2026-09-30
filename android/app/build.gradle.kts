// Android app module — delegates native build to the repo-root CMakeLists.txt
// so Linux and Android share one build definition. AGP bundles the resulting
// libwf_game.so into the APK automatically.

plugins {
    id("com.android.application")
}

android {
    namespace = "org.worldfoundry.wf_game"
    compileSdk = 34
    ndkVersion = "26.2.11394342"

    defaultConfig {
        applicationId = "org.worldfoundry.wf_game"
        minSdk        = 21
        targetSdk     = 34
        versionCode   = 1
        versionName   = "0.1"

        ndk {
            // arm64 for phones and the Chromecast 4K, armeabi-v7a for the Chromecast HD: its SoC
            // (Amlogic S805X2) runs a 32-bit-only Android build (adb: ABIs armeabi-v7a,armeabi),
            // so an arm64-only APK cannot even be installed there (verified 2026-10-01).
            abiFilters += setOf("arm64-v8a", "armeabi-v7a")
        }
    }

    // One app per game, all from the same native library and Java glue
    // (docs/plans/2026-09-30-aquarium-chromecast.md). A flavor differs only in
    // its applicationId (so the apps install side by side), its assets/cd.iff
    // (src/<flavor>/assets/) and its launcher label, icons and TV banner
    // (src/<flavor>/res/ overriding src/main/res/). The native build config is
    // identical across flavors, so AGP configures and compiles CMake once per
    // build type and every flavor packages the same libwf_game.so.
    flavorDimensions += "game"
    productFlavors {
        create("snowgoons") {
            dimension = "game"
            // The original app: keeps the pre-flavor applicationId, label,
            // icon, banner (src/main/res) and the multi-level cd.iff.
        }
        create("aquarium") {
            dimension = "game"
            applicationIdSuffix = ".aquarium"   // org.worldfoundry.wf_game.aquarium
            versionNameSuffix   = "-aquarium"
        }
    }

    externalNativeBuild {
        cmake {
            path = file("../../CMakeLists.txt")
            version = "3.22.1+"
        }
    }

    buildTypes {
        getByName("debug") {
            // AGP's default: CMake passes -DCMAKE_BUILD_TYPE=Debug, which in
            // our CMakeLists maps to -O0 -g for the wf_game target.
            externalNativeBuild {
                cmake {
                    arguments += "-DCMAKE_BUILD_TYPE=Debug"
                }
            }
        }
        getByName("release") {
            isMinifyEnabled = false
            // Sideload-signed with the debug keystore so `task build-apk`
            // produces an installable APK without a real signing config.
            // Flip this back to true (and add a signingConfig) once we have
            // a distribution pipeline.
            signingConfig = signingConfigs.getByName("debug")
            isDebuggable = false
            externalNativeBuild {
                cmake {
                    // Full release: -O3 + thin LTO + section GC + ICF.
                    // See wf_game target's generator-expression flags in
                    // the repo-root CMakeLists.txt.
                    arguments += "-DCMAKE_BUILD_TYPE=Release"
                }
            }
        }
    }

    compileOptions {
        // Java code (LogViewerActivity) targets 1.8 — fine for minSdk 21.
        sourceCompatibility = JavaVersion.VERSION_1_8
        targetCompatibility = JavaVersion.VERSION_1_8
    }

    packaging {
        jniLibs {
            // Keep symbols until we have a real obfuscation/strip pipeline.
            useLegacyPackaging = true
        }
    }

    // Override the AGP default (app-<flavor>-debug.apk) so the file uploaded to
    // Drive and downloaded on the phone shows up as, e.g.,
    // "worldfoundry-aquarium-debug.apk" (in apk/<flavor>/<buildType>/).
    applicationVariants.all {
        val variant = this
        outputs.all {
            (this as com.android.build.gradle.internal.api.BaseVariantOutputImpl)
                .outputFileName = "worldfoundry-${variant.flavorName}-${variant.buildType.name}.apk"
        }
    }

    // Asset pipeline (Phase 3 step 5): Gradle bundles src/<flavor>/assets/
    // into that flavor's APK (src/main/assets/ is empty). Every asset is a
    // symlink to a tracked file:
    //   snowgoons: cd.iff → wfsource/source/game/cd.iff (task build-cd-iff),
    //     plus level0.mid + florestan-subset.sf2 — the loose MIDI + soundfont
    //     are a dev shortcut; the real remediation is docs/plans/2026-04-18-
    //     audio-assets-from-iff.md (move audio inside cd.iff).
    //   aquarium: cd.iff → wflevels/aquarium-cd.iff (task build-cd-iff-aquarium).
    //     No MIDI or soundfont: the level has no music, and MusicPlayer::play
    //     returns quietly when the soundfont asset is absent.
}
