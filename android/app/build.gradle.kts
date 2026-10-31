plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "io.scrollbreaker.capture"
    compileSdk = 35

    defaultConfig {
        applicationId = "io.scrollbreaker.capture"
        // AccessibilityService.takeScreenshot() is API 30+. There is no fallback:
        // MediaProjection would need a consent dialog per session, which defeats
        // the point of an unattended capture loop.
        minSdk = 30
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    // No signing config here on purpose. Build a debug APK yourself, or provide
    // your own keystore — never commit one.
}

dependencies {
    // Intentionally empty: org.json and HttpURLConnection ship with Android.
    // Fewer dependencies is the whole point of this app.
}
