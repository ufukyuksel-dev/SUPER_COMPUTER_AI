package com.adbmcp.infrastructure

import org.springframework.boot.context.properties.ConfigurationProperties

@ConfigurationProperties(prefix = "adb")
data class AdbProperties(
    val path: String = "auto",
    val defaultTimeoutMs: Long = 30000,
    val videoTimeoutMs: Long = 180000
)
