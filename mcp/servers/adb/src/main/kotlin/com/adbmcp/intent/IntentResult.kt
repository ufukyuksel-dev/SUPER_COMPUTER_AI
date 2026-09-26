package com.adbmcp.intent

import com.adbmcp.infrastructure.ErrorCode

data class IntentResult(
    val success: Boolean,
    val output: String? = null,
    val error: String? = null,
    val errorCode: ErrorCode? = null
)
