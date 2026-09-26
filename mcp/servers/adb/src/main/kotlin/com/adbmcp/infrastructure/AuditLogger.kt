package com.adbmcp.infrastructure

import org.slf4j.LoggerFactory
import org.springframework.stereotype.Component

@Component
class AuditLogger {

    private val logger = LoggerFactory.getLogger("AUDIT")

    fun log(
        toolName: String,
        deviceSerial: String?,
        parameters: Map<String, Any?>,
        resultStatus: String,
        durationMs: Long
    ) {
        val maskedParams = parameters.mapValues { (key, value) ->
            if (key == "text" && value is String && value.length > 3) {
                value.take(3) + "***"
            } else {
                value
            }
        }

        logger.info(
            "tool={} device={} params={} status={} duration={}ms",
            toolName,
            deviceSerial ?: "auto",
            maskedParams,
            resultStatus,
            durationMs
        )
    }
}
