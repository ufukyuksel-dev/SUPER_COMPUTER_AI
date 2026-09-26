package com.adbmcp.input

import com.adbmcp.infrastructure.ErrorCode

data class CommandResult(
    val success: Boolean,
    val error: String? = null,
    val errorCode: ErrorCode? = null
)

data class TapResult(
    val success: Boolean,
    val x: Int,
    val y: Int,
    val error: String? = null
)

data class SwipeResult(
    val success: Boolean,
    val x1: Int,
    val y1: Int,
    val x2: Int,
    val y2: Int,
    val durationMs: Int,
    val error: String? = null
)

data class ImeInfo(
    val imeId: String,
    val label: String? = null
)
