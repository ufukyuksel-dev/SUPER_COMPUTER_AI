package com.adbmcp.file

data class PushFileResult(
    val success: Boolean,
    val devicePath: String? = null,
    val error: String? = null,
    val errorCode: String? = null
)

data class PullFileResult(
    val success: Boolean,
    val artifactPath: String? = null,
    val error: String? = null,
    val errorCode: String? = null
)
