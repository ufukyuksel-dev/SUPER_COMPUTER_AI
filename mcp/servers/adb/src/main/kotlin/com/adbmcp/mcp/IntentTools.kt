package com.adbmcp.mcp

import com.adbmcp.device.DeviceService
import com.adbmcp.infrastructure.AdbException
import com.adbmcp.infrastructure.AuditLogger
import com.adbmcp.intent.ExtraType
import com.adbmcp.intent.IntentExtra
import com.adbmcp.intent.IntentService
import org.springframework.ai.tool.annotation.Tool
import org.springframework.ai.tool.annotation.ToolParam
import org.springframework.stereotype.Service

@Service
class IntentTools(
    private val intentService: IntentService,
    private val deviceService: DeviceService,
    private val auditLogger: AuditLogger
) {
    @Tool(description = "Start activity with optional action, data, component, typed extras, flags, categories")
    fun am_start(
        @ToolParam(description = "Intent action (e.g. android.intent.action.VIEW)") action: String? = null,
        @ToolParam(description = "Intent data URI") data: String? = null,
        @ToolParam(description = "Component (pkg/.Activity)") component: String? = null,
        @ToolParam(description = "Typed extras as JSON array: [{\"key\":\"k\",\"value\":\"v\",\"type\":\"STRING|INT|LONG|FLOAT|BOOLEAN|URI|COMPONENT|STRING_ARRAY|INT_ARRAY\"}]") extras: List<Map<String, String>>? = null,
        @ToolParam(description = "Intent flags") flags: List<String>? = null,
        @ToolParam(description = "Intent categories") categories: List<String>? = null,
        @ToolParam(description = "Device serial (optional)") deviceSerial: String? = null
    ): String {
        val start = System.currentTimeMillis()
        return try {
            val typedExtras = parseExtras(extras)
            val resolvedSerial = deviceService.resolveWithSessionHint(deviceSerial)
            val result = intentService.amStart(action, data, component, typedExtras, flags ?: emptyList(), categories ?: emptyList(), resolvedSerial)
            auditLogger.log("am_start", resolvedSerial, mapOf("action" to action, "component" to component), "success", System.currentTimeMillis() - start)
            ToolResponse.success(result)
        } catch (e: AdbException) {
            auditLogger.log("am_start", deviceSerial, mapOf("action" to action, "component" to component), "error", System.currentTimeMillis() - start)
            ToolResponse.error(e)
        }
    }

    @Tool(description = "Send broadcast intent with optional action, data, component, typed extras")
    fun am_broadcast(
        @ToolParam(description = "Intent action") action: String? = null,
        @ToolParam(description = "Intent data URI") data: String? = null,
        @ToolParam(description = "Component (pkg/.Activity)") component: String? = null,
        @ToolParam(description = "Typed extras as JSON array") extras: List<Map<String, String>>? = null,
        @ToolParam(description = "Intent flags") flags: List<String>? = null,
        @ToolParam(description = "Intent categories") categories: List<String>? = null,
        @ToolParam(description = "Device serial (optional)") deviceSerial: String? = null
    ): String {
        val start = System.currentTimeMillis()
        return try {
            val typedExtras = parseExtras(extras)
            val resolvedSerial = deviceService.resolveWithSessionHint(deviceSerial)
            val result = intentService.amBroadcast(action, data, component, typedExtras, flags ?: emptyList(), categories ?: emptyList(), resolvedSerial)
            auditLogger.log("am_broadcast", resolvedSerial, mapOf("action" to action), "success", System.currentTimeMillis() - start)
            ToolResponse.success(result)
        } catch (e: AdbException) {
            auditLogger.log("am_broadcast", deviceSerial, mapOf("action" to action), "error", System.currentTimeMillis() - start)
            ToolResponse.error(e)
        }
    }

    @Tool(description = "Force stop app by package name")
    fun force_stop(
        @ToolParam(description = "Package name to force stop") packageName: String,
        @ToolParam(description = "Device serial (optional)") deviceSerial: String? = null
    ): String {
        val start = System.currentTimeMillis()
        return try {
            val resolvedSerial = deviceService.resolveWithSessionHint(deviceSerial)
            val result = intentService.forceStop(packageName, resolvedSerial)
            auditLogger.log("force_stop", resolvedSerial, mapOf("packageName" to packageName), "success", System.currentTimeMillis() - start)
            ToolResponse.success(result)
        } catch (e: AdbException) {
            auditLogger.log("force_stop", deviceSerial, mapOf("packageName" to packageName), "error", System.currentTimeMillis() - start)
            ToolResponse.error(e)
        }
    }

    @Tool(description = "List installed packages (optional filter)")
    fun list_packages(
        @ToolParam(description = "Optional filter string") filter: String? = null,
        @ToolParam(description = "Device serial (optional)") deviceSerial: String? = null
    ): String {
        val start = System.currentTimeMillis()
        return try {
            val resolvedSerial = deviceService.resolveWithSessionHint(deviceSerial)
            val packages = intentService.listPackages(filter, resolvedSerial)
            auditLogger.log("list_packages", resolvedSerial, mapOf("filter" to filter), "success", System.currentTimeMillis() - start)
            ToolResponse.success(mapOf("success" to true, "packages" to packages, "count" to packages.size))
        } catch (e: AdbException) {
            auditLogger.log("list_packages", deviceSerial, mapOf("filter" to filter), "error", System.currentTimeMillis() - start)
            ToolResponse.error(e)
        }
    }

    @Tool(description = "Get currently focused activity")
    fun current_activity(
        @ToolParam(description = "Device serial (optional)") deviceSerial: String? = null
    ): String {
        val start = System.currentTimeMillis()
        return try {
            val resolvedSerial = deviceService.resolveWithSessionHint(deviceSerial)
            val activity = intentService.currentActivity(resolvedSerial)
            auditLogger.log("current_activity", resolvedSerial, emptyMap(), "success", System.currentTimeMillis() - start)
            ToolResponse.success(mapOf("success" to true, "currentActivity" to activity))
        } catch (e: AdbException) {
            auditLogger.log("current_activity", deviceSerial, emptyMap(), "error", System.currentTimeMillis() - start)
            ToolResponse.error(e)
        }
    }

    private fun parseExtras(extras: List<Map<String, String>>?): List<IntentExtra> {
        return extras?.map { map ->
            IntentExtra(
                key = map["key"] ?: throw IllegalArgumentException("Extra missing 'key'"),
                value = map["value"] ?: throw IllegalArgumentException("Extra missing 'value'"),
                type = ExtraType.valueOf(map["type"] ?: "STRING")
            )
        } ?: emptyList()
    }
}
