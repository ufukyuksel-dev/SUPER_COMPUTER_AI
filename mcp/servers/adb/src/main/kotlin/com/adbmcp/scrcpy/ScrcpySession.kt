package com.adbmcp.scrcpy

import java.time.Instant

data class ScrcpySession(
    val sessionId: String,
    val deviceSerial: String,
    val sessionType: SessionType,
    val process: Process,
    val startedAt: Instant,
    val outputPath: String? = null
)

enum class SessionType { MIRROR, RECORD }
