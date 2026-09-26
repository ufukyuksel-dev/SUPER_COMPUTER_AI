package com.adbmcp.inspection.internal

import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class UiDumpParserTest {

    private val parser = UiDumpParser()

    private fun loadXml(name: String): String {
        return javaClass.classLoader.getResource("golden/uidumps/$name")!!.readText()
    }

    @Test
    fun `parse settings main returns correct element count`() {
        val xml = loadXml("settings_main.xml")
        val elements = parser.parse(xml)
        assertEquals(9, elements.size) // hierarchy + FrameLayout + action_bar + Settings title + RecyclerView + 5 items (parser walks all node elements)
    }

    @Test
    fun `parse extracts bounds correctly`() {
        val xml = loadXml("settings_main.xml")
        val elements = parser.parse(xml)
        val settingsTitle = elements.find { it.text == "Settings" }
        assertNotNull(settingsTitle)
        assertEquals(56, settingsTitle!!.bounds.left)
        assertEquals(126, settingsTitle.bounds.top)
        assertEquals(270, settingsTitle.bounds.right)
        assertEquals(194, settingsTitle.bounds.bottom)
    }

    @Test
    fun `parse calculates center correctly`() {
        val xml = loadXml("settings_main.xml")
        val elements = parser.parse(xml)
        val settingsTitle = elements.find { it.text == "Settings" }!!
        assertEquals((56 + 270) / 2, settingsTitle.centerX)
        assertEquals((126 + 194) / 2, settingsTitle.centerY)
    }

    @Test
    fun `findElements by text returns matching elements`() {
        val xml = loadXml("settings_main.xml")
        val elements = parser.parse(xml)
        val found = parser.findElements(elements, text = "Network")
        assertEquals(1, found.size)
        assertEquals("Network & internet", found[0].text)
    }

    @Test
    fun `findElements by resourceId returns matching elements`() {
        val xml = loadXml("settings_main.xml")
        val elements = parser.parse(xml)
        val found = parser.findElements(elements, resourceId = "android:id/title")
        assertEquals(5, found.size) // 5 settings items
    }

    @Test
    fun `findElements sorted by visual order`() {
        val xml = loadXml("settings_main.xml")
        val elements = parser.parse(xml)
        val found = parser.findElements(elements, resourceId = "android:id/title")
        assertTrue(found[0].bounds.top < found[1].bounds.top)
        assertTrue(found[1].bounds.top < found[2].bounds.top)
    }

    @Test
    fun `findAtPoint returns deepest element`() {
        val xml = loadXml("settings_main.xml")
        val elements = parser.parse(xml)
        // Click on "Network & internet" center
        val el = parser.findAtPoint(elements, 540, 320)
        assertNotNull(el)
        assertEquals("Network & internet", el!!.text)
    }

    @Test
    fun `findAtPoint returns null for empty area outside all bounds`() {
        val xml = loadXml("settings_main.xml")
        val elements = parser.parse(xml)
        // Outside all bounds
        val el = parser.findAtPoint(elements, 5000, 5000)
        assertNull(el)
    }

    @Test
    fun `findElements with no match returns empty`() {
        val xml = loadXml("settings_main.xml")
        val elements = parser.parse(xml)
        val found = parser.findElements(elements, text = "NonExistentText12345")
        assertTrue(found.isEmpty())
    }

    @Test
    fun `parse handles clickable attribute`() {
        val xml = loadXml("settings_main.xml")
        val elements = parser.parse(xml)
        val networkItem = elements.find { it.text == "Network & internet" }!!
        assertTrue(networkItem.clickable)

        val settingsTitle = elements.find { it.text == "Settings" }!!
        assertFalse(settingsTitle.clickable)
    }

    @Test
    fun `parse handles scrollable attribute`() {
        val xml = loadXml("settings_main.xml")
        val elements = parser.parse(xml)
        val recyclerView = elements.find { it.className.contains("RecyclerView") }!!
        assertTrue(recyclerView.scrollable)
    }

    // --- Compose UI Tests ---

    @Test
    fun `parse compose screen detects compose nodes`() {
        val xml = loadXml("compose_screen.xml")
        val elements = parser.parse(xml)
        assertTrue(parser.hasComposeNodes(elements))
    }

    @Test
    fun `parse traditional screen has no compose nodes`() {
        val xml = loadXml("settings_main.xml")
        val elements = parser.parse(xml)
        assertFalse(parser.hasComposeNodes(elements))
    }

    @Test
    fun `compose nodes are marked with isComposeNode flag`() {
        val xml = loadXml("compose_screen.xml")
        val elements = parser.parse(xml)
        val loginButton = elements.find { it.text == "Login" }
        assertNotNull(loginButton)
        assertTrue(loginButton!!.isComposeNode)
    }

    @Test
    fun `ComposeView itself is marked as compose node`() {
        val xml = loadXml("compose_screen.xml")
        val elements = parser.parse(xml)
        val composeView = elements.find { it.className.contains("ComposeView") }
        assertNotNull(composeView)
        assertTrue(composeView!!.isComposeNode)
    }

    @Test
    fun `non-compose parent nodes are not marked`() {
        val xml = loadXml("compose_screen.xml")
        val elements = parser.parse(xml)
        val outerFrame = elements.first { it.className == "android.widget.FrameLayout" }
        assertFalse(outerFrame.isComposeNode)
    }

    @Test
    fun `findElements by testTag exact match`() {
        val xml = loadXml("compose_screen.xml")
        val elements = parser.parse(xml)
        val found = parser.findElements(elements, testTag = "login_button")
        assertEquals(1, found.size)
        assertEquals("Login", found[0].text)
    }

    @Test
    fun `findElements by testTag with package prefix`() {
        val xml = loadXml("compose_screen.xml")
        val elements = parser.parse(xml)
        // email_field has resource-id "com.example.myapp:id/email_field"
        val found = parser.findElements(elements, testTag = "email_field")
        assertEquals(1, found.size)
        assertEquals("Email input", found[0].contentDesc)
    }

    @Test
    fun `findElements by testTag without prefix`() {
        val xml = loadXml("compose_screen.xml")
        val elements = parser.parse(xml)
        // password_field has resource-id "password_field" (no package prefix)
        val found = parser.findElements(elements, testTag = "password_field")
        assertEquals(1, found.size)
        assertEquals("Password input", found[0].contentDesc)
    }

    @Test
    fun `findElements by text in compose screen`() {
        val xml = loadXml("compose_screen.xml")
        val elements = parser.parse(xml)
        val found = parser.findElements(elements, text = "Forgot password?")
        assertEquals(1, found.size)
        assertTrue(found[0].clickable)
    }

    @Test
    fun `findElements by contentDesc in compose screen`() {
        val xml = loadXml("compose_screen.xml")
        val elements = parser.parse(xml)
        val found = parser.findElements(elements, contentDesc = "Google sign-in")
        assertEquals(1, found.size)
        assertTrue(found[0].isComposeNode)
    }

    @Test
    fun `findAtPoint works with compose elements`() {
        val xml = loadXml("compose_screen.xml")
        val elements = parser.parse(xml)
        // Click center of login button [200,620][880,720]
        val el = parser.findAtPoint(elements, 540, 670)
        assertNotNull(el)
        assertEquals("Login", el!!.text)
        assertTrue(el.isComposeNode)
    }

    @Test
    fun `compose elements have generic class names`() {
        val xml = loadXml("compose_screen.xml")
        val elements = parser.parse(xml)
        val composeElements = elements.filter { it.isComposeNode && it.className != "androidx.compose.ui.platform.ComposeView" }
        // All Compose children should be android.view.View
        assertTrue(composeElements.all { it.className == "android.view.View" })
    }

    @Test
    fun `findElements by testTag no match returns empty`() {
        val xml = loadXml("compose_screen.xml")
        val elements = parser.parse(xml)
        val found = parser.findElements(elements, testTag = "nonexistent_tag")
        assertTrue(found.isEmpty())
    }
}
