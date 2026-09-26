package com.adbmcp.mcp

import com.adbmcp.device.DeviceService
import com.adbmcp.infrastructure.AdbException
import com.adbmcp.infrastructure.AuditLogger
import org.springframework.ai.tool.annotation.Tool
import org.springframework.ai.tool.annotation.ToolParam
import org.springframework.stereotype.Service

@Service
class DeviceTools(
    private val deviceService: DeviceService,
    private val auditLogger: AuditLogger
) {
    @Tool(description = "List connected Android devices with serial, model, and state")
    fun list_devices(): String {
        val start = System.currentTimeMillis()
        return try {
            val devices = deviceService.listDevices()
            val result = mapOf("success" to true, "devices" to devices)
            auditLogger.log("list_devices", null, emptyMap(), "success", System.currentTimeMillis() - start)
            ToolResponse.success(result)
        } catch (e: AdbException) {
            auditLogger.log("list_devices", null, emptyMap(), "error", System.currentTimeMillis() - start)
            ToolResponse.error(e)
        }
    }

    @Tool(description = "Get device properties: model, OS version, resolution, density, rotation")
    fun get_device_info(
        @ToolParam(description = "Device serial (optional, auto-selects if one device)") deviceSerial: String? = null
    ): String {
        val start = System.currentTimeMillis()
        return try {
            val info = deviceService.getDeviceInfo(deviceSerial)
            val result = mapOf("success" to true, "device" to info)
            auditLogger.log("get_device_info", deviceSerial, emptyMap(), "success", System.currentTimeMillis() - start)
            ToolResponse.success(result)
        } catch (e: AdbException) {
            auditLogger.log("get_device_info", deviceSerial, emptyMap(), "error", System.currentTimeMillis() - start)
            ToolResponse.error(e)
        }
    }

    @Tool(description = "Get current screen size using adb shell wm size")
    fun get_screen_size(
        @ToolParam(description = "Device serial (optional, auto-selects if one device)") deviceSerial: String? = null
    ): String {
        val start = System.currentTimeMillis()
        return try {
            val size = deviceService.getScreenSize(deviceSerial)
            val result = mapOf("success" to true, "screenSize" to size)
            auditLogger.log("get_screen_size", deviceSerial, emptyMap(), "success", System.currentTimeMillis() - start)
            ToolResponse.success(result)
        } catch (e: AdbException) {
            auditLogger.log("get_screen_size", deviceSerial, emptyMap(), "error", System.currentTimeMillis() - start)
            ToolResponse.error(e)
        }
    }

    @Tool(description = "Set preferred device serial for this session (convenience hint, per-call deviceSerial always overrides)")
    fun set_device(
        @ToolParam(description = "Device serial to set as session default") deviceSerial: String
    ): String {
        val start = System.currentTimeMillis()
        return try {
            deviceService.setDevice(deviceSerial)
            auditLogger.log("set_device", deviceSerial, emptyMap(), "success", System.currentTimeMillis() - start)
            ToolResponse.success(mapOf("success" to true, "deviceSerial" to deviceSerial))
        } catch (e: AdbException) {
            auditLogger.log("set_device", deviceSerial, emptyMap(), "error", System.currentTimeMillis() - start)
            ToolResponse.error(e)
        }
    }
}
