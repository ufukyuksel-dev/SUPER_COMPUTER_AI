package com.adbmcp.infrastructure

import com.adbmcp.writeExecutableScript
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import org.junit.jupiter.api.assertThrows
import java.nio.file.Path

class DeviceResolverTest {

    @TempDir
    lateinit var tempDir: Path

    @Test
    fun `resolve rejects explicit serials that are not connected`() {
        val resolver = DeviceResolver(adbExecutorWithDevices("emulator-5554", "emulator-5556"))

        val error = assertThrows<DeviceNotFoundException> {
            resolver.resolve("missing-device")
        }

        assertTrue(error.message!!.contains("emulator-5554"))
        assertTrue(error.message!!.contains("emulator-5556"))
    }

    @Test
    fun `resolve returns connected explicit serial`() {
        val resolver = DeviceResolver(adbExecutorWithDevices("emulator-5554", "emulator-5556"))

        val serial = resolver.resolve("emulator-5556")

        assertEquals("emulator-5556", serial)
    }

    private fun adbExecutorWithDevices(vararg serials: String): AdbExecutor {
        val scriptPath = writeExecutableScript(
            tempDir,
            "fake-adb.sh",
            """
            #!/bin/sh
            if [ "$1" = "devices" ]; then
              echo "List of devices attached"
              ${serials.joinToString("\n") { "echo \"$it device\"" }}
              exit 0
            fi
            echo "unexpected args: $@" >&2
            exit 1
            """
        )
        return AdbExecutor(AdbProperties(path = scriptPath))
    }
}
