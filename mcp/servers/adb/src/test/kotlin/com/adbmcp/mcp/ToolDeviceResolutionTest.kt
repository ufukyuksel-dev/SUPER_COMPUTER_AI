package com.adbmcp.mcp

import com.adbmcp.writeExecutableScript
import com.adbmcp.device.DeviceInfo
import com.adbmcp.device.DevicePort
import com.adbmcp.device.ScreenSizeInfo
import com.adbmcp.device.DeviceService
import com.adbmcp.infrastructure.AdbExecutor
import com.adbmcp.infrastructure.AdbProperties
import com.adbmcp.infrastructure.AuditLogger
import com.adbmcp.infrastructure.DeviceResolver
import com.adbmcp.input.AutomationService
import com.adbmcp.input.CommandResult
import com.adbmcp.input.InputPort
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import org.springframework.ai.tool.method.MethodToolCallbackProvider
import java.nio.file.Path

class ToolDeviceResolutionTest {

    @TempDir
    lateinit var tempDir: Path

    @Test
    fun `set device hint is honored by input tools`() {
        val deviceResolver = createDeviceResolver()
        val deviceService = DeviceService(FakeDevicePort(), deviceResolver)

        var tappedSerial: String? = null
        val deviceTools = DeviceTools(deviceService, AuditLogger())
        val inputTools = InputTools(AutomationService(fakeInputPort { tappedSerial = it }, deviceResolver), deviceService, AuditLogger())

        val setDeviceResponse = deviceTools.set_device("emulator-5554")
        val tapResponse = inputTools.tap(10, 20, null)

        assertTrue(setDeviceResponse.contains("\"success\":true"))
        assertTrue(tapResponse.contains("\"success\":true"))
        assertEquals("emulator-5554", tappedSerial)
    }

    @Test
    fun `explicit deviceSerial overrides session hint`() {
        val deviceResolver = createDeviceResolver()
        val deviceService = DeviceService(FakeDevicePort(), deviceResolver)

        var tappedSerial: String? = null
        val deviceTools = DeviceTools(deviceService, AuditLogger())
        val inputTools = InputTools(AutomationService(fakeInputPort { tappedSerial = it }, deviceResolver), deviceService, AuditLogger())

        deviceTools.set_device("emulator-5554")
        inputTools.tap(10, 20, "emulator-5556")

        assertEquals("emulator-5556", tappedSerial)
    }

    @Test
    fun `tool schemas exclude toolContext parameters`() {
        val deviceResolver = createDeviceResolver()
        val deviceService = DeviceService(FakeDevicePort(), deviceResolver)
        val inputTools = InputTools(AutomationService(fakeInputPort { }, deviceResolver), deviceService, AuditLogger())

        val callbacks = MethodToolCallbackProvider.builder()
            .toolObjects(inputTools)
            .build()
            .toolCallbacks
        val tapSchema = callbacks
            .single { it.toolDefinition.name() == "tap" }
            .toolDefinition
            .inputSchema()

        assertFalse(tapSchema.contains("toolContext", ignoreCase = true))
    }

    private class FakeDevicePort : DevicePort {
        override fun listDevices(): List<DeviceInfo> = emptyList()

        override fun getDeviceInfo(serial: String): DeviceInfo = DeviceInfo(serial = serial)

        override fun getScreenSize(serial: String): ScreenSizeInfo = ScreenSizeInfo(width = 1080, height = 2400, activeSize = "1080x2400")
    }

    private fun createDeviceResolver(): DeviceResolver {
        val adbScript = writeExecutableScript(
            tempDir,
            "fake-adb.sh",
            """
            #!/bin/sh
            if [ "$1" = "devices" ]; then
              echo "List of devices attached"
              echo "emulator-5554 device"
              echo "emulator-5556 device"
              exit 0
            fi
            echo "unexpected args: $@" >&2
            exit 1
            """
        )
        return DeviceResolver(AdbExecutor(AdbProperties(path = adbScript)))
    }

    private fun fakeInputPort(onTap: (String) -> Unit): InputPort {
        return object : InputPort {
            override fun tap(serial: String, x: Int, y: Int): CommandResult {
                onTap(serial)
                return CommandResult(success = true)
            }

            override fun swipe(serial: String, x1: Int, y1: Int, x2: Int, y2: Int, durationMs: Int): CommandResult {
                throw UnsupportedOperationException()
            }

            override fun longPress(serial: String, x: Int, y: Int, durationMs: Int): CommandResult {
                throw UnsupportedOperationException()
            }

            override fun typeText(serial: String, text: String, useAdbKeyboard: Boolean): CommandResult {
                throw UnsupportedOperationException()
            }

            override fun keyEvent(serial: String, keycode: String): CommandResult {
                throw UnsupportedOperationException()
            }

            override fun imeList(serial: String): List<String> {
                throw UnsupportedOperationException()
            }

            override fun imeSet(serial: String, imeId: String): CommandResult {
                throw UnsupportedOperationException()
            }

            override fun imeCurrent(serial: String): String {
                throw UnsupportedOperationException()
            }
        }
    }
}
