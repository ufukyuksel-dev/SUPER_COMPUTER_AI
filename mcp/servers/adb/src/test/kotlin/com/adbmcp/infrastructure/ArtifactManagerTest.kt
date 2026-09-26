package com.adbmcp.infrastructure

import org.junit.jupiter.api.Assertions.assertNotEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import java.nio.file.Path

class ArtifactManagerTest {

    @TempDir
    lateinit var tempDir: Path

    @Test
    fun `allocate pull path produces unique filenames`() {
        val manager = ArtifactManager(
            ArtifactProperties(
                baseDir = tempDir.toString(),
                screenshotsDir = "screenshots",
                videosDir = "videos",
                uiDumpsDir = "ui-dumps",
                pulledFilesDir = "pulled"
            )
        )

        val first = manager.allocatePullPath("emulator-5554", "/sdcard/log.txt")
        val second = manager.allocatePullPath("emulator-5554", "/sdcard/log.txt")

        assertNotEquals(first, second)
        assertTrue(first.fileName.toString().endsWith("_log.txt"))
        assertTrue(second.fileName.toString().endsWith("_log.txt"))
    }
}
