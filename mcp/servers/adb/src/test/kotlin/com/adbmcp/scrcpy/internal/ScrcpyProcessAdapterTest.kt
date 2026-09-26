package com.adbmcp.scrcpy.internal

import com.adbmcp.writeExecutableScript
import com.adbmcp.infrastructure.AdbExecutor
import com.adbmcp.infrastructure.AdbProperties
import com.adbmcp.scrcpy.ScrcpyProperties
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import java.nio.file.Path

class ScrcpyProcessAdapterTest {

    @TempDir
    lateinit var tempDir: Path

    @Test
    fun `connect tcpip reports adb connect failures`() {
        val adbScript = writeExecutableScript(
            tempDir,
            "fake-adb.sh",
            """
            #!/bin/sh
            if [ "$1" = "-s" ] && [ "$3" = "tcpip" ]; then
              echo "restarting in TCP mode port: $4"
              exit 0
            fi
            if [ "$1" = "connect" ]; then
              echo "failed to connect to $2" >&2
              exit 1
            fi
            echo "unexpected args: $@" >&2
            exit 1
            """
        )
        val adapter = ScrcpyProcessAdapter(
            ScrcpyProperties(path = tempDir.resolve("unused-scrcpy").toString()),
            AdbExecutor(AdbProperties(path = adbScript))
        )

        val result = adapter.connectTcpip("emulator-5554", "192.168.0.25", 5555)

        assertFalse(result.success)
        assertTrue(result.error!!.contains("failed to connect"))
    }
}
