pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}
rootProject.name = "TWMarketLedger"
include(":app", ":core-model", ":core-network", ":core-database", ":core-ui", ":feature-market", ":feature-security", ":feature-portfolio")
