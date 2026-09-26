package com.adbmcp.scrcpy

import org.springframework.boot.context.properties.ConfigurationProperties

@ConfigurationProperties(prefix = "scrcpy")
data class ScrcpyProperties(
    val path: String = "auto",
    val defaultMaxSize: Int = 1024,
    val defaultVideoBitRate: String = "8M",
    val recordingDir: String = "./artifacts/videos"
)
