package com.adbmcp.mcp

import com.adbmcp.device.DeviceService
import com.adbmcp.infrastructure.AdbException
import com.adbmcp.infrastructure.AuditLogger
import com.adbmcp.input.AutomationService
import org.springframework.ai.tool.annotation.Tool
import org.springframework.ai.tool.annotation.ToolParam
import org.springframework.stereotype.Service

@Service
class InputTools(
    private val automationService: AutomationService,
    private val deviceService: DeviceService,
    private val auditLogger: AuditLogger
) {
    @Tool(description = "Tap at screen coordinates (x, y) in pixels")
    fun tap(
        @ToolParam(description = "X coordinate in pixels") x: Int,
        @ToolParam(description = "Y coordinate in pixels") y: Int,
        @ToolParam(description = "Device serial (optional)") deviceSerial: String? = null
    ): String {
        val start = System.currentTimeMillis()
        return try {
            val resolvedSerial = deviceService.resolveWithSessionHint(deviceSerial)
            val result = automationService.tap(x, y, resolvedSerial)
            auditLogger.log("tap", resolvedSerial, mapOf("x" to x, "y" to y), "success", System.currentTimeMillis() - start)
            ToolResponse.success(result)
        } catch (e: AdbException) {
            auditLogger.log("tap", deviceSerial, mapOf("x" to x, "y" to y), "error", System.currentTimeMillis() - start)
            ToolResponse.error(e)
        }
    }

    @Tool(description = "Swipe from (x1,y1) to (x2,y2) with duration in ms")
    fun swipe(
        @ToolParam(description = "Start X coordinate") x1: Int,
        @ToolParam(description = "Start Y coordinate") y1: Int,
        @ToolParam(description = "End X coordinate") x2: Int,
        @ToolParam(description = "End Y coordinate") y2: Int,
        @ToolParam(description = "Swipe duration in ms (default 300)") durationMs: Int? = null,
        @ToolParam(description = "Device serial (optional)") deviceSerial: String? = null
    ): String {
        val start = System.currentTimeMillis()
        val duration = durationMs ?: 300
        return try {
            val resolvedSerial = deviceService.resolveWithSessionHint(deviceSerial)
            val result = automationService.swipe(x1, y1, x2, y2, duration, resolvedSerial)
            auditLogger.log("swipe", resolvedSerial, mapOf("x1" to x1, "y1" to y1, "x2" to x2, "y2" to y2), "success", System.currentTimeMillis() - start)
            ToolResponse.success(result)
        } catch (e: AdbException) {
            auditLogger.log("swipe", deviceSerial, mapOf("x1" to x1, "y1" to y1, "x2" to x2, "y2" to y2), "error", System.currentTimeMillis() - start)
            ToolResponse.error(e)
        }
    }

    @Tool(description = "Long press at (x, y) via zero-distance swipe with duration in ms")
    fun long_press(
        @ToolParam(description = "X coordinate") x: Int,
        @ToolParam(description = "Y coordinate") y: Int,
        @ToolParam(description = "Press duration in ms (default 1000)") durationMs: Int? = null,
        @ToolParam(description = "Device serial (optional)") deviceSerial: String? = null
    ): String {
        val start = System.currentTimeMillis()
        val duration = durationMs ?: 1000
        return try {
            val resolvedSerial = deviceService.resolveWithSessionHint(deviceSerial)
            val result = automationService.longPress(x, y, duration, resolvedSerial)
            auditLogger.log("long_press", resolvedSerial, mapOf("x" to x, "y" to y, "durationMs" to duration), "success", System.currentTimeMillis() - start)
            ToolResponse.success(result)
        } catch (e: AdbException) {
            auditLogger.log("long_press", deviceSerial, mapOf("x" to x, "y" to y), "error", System.currentTimeMillis() - start)
            ToolResponse.error(e)
        }
    }

    @Tool(description = "Input text. Use useAdbKeyboard=true for UTF-8/Turkish characters (requires ADBKeyboard IME installed)")
    fun type_text(
        @ToolParam(description = "Text to input") text: String,
        @ToolParam(description = "Use ADBKeyboard for UTF-8 (default false)") useAdbKeyboard: Boolean? = null,
        @ToolParam(description = "Device serial (optional)") deviceSerial: String? = null
    ): String {
        val start = System.currentTimeMillis()
        return try {
            val resolvedSerial = deviceService.resolveWithSessionHint(deviceSerial)
            val result = automationService.typeText(text, useAdbKeyboard ?: false, resolvedSerial)
            auditLogger.log("type_text", resolvedSerial, mapOf("text" to text), "success", System.currentTimeMillis() - start)
            ToolResponse.success(result)
        } catch (e: AdbException) {
            auditLogger.log("type_text", deviceSerial, mapOf("text" to text), "error", System.currentTimeMillis() - start)
            ToolResponse.error(e)
        }
    }

    @Tool(description = "Send key event (ENTER, BACK, HOME, POWER, etc.)")
    fun key_event(
        @ToolParam(description = "Key code (e.g. ENTER, BACK, HOME, POWER, VOLUME_UP)") keycode: String,
        @ToolParam(description = "Device serial (optional)") deviceSerial: String? = null
    ): String {
        val start = System.currentTimeMillis()
        return try {
            val resolvedSerial = deviceService.resolveWithSessionHint(deviceSerial)
            val result = automationService.keyEvent(keycode, resolvedSerial)
            auditLogger.log("key_event", resolvedSerial, mapOf("keycode" to keycode), "success", System.currentTimeMillis() - start)
            ToolResponse.success(result)
        } catch (e: AdbException) {
            auditLogger.log("key_event", deviceSerial, mapOf("keycode" to keycode), "error", System.currentTimeMillis() - start)
            ToolResponse.error(e)
        }
    }

    @Tool(description = "List installed input methods with their IDs")
    fun ime_list(
        @ToolParam(description = "Device serial (optional)") deviceSerial: String? = null
    ): String {
        val start = System.currentTimeMillis()
        return try {
            val resolvedSerial = deviceService.resolveWithSessionHint(deviceSerial)
            val imes = automationService.imeList(resolvedSerial)
            auditLogger.log("ime_list", resolvedSerial, emptyMap(), "success", System.currentTimeMillis() - start)
            ToolResponse.success(mapOf("success" to true, "imeList" to imes))
        } catch (e: AdbException) {
            auditLogger.log("ime_list", deviceSerial, emptyMap(), "error", System.currentTimeMillis() - start)
            ToolResponse.error(e)
        }
    }

    @Tool(description = "Set active input method by IME ID")
    fun ime_set(
        @ToolParam(description = "IME ID to set as active") imeId: String,
        @ToolParam(description = "Device serial (optional)") deviceSerial: String? = null
    ): String {
        val start = System.currentTimeMillis()
        return try {
            val resolvedSerial = deviceService.resolveWithSessionHint(deviceSerial)
            val result = automationService.imeSet(imeId, resolvedSerial)
            auditLogger.log("ime_set", resolvedSerial, mapOf("imeId" to imeId), "success", System.currentTimeMillis() - start)
            ToolResponse.success(result)
        } catch (e: AdbException) {
            auditLogger.log("ime_set", deviceSerial, mapOf("imeId" to imeId), "error", System.currentTimeMillis() - start)
            ToolResponse.error(e)
        }
    }

    @Tool(description = "Get currently active IME ID (for save/restore)")
    fun ime_current(
        @ToolParam(description = "Device serial (optional)") deviceSerial: String? = null
    ): String {
        val start = System.currentTimeMillis()
        return try {
            val resolvedSerial = deviceService.resolveWithSessionHint(deviceSerial)
            val current = automationService.imeCurrent(resolvedSerial)
            auditLogger.log("ime_current", resolvedSerial, emptyMap(), "success", System.currentTimeMillis() - start)
            ToolResponse.success(mapOf("success" to true, "currentIme" to current))
        } catch (e: AdbException) {
            auditLogger.log("ime_current", deviceSerial, emptyMap(), "error", System.currentTimeMillis() - start)
            ToolResponse.error(e)
        }
    }
}
