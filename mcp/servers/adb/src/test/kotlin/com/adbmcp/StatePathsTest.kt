package com.adbmcp

import com.adbmcp.infrastructure.ArtifactManager
import com.adbmcp.infrastructure.SecurityProperties
import com.adbmcp.infrastructure.StateDir
import com.adbmcp.scrcpy.ScrcpyProperties
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.springframework.beans.factory.annotation.Autowired
import org.springframework.boot.test.context.SpringBootTest
import org.springframework.core.env.Environment
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.Paths

/** Every runtime path derives from the state directory (build.gradle.kts points it at build/test-state). */
@SpringBootTest
class StatePathsTest(
    @Autowired private val environment: Environment,
    @Autowired private val artifacts: ArtifactManager,
    @Autowired private val scrcpy: ScrcpyProperties,
    @Autowired private val security: SecurityProperties
) {
    private val state: Path = Paths.get(System.getProperty(StateDir.PROPERTY)).toAbsolutePath().normalize()

    private fun abs(value: String): Path = Paths.get(value).toAbsolutePath().normalize()

    @Test
    fun `artifacts, recordings, logs and host transfers live under the state directory`() {
        assertTrue(state.endsWith(Paths.get("build", "test-state")), "test JVM must use build/test-state: $state")
        assertEquals(state.resolve("artifacts"), artifacts.getBaseDir().toAbsolutePath().normalize())
        assertTrue(Files.isDirectory(artifacts.getScreenshotsDir()))
        assertEquals(state.resolve("artifacts/videos"), abs(scrcpy.recordingDir))
        assertEquals(state.resolve("logs/adb-mcp-server.log"), abs(environment.getProperty("logging.file.name")!!))
        assertEquals(listOf(state.resolve("transfers")), security.fileTransfer.hostAllowedPaths.map(::abs))
    }

    @Test
    fun `nothing is written to the working directory`() {
        for (name in listOf("artifacts", "logs", "transfers")) {
            assertFalse(Files.exists(Paths.get(name)), "$name must not be created in ${Paths.get("").toAbsolutePath()}")
        }
    }
}
