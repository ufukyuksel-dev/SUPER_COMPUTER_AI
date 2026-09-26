package com.adbmcp.inspection

data class UiElement(
    val index: Int,
    val text: String,
    val resourceId: String,
    val className: String,
    val packageName: String,
    val contentDesc: String,
    val checkable: Boolean,
    val checked: Boolean,
    val clickable: Boolean,
    val enabled: Boolean,
    val focusable: Boolean,
    val focused: Boolean,
    val scrollable: Boolean,
    val longClickable: Boolean,
    val selected: Boolean,
    val bounds: Bounds,
    val centerX: Int,
    val centerY: Int,
    val isComposeNode: Boolean = false,
    val inferredType: String = "View",
    val collapsedLabel: String? = null
)

data class Bounds(
    val left: Int,
    val top: Int,
    val right: Int,
    val bottom: Int
) {
    override fun toString(): String = "[$left,$top][$right,$bottom]"
}

data class FindElementResult(
    val found: Boolean,
    val element: UiElement? = null,
    val bounds: String? = null,
    val centerX: Int? = null,
    val centerY: Int? = null,
    val text: String? = null,
    val clickable: Boolean? = null,
    val inferredType: String? = null,
    val collapsedLabel: String? = null
)
