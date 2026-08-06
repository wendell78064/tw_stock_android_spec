plugins {
    id("com.android.application") version "8.7.3" apply false
    id("com.android.library") version "8.7.3" apply false
    id("org.jetbrains.kotlin.android") version "2.0.21" apply false
    id("org.jetbrains.kotlin.plugin.compose") version "2.0.21" apply false
    id("com.google.dagger.hilt.android") version "2.52" apply false
    id("com.google.devtools.ksp") version "2.0.21-1.0.28" apply false
    id("org.openapi.generator") version "7.13.0"
}

openApiValidate {
    inputSpec.set("${rootDir}/../api/openapi.yaml")
}

openApiGenerate {
    generatorName.set("kotlin")
    inputSpec.set("${rootDir}/../api/openapi.yaml")
    outputDir.set("${layout.buildDirectory.get()}/generated/openapi")
    packageName.set("tw.market.ledger.generated")
    modelPackage.set("tw.market.ledger.generated.model")
    apiPackage.set("tw.market.ledger.generated.api")
    configOptions.set(mapOf("library" to "jvm-retrofit2", "serializationLibrary" to "moshi"))
}

