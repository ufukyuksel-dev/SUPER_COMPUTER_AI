package com.adbmcp.inspection

interface UiInspectionPort {
    fun dumpUi(serial: String): String
    fun findElement(
        serial: String,
        text: String? = null,
        resourceId: String? = null,
        className: String? = null,
        contentDesc: String? = null,
        testTag: String? = null,
        index: Int = 0,
        clickable: Boolean? = null
    ): FindElementResult

    fun getElementAt(serial: String, x: Int, y: Int): FindElementResult
}
