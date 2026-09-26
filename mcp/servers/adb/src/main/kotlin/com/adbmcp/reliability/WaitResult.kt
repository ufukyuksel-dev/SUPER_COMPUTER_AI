package com.adbmcp.reliability

import com.adbmcp.inspection.UiElement

data class WaitForActivityResult(
    val success: Boolean,
    val timedOut: Boolean,
    val currentActivity: String?,
    val elapsedMs: Long
)

data class WaitForElementResult(
    val success: Boolean,
    val timedOut: Boolean,
    val element: UiElement? = null,
    val elapsedMs: Long
)

data class DeviceReadyResult(
    val success: Boolean,
    val responseTimeMs: Long,
    val error: String? = null
)
