package com.adbmcp.intent

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test

class IntentExtraTest {

    @Test
    fun `STRING maps to --es`() {
        assertEquals("--es", ExtraType.STRING.adbFlag)
    }

    @Test
    fun `INT maps to --ei`() {
        assertEquals("--ei", ExtraType.INT.adbFlag)
    }

    @Test
    fun `LONG maps to --el`() {
        assertEquals("--el", ExtraType.LONG.adbFlag)
    }

    @Test
    fun `FLOAT maps to --ef`() {
        assertEquals("--ef", ExtraType.FLOAT.adbFlag)
    }

    @Test
    fun `BOOLEAN maps to --ez`() {
        assertEquals("--ez", ExtraType.BOOLEAN.adbFlag)
    }

    @Test
    fun `URI maps to --eu`() {
        assertEquals("--eu", ExtraType.URI.adbFlag)
    }

    @Test
    fun `COMPONENT maps to --ecn`() {
        assertEquals("--ecn", ExtraType.COMPONENT.adbFlag)
    }

    @Test
    fun `STRING_ARRAY maps to --esa`() {
        assertEquals("--esa", ExtraType.STRING_ARRAY.adbFlag)
    }

    @Test
    fun `INT_ARRAY maps to --eia`() {
        assertEquals("--eia", ExtraType.INT_ARRAY.adbFlag)
    }

    @Test
    fun `all 9 extra types covered`() {
        assertEquals(9, ExtraType.entries.size)
    }
}
