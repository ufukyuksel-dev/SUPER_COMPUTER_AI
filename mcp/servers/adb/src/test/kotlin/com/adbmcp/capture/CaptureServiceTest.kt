package com.adbmcp.capture

import com.adbmcp.writeExecutableScript
import com.adbmcp.infrastructure.AdbExecutor
import com.adbmcp.infrastructure.AdbProperties
import com.adbmcp.infrastructure.ArtifactManager
import com.adbmcp.infrastructure.ArtifactProperties
import com.adbmcp.infrastructure.DeviceResolver
import org.junit.jupiter.api.Assertions.assertNotNull
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import java.nio.file.Files
import java.nio.file.Path

class CaptureServiceTest {

    @TempDir
    lateinit var tempDir: Path

    @Test
    fun `screenshot saves artifact under screenshots directory`() {
        val adbScript = writeExecutableScript(
            tempDir,
            "fake-adb.sh",
            """
            #!/bin/sh
            if [ "$1" = "devices" ]; then
              echo "List of devices attached"
              echo "emulator-5554 device"
              exit 0
            fi
            echo "unexpected args: $@" >&2
            exit 1
            """
        )
        val captureService = CaptureService(
            screenCapturePort = object : ScreenCapturePort {
                override fun captureScreen(serial: String, scale: Float): ScreenshotResult {
                    return ScreenshotResult(
                        imageBytes = "png-data".toByteArray(),
                        width = 1080,
                        height = 2400,
                        rotation = 0,
                        timestamp = 123L
                    )
                }
            },
            videoRecordingPort = object : VideoRecordingPort {
                override fun startScreenRecord(deviceSerial: String, deviceFilePath: String, maxDurationSeconds: Int): Process {
                    throw UnsupportedOperationException()
                }

                override fun pullRecording(deviceSerial: String, devicePath: String, hostPath: String): Boolean {
                    throw UnsupportedOperationException()
                }

                override fun killRecordingProcess(process: Process) {
                    throw UnsupportedOperationException()
                }

                override fun deleteDeviceFile(deviceSerial: String, path: String) {
                    throw UnsupportedOperationException()
                }
            },
            deviceResolver = DeviceResolver(AdbExecutor(AdbProperties(path = adbScript))),
            artifactManager = ArtifactManager(
                ArtifactProperties(
                    baseDir = tempDir.toString(),
                    screenshotsDir = "screenshots",
                    videosDir = "videos",
                    uiDumpsDir = "ui-dumps",
                    pulledFilesDir = "pulled"
                )
            )
        )

        val screenshot = captureService.screenshot(deviceSerial = "emulator-5554")

        assertNotNull(screenshot.artifactPath)
        val artifactPath = Path.of(screenshot.artifactPath!!)
        assertTrue(Files.exists(artifactPath))
        assertTrue(artifactPath.startsWith(tempDir.resolve("screenshots")))
        assertTrue(Files.readAllBytes(artifactPath).contentEquals("png-data".toByteArray()))
    }
}
