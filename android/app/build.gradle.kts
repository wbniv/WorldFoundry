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

        externalNativeBuild {
            cmake {
                arguments += "-DCMAKE_BUILD_TYPE=RelWithDebInfo"
            }
        }
        ndk {
            // arm64 only — the port plan's settled decision.
            abiFilters += setOf("arm64-v8a")
        }
    }

    externalNativeBuild {
        cmake {
            path = file("../../CMakeLists.txt")
            version = "3.22.1+"
        }
    }

    buildTypes {
        getByName("release") {
            isMinifyEnabled = false
            // Debuggable until we have a real signing config.
            isDebuggable = true
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

    // Override the AGP default (app-debug.apk) so the file uploaded to Drive
    // and downloaded on the phone shows up as "worldfoundry-debug.apk".
    applicationVariants.all {
        val variant = this
        outputs.all {
            (this as com.android.build.gradle.internal.api.BaseVariantOutputImpl)
                .outputFileName = "worldfoundry-${variant.buildType.name}.apk"
        }
    }

    // Asset pipeline (Phase 3 step 5): Gradle bundles src/main/assets/ into
    // the APK. Transitional layout: three symlinks into wfsource/source/game/
    // (cd.iff + level0.mid + florestan-subset.sf2) — the loose MIDI + soundfont
    // are a dev shortcut. Real remediation is docs/plans/2026-04-18-audio-
    // assets-from-iff.md: move audio inside cd.iff so only cd.iff ships.
}
