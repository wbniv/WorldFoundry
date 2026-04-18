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

    // Asset pipeline (Phase 3 step 5): bundle cd.iff under assets/. For now
    // the packaged APK ships no assets — sideload cd.iff to
    // /data/local/tmp/wf/cd.iff and start the engine from that working dir.
}
