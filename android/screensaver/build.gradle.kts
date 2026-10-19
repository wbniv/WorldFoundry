plugins {
    id("com.android.application")
}

android {
    namespace = "org.worldfoundry.screensaver"
    compileSdk = 34
    ndkVersion = "26.2.11394342"

    defaultConfig {
        applicationId = "org.worldfoundry.screensaver"
        minSdk = 21
        targetSdk = 34
        versionCode = 2
        versionName = "0.2"
        ndk {
            abiFilters += setOf("arm64-v8a", "armeabi-v7a")
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
            externalNativeBuild {
                cmake {
                    arguments += "-DCMAKE_PROJECT_wf_game_INCLUDE=${projectDir}/dream-project-hook.cmake"
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
