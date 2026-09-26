package com.adbmcp.mcp

import com.adbmcp.capture.CaptureService
import com.adbmcp.device.DeviceService
import com.adbmcp.infrastructure.AdbException
import com.adbmcp.infrastructure.AuditLogger
import org.springframework.ai.tool.annotation.Tool
import org.springframework.ai.tool.annotation.ToolParam
import org.springframework.stereotype.Service

@Service
class CaptureTools(
    private val captureService: CaptureService,
    private val deviceService: DeviceService,
    private val auditLogger: AuditLogger
) {
    @Tool(description = "Capture device screen, save PNG under artifacts/screenshots, and return the artifact path")
    fun screenshot(
        @ToolParam(description = "Scale factor 0.1-1.0 (default 1.0). Client must multiply coordinates back to original resolution.") scale: Float? = null,
        @ToolParam(description = "Device serial (optional)") deviceSerial: String? = null
    ): String {
        val start = System.currentTimeMillis()
        val actualScale = (scale ?: 1.0f).coerceIn(0.1f, 1.0f)
        return try {
            val resolvedSerial = deviceService.resolveWithSessionHint(deviceSerial)
            val result = captureService.screenshot(actualScale, resolvedSerial)
            auditLogger.log("screenshot", resolvedSerial, mapOf("scale" to actualScale), "success", System.currentTimeMillis() - start)
            ToolResponse.success(mapOf(
                "success" to true,
                "artifactPath" to result.artifactPath
            ))
        } catch (e: AdbException) {
            auditLogger.log("screenshot", deviceSerial, mapOf("scale" to actualScale), "error", System.currentTimeMillis() - start)
            ToolResponse.error(e)
        }
    }

    @Tool(description = "Start screen recording (max 180s, no audio). Returns recordingId for stop_video.")
    fun start_video(
        @ToolParam(description = "Device serial (optional)") deviceSerial: String? = null
    ): String {
        val start = System.currentTimeMillis()
        return try {
            val resolvedSerial = deviceService.resolveWithSessionHint(deviceSerial)
            val result = captureService.startVideo(resolvedSerial)
            auditLogger.log("start_video", resolvedSerial, emptyMap(), "success", System.currentTimeMillis() - start)
            ToolResponse.success(result)
        } catch (e: AdbException) {
            auditLogger.log("start_video", deviceSerial, emptyMap(), "error", System.currentTimeMillis() - start)
            ToolResponse.error(e)
        }
    }

    @Tool(description = "Stop screen recording by recordingId, return artifact path")
    fun stop_video(
        @ToolParam(description = "Recording ID returned by start_video") recordingId: String,
        @ToolParam(description = "Device serial (optional)") deviceSerial: String? = null
    ): String {
        val start = System.currentTimeMillis()
        return try {
            val result = captureService.stopVideo(recordingId)
            auditLogger.log("stop_video", deviceSerial, mapOf("recordingId" to recordingId), "success", System.currentTimeMillis() - start)
            ToolResponse.success(result)
        } catch (e: AdbException) {
            auditLogger.log("stop_video", deviceSerial, mapOf("recordingId" to recordingId), "error", System.currentTimeMillis() - start)
            ToolResponse.error(e)
        }
    }
}
