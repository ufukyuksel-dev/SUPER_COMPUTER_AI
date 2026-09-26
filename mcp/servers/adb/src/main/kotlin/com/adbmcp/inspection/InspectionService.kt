package com.adbmcp.inspection

import com.adbmcp.infrastructure.DeviceResolver
import com.adbmcp.inspection.internal.UiDumpParser
import org.springframework.stereotype.Service

@Service
class InspectionService(
    private val uiInspectionPort: UiInspectionPort,
    private val deviceResolver: DeviceResolver,
    private val uiDumpParser: UiDumpParser
) {
    fun dumpUi(deviceSerial: String? = null): String {
        val serial = deviceResolver.resolve(deviceSerial)
        return uiInspectionPort.dumpUi(serial)
    }

    fun isComposeUi(deviceSerial: String? = null): Boolean {
        val xml = dumpUi(deviceSerial)
        val elements = uiDumpParser.parse(xml)
        return uiDumpParser.hasComposeNodes(elements)
    }

    fun isComposeUiFromXml(xml: String): Boolean {
        val elements = uiDumpParser.parse(xml)
        return uiDumpParser.hasComposeNodes(elements)
    }

    fun findElement(
        text: String? = null,
        resourceId: String? = null,
        className: String? = null,
        contentDesc: String? = null,
        testTag: String? = null,
        index: Int = 0,
        clickable: Boolean? = null,
        deviceSerial: String? = null
    ): FindElementResult {
        val serial = deviceResolver.resolve(deviceSerial)
        return uiInspectionPort.findElement(serial, text, resourceId, className, contentDesc, testTag, index, clickable)
    }

    fun getElementAt(x: Int, y: Int, deviceSerial: String? = null): FindElementResult {
        val serial = deviceResolver.resolve(deviceSerial)
        return uiInspectionPort.getElementAt(serial, x, y)
    }
}
