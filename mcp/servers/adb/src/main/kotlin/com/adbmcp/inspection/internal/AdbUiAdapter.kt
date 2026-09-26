package com.adbmcp.inspection.internal

import com.adbmcp.infrastructure.AdbExecutor
import com.adbmcp.inspection.FindElementResult
import com.adbmcp.inspection.UiInspectionPort
import org.springframework.stereotype.Component

@Component
class AdbUiAdapter(
    private val adbExecutor: AdbExecutor,
    private val uiDumpParser: UiDumpParser
) : UiInspectionPort {

    override fun dumpUi(serial: String): String {
        // Dump UI hierarchy to file on device
        adbExecutor.execute(serial, "shell", "uiautomator", "dump",
            timeoutMs = 15000)
        // Read the dump file
        val pullResult = adbExecutor.execute(serial, "shell", "cat", "/sdcard/window_dump.xml",
            timeoutMs = 10000)
        // Cleanup
        adbExecutor.execute(serial, "shell", "rm", "-f", "/sdcard/window_dump.xml")
        return pullResult.stdout
    }

    override fun findElement(
        serial: String,
        text: String?,
        resourceId: String?,
        className: String?,
        contentDesc: String?,
        testTag: String?,
        index: Int,
        clickable: Boolean?
    ): FindElementResult {
        val xml = dumpUi(serial)
        val elements = uiDumpParser.parse(xml)
        var matching = uiDumpParser.findElements(elements, text, resourceId, className, contentDesc, testTag)
        if (clickable != null) {
            matching = matching.filter { it.clickable == clickable }
        }

        return if (matching.isNotEmpty() && index < matching.size) {
            val el = matching[index]
            FindElementResult(
                found = true,
                element = el,
                bounds = el.bounds.toString(),
                centerX = el.centerX,
                centerY = el.centerY,
                text = el.text,
                clickable = el.clickable,
                inferredType = el.inferredType,
                collapsedLabel = el.collapsedLabel
            )
        } else {
            FindElementResult(found = false)
        }
    }

    override fun getElementAt(serial: String, x: Int, y: Int): FindElementResult {
        val xml = dumpUi(serial)
        val elements = uiDumpParser.parse(xml)
        val el = uiDumpParser.findAtPoint(elements, x, y)

        return if (el != null) {
            FindElementResult(
                found = true,
                element = el,
                bounds = el.bounds.toString(),
                centerX = el.centerX,
                centerY = el.centerY,
                text = el.text,
                clickable = el.clickable,
                inferredType = el.inferredType,
                collapsedLabel = el.collapsedLabel
            )
        } else {
            FindElementResult(found = false)
        }
    }
}
