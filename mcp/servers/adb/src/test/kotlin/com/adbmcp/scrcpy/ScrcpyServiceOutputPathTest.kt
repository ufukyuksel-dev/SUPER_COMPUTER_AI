package com.adbmcp.scrcpy

import com.adbmcp.infrastructure.AdbExecutor
import com.adbmcp.infrastructure.AdbProperties
import com.adbmcp.infrastructure.ArtifactManager
import com.adbmcp.infrastructure.ArtifactProperties
import com.adbmcp.infrastructure.DeviceResolver
import com.adbmcp.infrastructure.PathBlockedException
import com.adbmcp.infrastructure.SecurityPolicy
import com.adbmcp.infrastructure.SecurityProperties
import com.adbmcp.writeExecutableScript
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertThrows
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import java.nio.file.Files
import java.nio.file.Path

/** scrcpy_start_record's agent-supplied outputPath must stay inside the private artifact directory. */
class ScrcpyServiceOutputPathTest {

    @TempDir
    lateinit var tempDir: Path

    private val recorded = mutableListOf<String>()

    private fun service(): ScrcpyService {
        val adb = writeExecutableScript(tempDir, "fake-adb.sh", """
            #!/bin/sh
            echo "List of devices attached"
            echo "emulator-5554 device"
            """)
        val port = object : ScrcpyPort {
            override fun startMirror(deviceSerial: String, maxSize: Int?): Process = throw UnsupportedOperationException()
            override fun startRecord(deviceSerial: String, outputPath: String, audioEnabled: Boolean, maxSize: Int?,
                                     videoBitRate: String?): Process {
                recorded += outputPath
                return ProcessBuilder("sleep", "5").start()
            }
            override fun stopSession(process: Process) { process.destroy() }
            override fun connectTcpip(deviceSerial: String, deviceIp: String, port: Int) = throw UnsupportedOperationException()
            override fun isProcessAlive(process: Process) = process.isAlive
            override fun isScrcpyAvailable() = true
        }
        return ScrcpyService(port, DeviceResolver(AdbExecutor(AdbProperties(path = adb))),
            ArtifactManager(ArtifactProperties(baseDir = tempDir.resolve("state/artifacts").toString())),
            SecurityPolicy(SecurityProperties()))
    }

    @Test
    fun `output paths outside the artifact directory are blocked before anything is created`() {
        val svc = service()
        val outside = Files.createDirectories(tempDir.resolve("outside"))
        Files.createDirectories(tempDir.resolve("state/artifacts"))
        Files.createSymbolicLink(tempDir.resolve("state/artifacts/link"), outside)
        for (path in listOf("${tempDir}/elsewhere/v.mp4", "${tempDir}/state/artifacts/../../escape/v.mp4",
                            "${tempDir}/state/artifacts/link/v.mp4", "relative.mp4")) {
            assertThrows(PathBlockedException::class.java, { svc.startRecord(path, deviceSerial = "emulator-5554") }, path)
        }
        assertEquals(emptyList<String>(), recorded)
        assertFalse(Files.exists(tempDir.resolve("elsewhere")))
        assertFalse(Files.exists(tempDir.resolve("escape")))
        assertEquals(emptyList<Path>(), Files.list(outside).use { it.toList() })
    }

    @Test
    fun `an output path inside the artifact directory and the default are accepted`() {
        val svc = service()
        val inside = tempDir.resolve("state/artifacts/videos/mine.mp4").toString()
        svc.startRecord(inside, deviceSerial = "emulator-5554")
        svc.startRecord(null, deviceSerial = "emulator-5554")
        assertEquals(inside, recorded[0])
        assertEquals(true, recorded[1].startsWith(tempDir.resolve("state/artifacts/videos").toString()))
        svc.shutdown()
    }
}
