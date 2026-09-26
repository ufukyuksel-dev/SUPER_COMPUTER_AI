package com.adbmcp.mcp

import com.adbmcp.device.DeviceService
import com.adbmcp.file.FileTransferService
import com.adbmcp.infrastructure.AdbException
import com.adbmcp.infrastructure.AuditLogger
import org.springframework.ai.tool.annotation.Tool
import org.springframework.ai.tool.annotation.ToolParam
import org.springframework.stereotype.Service

@Service
class FileTools(
    private val fileTransferService: FileTransferService,
    private val deviceService: DeviceService,
    private val auditLogger: AuditLogger
) {
    @Tool(description = "Push file from host to device (sandboxed to allowed paths)")
    fun push_file(
        @ToolParam(description = "Local file path on host (must be within allowed paths)") localPath: String,
        @ToolParam(description = "Remote path on device (e.g. /sdcard/file.txt)") remotePath: String,
        @ToolParam(description = "Device serial (optional)") deviceSerial: String? = null
    ): String {
        val start = System.currentTimeMillis()
        return try {
            val resolvedSerial = deviceService.resolveWithSessionHint(deviceSerial)
            val result = fileTransferService.pushFile(localPath, remotePath, resolvedSerial)
            auditLogger.log("push_file", resolvedSerial, mapOf("localPath" to localPath, "remotePath" to remotePath), "success", System.currentTimeMillis() - start)
            ToolResponse.success(result)
        } catch (e: AdbException) {
            auditLogger.log("push_file", deviceSerial, mapOf("localPath" to localPath, "remotePath" to remotePath), "error", System.currentTimeMillis() - start)
            ToolResponse.error(e)
        }
    }

    @Tool(description = "Pull file from device to host (sandboxed to allowed paths)")
    fun pull_file(
        @ToolParam(description = "Remote path on device") remotePath: String,
        @ToolParam(description = "Device serial (optional)") deviceSerial: String? = null
    ): String {
        val start = System.currentTimeMillis()
        return try {
            val resolvedSerial = deviceService.resolveWithSessionHint(deviceSerial)
            val result = fileTransferService.pullFile(remotePath, resolvedSerial)
            auditLogger.log("pull_file", resolvedSerial, mapOf("remotePath" to remotePath), "success", System.currentTimeMillis() - start)
            ToolResponse.success(result)
        } catch (e: AdbException) {
            auditLogger.log("pull_file", deviceSerial, mapOf("remotePath" to remotePath), "error", System.currentTimeMillis() - start)
            ToolResponse.error(e)
        }
    }
}
