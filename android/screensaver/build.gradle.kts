plugins {
    id("com.android.application")
}

// docs/plans/2026-11-21-aquarium-menu-and-screensaver-launch.md, Phase 2: one roster per package.
// A package that adds its own catalogue copies its manifest the same way, into its own flavor.
val aquariumCatalogAssets = layout.buildDirectory.dir("generated/levelCatalog/aquarium/assets")
val copyAquariumLevelCatalog by tasks.registering(Copy::class) {
    from(rootProject.file("../wflevels/aquarium-menu.manifest"))
    rename { "levels.manifest" }
    into(aquariumCatalogAssets)
}
// WF Clocks (docs/plans/2026-11-21-tide-harbour-clock.md): the same, from wflevels/clocks-menu.manifest.
// Test builds only (task build-clocks-two-entry-apk): -PwfClocksManifest=<manifest> and
// -PwfClocksAssets=<dir holding its cd.iff> replace the shipped roster and bundle for that build.
val clocksManifest = (findProperty("wfClocksManifest") as String?)?.let { file(it) }
    ?: rootProject.file("../wflevels/clocks-menu.manifest")
val clocksBundleAssets = (findProperty("wfClocksAssets") as String?)?.let { file(it) }
    ?: file("src/clocks/assets")
val clocksCatalogAssets = layout.buildDirectory.dir("generated/levelCatalog/clocks/assets")
val copyClocksLevelCatalog by tasks.registering(Copy::class) {
    from(clocksManifest)
    rename { "levels.manifest" }
    into(clocksCatalogAssets)
}

android {
    namespace = "org.worldfoundry.screensaver"
    compileSdk = 34
    ndkVersion = "26.2.11394342"

    defaultConfig {
        minSdk = 21
        targetSdk = 34
        ndk {
            abiFilters += setOf("arm64-v8a", "armeabi-v7a")
        }
    }

    flavorDimensions += "dream"
    productFlavors {
        create("aquarium") {
            dimension = "dream"
            applicationId = "org.worldfoundry.game.aquarium"   // org.worldfoundry.game.{{name}}, Will 2026-11-22 (was org.worldfoundry.screensaver)
            versionCode = 4
            versionName = "0.4"
        }
        create("seahorse") {
            dimension = "dream"
            applicationId = "org.worldfoundry.seahorsegrid"
            versionCode = 1
            versionName = "0.1"
        }
        create("clocks") {                 // WF Clocks: every clock of wflevels/clocks-menu.manifest
            dimension = "dream"
            applicationId = "org.worldfoundry.game.clocks"
            versionCode = 1
            versionName = "0.1"
        }
        create("tidespike") {              // Tide Harbour Phase 0 spike: throwaway, one APK for four levels
            dimension = "dream"
            applicationId = "org.worldfoundry.tidespike"
            versionCode = 1
            versionName = "0.1"
        }
        create("planted") {
            dimension = "dream"
            applicationId = "org.worldfoundry.plantedtank"
            versionCode = 1
            versionName = "0.1"
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
            externalNativeBuild {
                cmake {
                    arguments += "-DCMAKE_PROJECT_wf_game_INCLUDE=${projectDir}/dream-project-hook.cmake"
                    targets += "wf_dream"
                }
            }
        }
        getByName("release") {
            // As the game app's release (android/app/build.gradle.kts): signed with the
            // debug keystore so it installs by sideload, not debuggable, and the native
            // code built as CMake Release (-O3 + thin LTO for wfengine, Jolt and zforth).
            // A Debug Dream ran the reef at about 3 FPS on cast1 (2026-11-09).
            signingConfig = signingConfigs.getByName("debug")
            isDebuggable = false
            externalNativeBuild {
                cmake {
                    arguments += "-DCMAKE_PROJECT_wf_game_INCLUDE=${projectDir}/dream-project-hook.cmake"
                    arguments += "-DCMAKE_BUILD_TYPE=Release"
                    targets += "wf_dream"
                }
            }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_1_8
        targetCompatibility = JavaVersion.VERSION_1_8
    }

    // The aquarium flavor's level roster: wflevels/aquarium-menu.manifest, copied (never checked
    // in twice) into generated assets as levels.manifest, which LevelCatalog reads at runtime.
    sourceSets.getByName("aquarium").assets.srcDir(aquariumCatalogAssets)
    sourceSets.getByName("clocks").assets.setSrcDirs(listOf(clocksBundleAssets, clocksCatalogAssets))
}

tasks.named("preBuild") { dependsOn(copyAquariumLevelCatalog, copyClocksLevelCatalog) }
