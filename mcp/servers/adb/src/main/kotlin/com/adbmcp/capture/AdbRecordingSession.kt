package com.adbmcp.capture

import java.time.Instant

data class AdbRecordingSession(
    val recordingId: String,
    val deviceSerial: String,
    val process: Process,
    val deviceFilePath: String,
    val startedAt: Instant,
    val maxDurationSeconds: Int = 180
)

data class StartVideoResult(
    val success: Boolean,
    val recordingId: String? = null,
    val error: String? = null,
    val errorCode: String? = null
)

data class StopVideoResult(
    val success: Boolean,
    val artifactPath: String? = null,
    val durationSeconds: Long? = null,
    val error: String? = null,
    val errorCode: String? = null
)
