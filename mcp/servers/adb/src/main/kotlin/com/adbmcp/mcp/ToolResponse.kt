package com.adbmcp.mcp

import com.adbmcp.infrastructure.AdbException
import com.fasterxml.jackson.databind.ObjectMapper

object ToolResponse {
    private val objectMapper = ObjectMapper().findAndRegisterModules()

    fun success(data: Any): String = objectMapper.writeValueAsString(data)

    fun error(e: AdbException): String = objectMapper.writeValueAsString(
        mapOf(
            "success" to false,
            "error" to e.message,
            "errorCode" to e.errorCode.name
        )
    )

    fun error(message: String, errorCode: String? = null): String = objectMapper.writeValueAsString(
        mapOf(
            "success" to false,
            "error" to message,
            "errorCode" to errorCode
        )
    )
}
