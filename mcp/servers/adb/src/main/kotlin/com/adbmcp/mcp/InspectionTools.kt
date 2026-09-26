package com.adbmcp.mcp

import com.adbmcp.device.DeviceService
import com.adbmcp.infrastructure.AdbException
import com.adbmcp.infrastructure.AuditLogger
import com.adbmcp.inspection.InspectionService
import org.springframework.ai.tool.annotation.Tool
import org.springframework.ai.tool.annotation.ToolParam
import org.springframework.stereotype.Service

@Service
class InspectionTools(
    private val inspectionService: InspectionService,
    private val deviceService: DeviceService,
    private val auditLogger: AuditLogger
) {
    @Tool(description = "Dump UI hierarchy as XML (uiautomator dump). Works with both traditional Android Views and Jetpack Compose. For Compose apps, elements appear as android.view.View — use testTag (Modifier.testTag) to identify them. Returns composeDetected flag when Compose UI is found.")
    fun dump_ui(
        @ToolParam(description = "Device serial (optional)") deviceSerial: String? = null
    ): String {
        val start = System.currentTimeMillis()
        return try {
            val resolvedSerial = deviceService.resolveWithSessionHint(deviceSerial)
            val xml = inspectionService.dumpUi(resolvedSerial)
            val composeDetected = inspectionService.isComposeUiFromXml(xml)
            val response = mutableMapOf<String, Any>(
                "success" to true,
                "xmlContent" to xml,
                "composeDetected" to composeDetected
            )
            if (composeDetected) {
                response["hint"] = "Compose UI detected. Use testTag parameter in find_element/wait_for_element for best results. Compose elements have class=android.view.View and need Modifier.testTag() for resource-id."
            }
            auditLogger.log("dump_ui", resolvedSerial, emptyMap(), "success", System.currentTimeMillis() - start)
            ToolResponse.success(response)
        } catch (e: AdbException) {
            auditLogger.log("dump_ui", deviceSerial, emptyMap(), "error", System.currentTimeMillis() - start)
            ToolResponse.error(e)
        }
    }

    @Tool(description = "Find UI element by text, resource-id, class name, content-description, testTag, or clickable state. Supports both traditional Android Views and Jetpack Compose. For Compose elements, use testTag (maps to Modifier.testTag in Compose code) or text for reliable matching. Returns bounds, center coordinates, inferredType (Button/Text/IconButton/etc.), and collapsedLabel for Compose nodes.")
    fun find_element(
        @ToolParam(description = "Match by text (exact or contains)") text: String? = null,
        @ToolParam(description = "Match by resource-id (exact match)") resourceId: String? = null,
        @ToolParam(description = "Match by class name") className: String? = null,
        @ToolParam(description = "Match by content-description") contentDesc: String? = null,
        @ToolParam(description = "Match by Compose testTag (Modifier.testTag). Flexible matching: works with or without package prefix.") testTag: String? = null,
        @ToolParam(description = "Which match to return if multiple (default 0)") index: Int? = null,
        @ToolParam(description = "Filter by clickable state (true=only clickable, false=only non-clickable, null=any)") clickable: Boolean? = null,
        @ToolParam(description = "Device serial (optional)") deviceSerial: String? = null
    ): String {
        val start = System.currentTimeMillis()
        return try {
            val resolvedSerial = deviceService.resolveWithSessionHint(deviceSerial)
            // Treat blank strings as null (no filter) — LLM clients often pass "" instead of omitting
            val result = inspectionService.findElement(
                text?.takeIf { it.isNotBlank() },
                resourceId?.takeIf { it.isNotBlank() },
                className?.takeIf { it.isNotBlank() },
                contentDesc?.takeIf { it.isNotBlank() },
                testTag?.takeIf { it.isNotBlank() },
                index ?: 0,
                clickable,
                resolvedSerial
            )
            auditLogger.log("find_element", resolvedSerial, mapOf("text" to text, "resourceId" to resourceId, "testTag" to testTag), "success", System.currentTimeMillis() - start)
            ToolResponse.success(result)
        } catch (e: AdbException) {
            auditLogger.log("find_element", deviceSerial, mapOf("text" to text, "resourceId" to resourceId, "testTag" to testTag), "error", System.currentTimeMillis() - start)
            ToolResponse.error(e)
        }
    }

    @Tool(description = "Get UI element info at (x,y) coordinates. Works with both traditional Views and Jetpack Compose elements.")
    fun get_element_at(
        @ToolParam(description = "X coordinate") x: Int,
        @ToolParam(description = "Y coordinate") y: Int,
        @ToolParam(description = "Device serial (optional)") deviceSerial: String? = null
    ): String {
        val start = System.currentTimeMillis()
        return try {
            val resolvedSerial = deviceService.resolveWithSessionHint(deviceSerial)
            val result = inspectionService.getElementAt(x, y, resolvedSerial)
            auditLogger.log("get_element_at", resolvedSerial, mapOf("x" to x, "y" to y), "success", System.currentTimeMillis() - start)
            ToolResponse.success(result)
        } catch (e: AdbException) {
            auditLogger.log("get_element_at", deviceSerial, mapOf("x" to x, "y" to y), "error", System.currentTimeMillis() - start)
            ToolResponse.error(e)
        }
    }
}
