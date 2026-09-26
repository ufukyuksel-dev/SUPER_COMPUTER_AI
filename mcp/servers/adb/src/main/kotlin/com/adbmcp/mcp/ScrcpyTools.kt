package com.adbmcp.mcp

import com.adbmcp.device.DeviceService
import com.adbmcp.infrastructure.AdbException
import com.adbmcp.infrastructure.AuditLogger
import com.adbmcp.scrcpy.ScrcpyService
import org.springframework.ai.tool.annotation.Tool
import org.springframework.ai.tool.annotation.ToolParam
import org.springframework.stereotype.Service

@Service
class ScrcpyTools(
    private val scrcpyService: ScrcpyService,
    private val deviceService: DeviceService,
    private val auditLogger: AuditLogger
) {
    @Tool(description = "Start live scrcpy mirror session. Returns sessionId.")
    fun scrcpy_start_mirror(
        @ToolParam(description = "Device serial (optional)") deviceSerial: String? = null
    ): String {
        val start = System.currentTimeMillis()
        return try {
            val resolvedSerial = deviceService.resolveWithSessionHint(deviceSerial)
            val result = scrcpyService.startMirror(resolvedSerial)
            auditLogger.log("scrcpy_start_mirror", resolvedSerial, emptyMap(), "success", System.currentTimeMillis() - start)
            ToolResponse.success(result)
        } catch (e: AdbException) {
            auditLogger.log("scrcpy_start_mirror", deviceSerial, emptyMap(), "error", System.currentTimeMillis() - start)
            ToolResponse.error(e)
        }
    }

    @Tool(description = "Stop scrcpy mirror session by sessionId")
    fun scrcpy_stop_mirror(
        @ToolParam(description = "Session ID from scrcpy_start_mirror") sessionId: String
    ): String {
        val start = System.currentTimeMillis()
        return try {
            val result = scrcpyService.stopMirror(sessionId)
            auditLogger.log("scrcpy_stop_mirror", null, mapOf("sessionId" to sessionId), "success", System.currentTimeMillis() - start)
            ToolResponse.success(result)
        } catch (e: AdbException) {
            auditLogger.log("scrcpy_stop_mirror", null, mapOf("sessionId" to sessionId), "error", System.currentTimeMillis() - start)
            ToolResponse.error(e)
        }
    }

    @Tool(description = "Start scrcpy video+audio recording. Returns sessionId.")
    fun scrcpy_start_record(
        @ToolParam(description = "Output file path (optional, auto-generated if omitted)") outputPath: String? = null,
        @ToolParam(description = "Enable audio recording (default true, requires Android 11+)") audioEnabled: Boolean? = null,
        @ToolParam(description = "Device serial (optional)") deviceSerial: String? = null
    ): String {
        val start = System.currentTimeMillis()
        return try {
            val resolvedSerial = deviceService.resolveWithSessionHint(deviceSerial)
            val result = scrcpyService.startRecord(outputPath, audioEnabled ?: true, resolvedSerial)
            auditLogger.log("scrcpy_start_record", resolvedSerial, mapOf("outputPath" to outputPath), "success", System.currentTimeMillis() - start)
            ToolResponse.success(result)
        } catch (e: AdbException) {
            auditLogger.log("scrcpy_start_record", deviceSerial, mapOf("outputPath" to outputPath), "error", System.currentTimeMillis() - start)
            ToolResponse.error(e)
        }
    }

    @Tool(description = "Stop scrcpy recording by sessionId, return file path")
    fun scrcpy_stop_record(
        @ToolParam(description = "Session ID from scrcpy_start_record") sessionId: String
    ): String {
        val start = System.currentTimeMillis()
        return try {
            val result = scrcpyService.stopRecord(sessionId)
            auditLogger.log("scrcpy_stop_record", null, mapOf("sessionId" to sessionId), "success", System.currentTimeMillis() - start)
            ToolResponse.success(result)
        } catch (e: AdbException) {
            auditLogger.log("scrcpy_stop_record", null, mapOf("sessionId" to sessionId), "error", System.currentTimeMillis() - start)
            ToolResponse.error(e)
        }
    }

    @Tool(description = "Connect a USB-attached device to Wi-Fi TCP/IP mode and then adb connect to its IP address")
    fun scrcpy_connect_tcpip(
        @ToolParam(description = "Device IP address") deviceIp: String,
        @ToolParam(description = "Port (default 5555)") port: Int? = null,
        @ToolParam(description = "USB-connected device serial to switch into TCP/IP mode (optional if set_device was used)") deviceSerial: String? = null
    ): String {
        val start = System.currentTimeMillis()
        return try {
            val resolvedSerial = deviceService.resolveWithSessionHint(deviceSerial)
            val result = scrcpyService.connectTcpip(deviceIp, port ?: 5555, resolvedSerial)
            auditLogger.log("scrcpy_connect_tcpip", resolvedSerial, mapOf("deviceIp" to deviceIp, "port" to port), "success", System.currentTimeMillis() - start)
            ToolResponse.success(result)
        } catch (e: AdbException) {
            auditLogger.log("scrcpy_connect_tcpip", deviceSerial, mapOf("deviceIp" to deviceIp, "port" to port), "error", System.currentTimeMillis() - start)
            ToolResponse.error(e)
        }
    }

    @Tool(description = "Get scrcpy session info by sessionId or list all active sessions")
    fun scrcpy_status(
        @ToolParam(description = "Session ID (optional, omit to list all)") sessionId: String? = null
    ): String {
        val start = System.currentTimeMillis()
        return try {
            val result = scrcpyService.getStatus(sessionId)
            auditLogger.log("scrcpy_status", null, mapOf("sessionId" to sessionId), "success", System.currentTimeMillis() - start)
            ToolResponse.success(result)
        } catch (e: AdbException) {
            auditLogger.log("scrcpy_status", null, mapOf("sessionId" to sessionId), "error", System.currentTimeMillis() - start)
            ToolResponse.error(e)
        }
    }
}
