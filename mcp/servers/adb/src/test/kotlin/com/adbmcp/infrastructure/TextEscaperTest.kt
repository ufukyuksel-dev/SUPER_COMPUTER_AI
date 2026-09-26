package com.adbmcp.infrastructure

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Test

class TextEscaperTest {

    private val escaper = TextEscaper()

    @Test
    fun `escapes spaces`() {
        val result = escaper.escapeForShell("hello world")
        assertEquals("hello%sworld", result)
    }

    @Test
    fun `escapes special characters`() {
        val result = escaper.escapeForShell("a&b|c;d")
        assertEquals("a\\&b\\|c\\;d", result)
    }

    @Test
    fun `escapes quotes`() {
        val result = escaper.escapeForShell("he said \"hi\"")
        assertEquals("he%ssaid%s\\\"hi\\\"", result)
    }

    @Test
    fun `plain text unchanged`() {
        val result = escaper.escapeForShell("hello123")
        assertEquals("hello123", result)
    }

    @Test
    fun `escapes dollar sign`() {
        val result = escaper.escapeForShell("\$HOME")
        assertEquals("\\\$HOME", result)
    }
}
