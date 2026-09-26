plugins {
    id("org.jetbrains.kotlin.jvm") version "2.2.21"
    id("org.jetbrains.kotlin.plugin.spring") version "2.2.21"
    id("org.springframework.boot") version "3.5.10"
    id("io.spring.dependency-management") version "1.1.7"
}

group = "com.adbmcp"
version = "0.0.1-SNAPSHOT"

java {
    toolchain {
        languageVersion.set(JavaLanguageVersion.of(21))
    }
}

repositories {
    mavenCentral()
    maven { url = uri("https://repo.spring.io/milestone") }
}

dependencyManagement {
    imports {
        mavenBom("org.springframework.ai:spring-ai-bom:1.1.2")
        mavenBom("org.springframework.modulith:spring-modulith-bom:1.4.8")
    }
}

dependencies {
    // Spring AI MCP Server — both transports, profile selects which activates
    implementation("org.springframework.ai:spring-ai-starter-mcp-server")
    implementation("org.springframework.ai:spring-ai-starter-mcp-server-webflux")

    // Spring WebFlux (needed for SSE profile)
    implementation("org.springframework.boot:spring-boot-starter-webflux")

    // Spring Modulith
    implementation("org.springframework.modulith:spring-modulith-starter-core")

    // Kotlin
    implementation("org.jetbrains.kotlin:kotlin-reflect")

    // Jackson Kotlin module
    implementation("com.fasterxml.jackson.module:jackson-module-kotlin")

    // Test
    testImplementation("org.springframework.boot:spring-boot-starter-test")
    testImplementation("org.springframework.modulith:spring-modulith-starter-test")
    testImplementation("org.jetbrains.kotlin:kotlin-test-junit5")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}

kotlin {
    compilerOptions {
        freeCompilerArgs.addAll("-Xjsr305=strict")
    }
}

tasks.withType<Test> {
    useJUnitPlatform()
    // Hermetic: the Spring context writes artifacts and logs under build/, never into the checkout or ~/.local.
    systemProperty("adb-mcp.state-dir", layout.buildDirectory.dir("test-state").get().asFile.absolutePath)
}
