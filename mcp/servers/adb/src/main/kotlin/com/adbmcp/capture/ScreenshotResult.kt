package com.adbmcp.capture

data class ScreenshotResult(
    val imageBytes: ByteArray,
    val width: Int,
    val height: Int,
    val rotation: Int,
    val timestamp: Long,
    val artifactPath: String? = null
)
