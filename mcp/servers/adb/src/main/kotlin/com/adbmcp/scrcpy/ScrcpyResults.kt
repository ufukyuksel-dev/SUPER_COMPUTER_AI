package com.adbmcp.scrcpy

import java.time.Instant

data class ScrcpyStartResult(
    val success: Boolean,
    val sessionId: String? = null,
    val error: String? = null,
    val errorCode: String? = null
)

data class ScrcpyStopResult(
    val success: Boolean,
    val outputPath: String? = null,
    val durationSeconds: Long? = null,
    val error: String? = null,
    val errorCode: String? = null
)

data class ScrcpyConnectResult(
    val success: Boolean,
    val deviceSerial: String? = null,
    val error: String? = null,
    val errorCode: String? = null
)

data class ScrcpyStatusResult(
    val success: Boolean,
    val sessions: List<ScrcpySessionInfo>? = null,
    val session: ScrcpySessionInfo? = null,
    val error: String? = null,
    val errorCode: String? = null
)

data class ScrcpySessionInfo(
    val sessionId: String,
    val deviceSerial: String,
    val sessionType: SessionType,
    val startedAt: Instant,
    val durationSeconds: Long,
    val outputPath: String? = null
)
