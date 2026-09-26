package com.adbmcp.inspection.internal

import com.adbmcp.inspection.Bounds
import com.adbmcp.inspection.UiElement
import org.springframework.stereotype.Component
import org.w3c.dom.Element
import org.w3c.dom.Node
import java.io.ByteArrayInputStream
import javax.xml.parsers.DocumentBuilderFactory

@Component
class UiDumpParser {

    private val boundsRegex = "\\[(\\d+),(\\d+)\\]\\[(\\d+),(\\d+)\\]".toRegex()

    companion object {
        private const val COMPOSE_VIEW_CLASS = "ComposeView"
    }

    fun parse(xml: String): List<UiElement> {
        val factory = DocumentBuilderFactory.newInstance()
        factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true)
        val builder = factory.newDocumentBuilder()
        val document = builder.parse(ByteArrayInputStream(xml.toByteArray()))
        val elements = mutableListOf<UiElement>()
        walkNodes(document.documentElement, elements, insideCompose = false)
        return elements
    }

    fun findElements(
        elements: List<UiElement>,
        text: String? = null,
        resourceId: String? = null,
        className: String? = null,
        contentDesc: String? = null,
        testTag: String? = null
    ): List<UiElement> {
        return elements.filter { el ->
            val textMatch = text == null || el.text.contains(text, ignoreCase = true)
            val idMatch = resourceId == null || el.resourceId == resourceId
            val classMatch = className == null || el.className == className
            val descMatch = contentDesc == null || el.contentDesc.contains(contentDesc, ignoreCase = true)
            val tagMatch = testTag == null || matchTestTag(el.resourceId, testTag)
            textMatch && idMatch && classMatch && descMatch && tagMatch
        }.sortedWith(compareBy({ it.bounds.top }, { it.bounds.left }))
    }

    fun findAtPoint(elements: List<UiElement>, x: Int, y: Int): UiElement? {
        return elements
            .filter { el ->
                x >= el.bounds.left && x <= el.bounds.right &&
                        y >= el.bounds.top && y <= el.bounds.bottom
            }
            .lastOrNull() // deepest (last in DFS order) matching element
    }

    fun hasComposeNodes(elements: List<UiElement>): Boolean {
        return elements.any { it.isComposeNode }
    }

    private fun matchTestTag(resourceId: String, testTag: String): Boolean {
        if (resourceId.isEmpty()) return false
        // Exact match
        if (resourceId == testTag) return true
        // Match with :id/ prefix (e.g., "com.example:id/my_tag" matches "my_tag")
        if (resourceId.endsWith(":id/$testTag")) return true
        // Contains match for flexibility
        if (resourceId.contains(testTag, ignoreCase = true)) return true
        return false
    }

    private fun walkNodes(node: Node, elements: MutableList<UiElement>, insideCompose: Boolean) {
        if (node is Element && node.tagName == "node") {
            val className = node.getAttribute("class") ?: ""
            val isComposeView = className.contains(COMPOSE_VIEW_CLASS)
            val composeContext = insideCompose || isComposeView
            parseNode(node, composeContext)?.let { elements.add(it) }
            val children = node.childNodes
            for (i in 0 until children.length) {
                walkNodes(children.item(i), elements, composeContext)
            }
            return
        }
        val children = node.childNodes
        for (i in 0 until children.length) {
            walkNodes(children.item(i), elements, insideCompose)
        }
    }

    private fun parseNode(element: Element, isCompose: Boolean = false): UiElement? {
        val boundsStr = element.getAttribute("bounds") ?: return null
        val bounds = parseBounds(boundsStr) ?: return null

        val text = element.getAttribute("text") ?: ""
        val className = element.getAttribute("class") ?: ""
        val contentDesc = element.getAttribute("content-desc") ?: ""
        val clickable = element.getAttribute("clickable")?.toBoolean() ?: false
        val checkable = element.getAttribute("checkable")?.toBoolean() ?: false
        val scrollable = element.getAttribute("scrollable")?.toBoolean() ?: false
        val focusable = element.getAttribute("focusable")?.toBoolean() ?: false
        val longClickable = element.getAttribute("long-clickable")?.toBoolean() ?: false

        val inferredType = inferType(className, text, contentDesc, clickable, checkable, scrollable, focusable, longClickable, isCompose)
        val collapsedLabel = if (isCompose) buildCollapsedLabel(element, text, contentDesc) else null

        return UiElement(
            index = element.getAttribute("index")?.toIntOrNull() ?: 0,
            text = text,
            resourceId = element.getAttribute("resource-id") ?: "",
            className = className,
            packageName = element.getAttribute("package") ?: "",
            contentDesc = contentDesc,
            checkable = checkable,
            checked = element.getAttribute("checked")?.toBoolean() ?: false,
            clickable = clickable,
            enabled = element.getAttribute("enabled")?.toBoolean() ?: true,
            focusable = focusable,
            focused = element.getAttribute("focused")?.toBoolean() ?: false,
            scrollable = scrollable,
            longClickable = longClickable,
            selected = element.getAttribute("selected")?.toBoolean() ?: false,
            bounds = bounds,
            centerX = (bounds.left + bounds.right) / 2,
            centerY = (bounds.top + bounds.bottom) / 2,
            isComposeNode = isCompose,
            inferredType = inferredType,
            collapsedLabel = collapsedLabel
        )
    }

    private fun inferType(
        className: String, text: String, contentDesc: String,
        clickable: Boolean, checkable: Boolean, scrollable: Boolean,
        focusable: Boolean, longClickable: Boolean, isCompose: Boolean
    ): String {
        // Traditional Android Views — use class name directly
        if (!isCompose) return when {
            className.endsWith("Button") -> "Button"
            className.endsWith("EditText") -> "TextField"
            className.endsWith("TextView") -> "Text"
            className.endsWith("ImageView") -> "Image"
            className.endsWith("CheckBox") -> "Checkbox"
            className.endsWith("Switch") -> "Switch"
            className.endsWith("RecyclerView") || className.endsWith("ListView") -> "List"
            className.endsWith("ScrollView") -> "ScrollContainer"
            else -> "View"
        }
        // Compose nodes — heuristic inference
        return when {
            checkable -> "Toggle"
            scrollable -> "ScrollContainer"
            clickable && text.isNotEmpty() -> "Button"
            clickable && contentDesc.isNotEmpty() -> "IconButton"
            clickable && text.isEmpty() -> "Clickable"
            focusable && !clickable -> "TextField"
            text.isNotEmpty() && !clickable -> "Text"
            contentDesc.isNotEmpty() && !clickable -> "Image"
            else -> "View"
        }
    }

    private fun buildCollapsedLabel(element: Element, selfText: String, selfContentDesc: String): String? {
        if (selfText.isNotEmpty()) return null // already has its own text
        // Look at immediate child nodes for text
        val childTexts = mutableListOf<String>()
        val children = element.childNodes
        for (i in 0 until children.length) {
            val child = children.item(i)
            if (child is Element && child.tagName == "node") {
                val childText = child.getAttribute("text") ?: ""
                if (childText.isNotEmpty()) childTexts.add(childText)
            }
        }
        if (childTexts.isEmpty()) return null
        val label = childTexts.joinToString(" | ")
        val desc = if (selfContentDesc.isNotEmpty()) " ($selfContentDesc)" else ""
        return "$label$desc"
    }

    private fun parseBounds(boundsStr: String): Bounds? {
        val match = boundsRegex.find(boundsStr) ?: return null
        return Bounds(
            left = match.groupValues[1].toInt(),
            top = match.groupValues[2].toInt(),
            right = match.groupValues[3].toInt(),
            bottom = match.groupValues[4].toInt()
        )
    }
}
