plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("com.google.dagger.hilt.android")
    id("com.google.devtools.ksp")
}

android {
    namespace = "tw.market.ledger"
    compileSdk = 35

    defaultConfig {
        applicationId = "tw.market.ledger"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        buildConfigField("String", "API_BASE_URL", "\"http://10.0.2.2:8000/v1/\"")
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}

dependencies {
    implementation(project(":core-ui"))
    implementation(project(":core-network"))
    implementation(project(":core-database"))
    implementation(project(":feature-market"))
    implementation(project(":feature-security"))
    implementation(project(":feature-portfolio"))
    implementation(project(":feature-watchlist"))
    implementation(project(":feature-alert"))
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("androidx.compose.material3:material3:1.3.2")
    implementation("androidx.hilt:hilt-navigation-compose:1.2.0")
    implementation("androidx.navigation:navigation-compose:2.8.7")
    implementation("androidx.room:room-runtime:2.6.1")
    implementation("com.squareup.retrofit2:retrofit:2.11.0")
    implementation("com.squareup.retrofit2:converter-moshi:2.11.0")
    implementation("com.squareup.moshi:moshi-kotlin:1.15.2")
    implementation("com.google.dagger:hilt-android:2.52")
    ksp("com.google.dagger:hilt-compiler:2.52")
    debugImplementation("androidx.compose.ui:ui-test-manifest:1.7.8")
    androidTestImplementation("androidx.compose.ui:ui-test-junit4:1.7.8")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
}
