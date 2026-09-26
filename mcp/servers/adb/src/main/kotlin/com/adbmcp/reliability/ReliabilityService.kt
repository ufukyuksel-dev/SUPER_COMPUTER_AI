package com.adbmcp.reliability

import com.adbmcp.infrastructure.AdbExecutor
import com.adbmcp.infrastructure.DeviceResolver
import com.adbmcp.inspection.UiInspectionPort
import com.adbmcp.intent.IntentPort
import org.springframework.stereotype.Service

@Service
class ReliabilityService(
    private val intentPort: IntentPort,
    private val uiInspectionPort: UiInspectionPort,
    private val deviceResolver: DeviceResolver,
    private val adbExecutor: AdbExecutor
) {
    companion object {
        private const val POLL_INTERVAL_MS = 500L
        private const val DEFAULT_TIMEOUT_MS = 10000
        private const val MAX_TIMEOUT_MS = 60000
    }

    fun waitForActivity(
        activityName: String,
        timeoutMs: Int = DEFAULT_TIMEOUT_MS,
        deviceSerial: String? = null
    ): WaitForActivityResult {
        val serial = deviceResolver.resolve(deviceSerial)
        val clampedTimeout = timeoutMs.coerceIn(1000, MAX_TIMEOUT_MS)
        val startTime = System.currentTimeMillis()

        while (System.currentTimeMillis() - startTime < clampedTimeout) {
            val current = intentPort.currentActivity(serial)
            if (current.contains(activityName, ignoreCase = true)) {
                return WaitForActivityResult(
                    success = true,
                    timedOut = false,
                    currentActivity = current,
                    elapsedMs = System.currentTimeMillis() - startTime
                )
            }
            Thread.sleep(POLL_INTERVAL_MS)
        }

        val lastActivity = try { intentPort.currentActivity(serial) } catch (_: Exception) { null }
        return WaitForActivityResult(
            success = false,
            timedOut = true,
            currentActivity = lastActivity,
            elapsedMs = System.currentTimeMillis() - startTime
        )
    }

    fun waitForElement(
        text: String? = null,
        resourceId: String? = null,
        className: String? = null,
        contentDesc: String? = null,
        testTag: String? = null,
        timeoutMs: Int = DEFAULT_TIMEOUT_MS,
        deviceSerial: String? = null
    ): WaitForElementResult {
        require(text != null || resourceId != null || className != null || contentDesc != null || testTag != null) {
            "At least one search criteria must be provided"
        }

        val serial = deviceResolver.resolve(deviceSerial)
        val clampedTimeout = timeoutMs.coerceIn(1000, MAX_TIMEOUT_MS)
        val startTime = System.currentTimeMillis()

        while (System.currentTimeMillis() - startTime < clampedTimeout) {
            try {
                val result = uiInspectionPort.findElement(serial, text, resourceId, className, contentDesc, testTag, 0)
                if (result.found && result.element != null) {
                    return WaitForElementResult(
                        success = true,
                        timedOut = false,
                        element = result.element,
                        elapsedMs = System.currentTimeMillis() - startTime
                    )
                }
            } catch (_: Exception) {
                // UI dump can fail transiently, continue polling
            }
            Thread.sleep(POLL_INTERVAL_MS)
        }

        return WaitForElementResult(
            success = false,
            timedOut = true,
            elapsedMs = System.currentTimeMillis() - startTime
        )
    }

    fun deviceReady(deviceSerial: String? = null): DeviceReadyResult {
        val startTime = System.currentTimeMillis()
        return try {
            val serial = deviceResolver.resolve(deviceSerial)
            val result = adbExecutor.execute(serial, "shell", "echo", "ok", timeoutMs = 5000)
            DeviceReadyResult(
                success = result.isSuccess && result.stdout.trim() == "ok",
                responseTimeMs = System.currentTimeMillis() - startTime
            )
        } catch (e: Exception) {
            DeviceReadyResult(
                success = false,
                responseTimeMs = System.currentTimeMillis() - startTime,
                error = e.message
            )
        }
    }
}
