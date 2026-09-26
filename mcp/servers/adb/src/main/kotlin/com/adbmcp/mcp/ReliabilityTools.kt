package com.adbmcp.mcp

import com.adbmcp.device.DeviceService
import com.adbmcp.infrastructure.AdbException
import com.adbmcp.infrastructure.AuditLogger
import com.adbmcp.reliability.ReliabilityService
import org.springframework.ai.tool.annotation.Tool
import org.springframework.ai.tool.annotation.ToolParam
import org.springframework.stereotype.Service

@Service
class ReliabilityTools(
    private val reliabilityService: ReliabilityService,
    private val deviceService: DeviceService,
    private val auditLogger: AuditLogger
) {
    @Tool(description = "Block until specified activity is in foreground (or timeout). Returns success/timedOut, not error on timeout.")
    fun wait_for_activity(
        @ToolParam(description = "Full or partial activity name to wait for") activityName: String,
        @ToolParam(description = "Max wait time in ms (default 10000, max 60000)") timeoutMs: Int? = null,
        @ToolParam(description = "Device serial (optional)") deviceSerial: String? = null
    ): String {
        val start = System.currentTimeMillis()
        return try {
            val resolvedSerial = deviceService.resolveWithSessionHint(deviceSerial)
            val result = reliabilityService.waitForActivity(activityName, timeoutMs ?: 10000, resolvedSerial)
            auditLogger.log("wait_for_activity", resolvedSerial, mapOf("activityName" to activityName, "timeoutMs" to timeoutMs), "success", System.currentTimeMillis() - start)
            ToolResponse.success(result)
        } catch (e: AdbException) {
            auditLogger.log("wait_for_activity", deviceSerial, mapOf("activityName" to activityName), "error", System.currentTimeMillis() - start)
            ToolResponse.error(e)
        }
    }

    @Tool(description = "Block until UI element matching criteria appears (or timeout). Poll uiautomator every 500ms. Supports Jetpack Compose via testTag parameter.")
    fun wait_for_element(
        @ToolParam(description = "Match by text") text: String? = null,
        @ToolParam(description = "Match by resource-id") resourceId: String? = null,
        @ToolParam(description = "Match by class name") className: String? = null,
        @ToolParam(description = "Match by content-description") contentDesc: String? = null,
        @ToolParam(description = "Match by Compose testTag (Modifier.testTag)") testTag: String? = null,
        @ToolParam(description = "Max wait time in ms (default 10000, max 60000)") timeoutMs: Int? = null,
        @ToolParam(description = "Device serial (optional)") deviceSerial: String? = null
    ): String {
        val start = System.currentTimeMillis()
        return try {
            val resolvedSerial = deviceService.resolveWithSessionHint(deviceSerial)
            val result = reliabilityService.waitForElement(text, resourceId, className, contentDesc, testTag, timeoutMs ?: 10000, resolvedSerial)
            auditLogger.log("wait_for_element", resolvedSerial, mapOf("text" to text, "resourceId" to resourceId), "success", System.currentTimeMillis() - start)
            ToolResponse.success(result)
        } catch (e: Exception) {
            auditLogger.log("wait_for_element", deviceSerial, mapOf("text" to text), "error", System.currentTimeMillis() - start)
            if (e is AdbException) ToolResponse.error(e)
            else ToolResponse.error(e.message ?: "Unknown error")
        }
    }

    @Tool(description = "Quick check: is device online and ADB responsive?")
    fun device_ready(
        @ToolParam(description = "Device serial (optional)") deviceSerial: String? = null
    ): String {
        val start = System.currentTimeMillis()
        return try {
            val resolvedSerial = deviceService.resolveWithSessionHint(deviceSerial)
            val result = reliabilityService.deviceReady(resolvedSerial)
            auditLogger.log("device_ready", resolvedSerial, emptyMap(), if (result.success) "success" else "error", System.currentTimeMillis() - start)
            ToolResponse.success(result)
        } catch (e: AdbException) {
            auditLogger.log("device_ready", deviceSerial, emptyMap(), "error", System.currentTimeMillis() - start)
            ToolResponse.error(e)
        }
    }
}
