package com.adbmcp.capture.internal

import com.adbmcp.writeExecutableScript
import com.adbmcp.infrastructure.AdbExecutor
import com.adbmcp.infrastructure.AdbProperties
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import java.nio.file.Files
import java.nio.file.Path
import java.util.Base64

class AdbCaptureAdapterTest {

    @TempDir
    lateinit var tempDir: Path

    @Test
    fun `capture screen uses configured adb executable`() {
        val commandLog = tempDir.resolve("capture.log")
        val pngFile = tempDir.resolve("screen.png")
        Files.write(
            pngFile,
            Base64.getDecoder().decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO8B9V0AAAAASUVORK5CYII=")
        )
        val adbScript = writeExecutableScript(
            tempDir,
            "fake-adb.sh",
            """
            #!/bin/sh
            echo "$@" >> "${commandLog}"
            if [ "$1" = "-s" ] && [ "$3" = "shell" ] && [ "$4" = "screencap" ]; then
              cat "${pngFile}"
              exit 0
            fi
            if [ "$1" = "-s" ] && [ "$3" = "shell" ] && [ "$4" = "dumpsys" ]; then
              echo "SurfaceOrientation: 1"
              exit 0
            fi
            echo "unexpected args: $@" >&2
            exit 1
            """
        )
        val adapter = AdbCaptureAdapter(AdbExecutor(AdbProperties(path = adbScript)))

        val screenshot = adapter.captureScreen("emulator-5554", 1.0f)

        val loggedCommands = Files.readString(commandLog)
        assertEquals(1, screenshot.width)
        assertEquals(1, screenshot.height)
        assertEquals(90, screenshot.rotation)
        assertTrue(loggedCommands.contains("shell screencap -p"))
        assertTrue(loggedCommands.contains("shell dumpsys input"))
    }
}
