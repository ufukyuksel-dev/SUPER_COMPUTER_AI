package com.adbmcp.infrastructure

import org.springframework.boot.context.properties.ConfigurationProperties

@ConfigurationProperties(prefix = "artifacts")
data class ArtifactProperties(
    val baseDir: String = "./artifacts",
    val screenshotsDir: String = "screenshots",
    val videosDir: String = "videos",
    val uiDumpsDir: String = "ui-dumps",
    val pulledFilesDir: String = "pulled",
    val maxAgeHours: Int = 24,
    val maxTotalSizeMb: Long = 2048
)
