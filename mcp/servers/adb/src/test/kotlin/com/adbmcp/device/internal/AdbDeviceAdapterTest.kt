package com.adbmcp.device.internal

import com.adbmcp.writeExecutableScript
import com.adbmcp.infrastructure.AdbExecutor
import com.adbmcp.infrastructure.AdbProperties
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import java.nio.file.Path

class AdbDeviceAdapterTest {

    @TempDir
    lateinit var tempDir: Path

    @Test
    fun `get screen size parses active and physical sizes`() {
        val adbScript = writeExecutableScript(
            tempDir,
            "fake-adb.sh",
            """
            #!/bin/sh
            if [ "$1" = "-s" ] && [ "$3" = "shell" ] && [ "$4" = "wm" ] && [ "$5" = "size" ]; then
              echo "Physical size: 1080x2400"
              echo "Override size: 1080x1920"
              exit 0
            fi
            echo "unexpected args: $@" >&2
            exit 1
            """
        )
        val adapter = AdbDeviceAdapter(AdbExecutor(AdbProperties(path = adbScript)))

        val screenSize = adapter.getScreenSize("emulator-5554")

        assertEquals("1080x2400", screenSize.physicalSize)
        assertEquals("1080x1920", screenSize.overrideSize)
        assertEquals("1080x1920", screenSize.activeSize)
        assertEquals(1080, screenSize.width)
        assertEquals(1920, screenSize.height)
    }
}
