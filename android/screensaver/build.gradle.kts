plugins {
    id("com.android.application")
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
            applicationId = "org.worldfoundry.screensaver"
            versionCode = 3
            versionName = "0.3"
        }
        create("seahorse") {
            dimension = "dream"
            applicationId = "org.worldfoundry.seahorsegrid"
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
}
