package com.adbmcp.intent.internal

import com.adbmcp.writeExecutableScript
import com.adbmcp.infrastructure.AdbExecutor
import com.adbmcp.infrastructure.AdbProperties
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import java.nio.file.Files
import java.nio.file.Path

class AdbIntentAdapterTest {

    @TempDir
    lateinit var tempDir: Path

    @Test
    fun `filtered package listing keeps package names and does not use f flag`() {
        val commandLog = tempDir.resolve("adb-commands.log")
        val adbScript = writeExecutableScript(
            tempDir,
            "fake-adb.sh",
            """
            #!/bin/sh
            echo "$@" >> "${commandLog}"
            if [ "$1" = "-s" ] && [ "$3" = "shell" ] && [ "$4" = "pm" ] && [ "$5" = "list" ] && [ "$6" = "packages" ]; then
              echo "package:/data/app/~~abc/base.apk=com.example.alpha"
              echo "package:com.example.beta"
              exit 0
            fi
            echo "unexpected args: $@" >&2
            exit 1
            """
        )
        val adapter = AdbIntentAdapter(AdbExecutor(AdbProperties(path = adbScript)))

        val packages = adapter.listPackages("emulator-5554", "com.example")

        assertEquals(listOf("com.example.alpha", "com.example.beta"), packages)
        assertFalse(Files.readString(commandLog).contains(" -f "))
    }
}
