package com.adbmcp.infrastructure

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertThrows
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import org.springframework.boot.SpringApplication
import org.springframework.core.env.MapPropertySource
import org.springframework.core.env.StandardEnvironment
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.attribute.PosixFilePermissions

class StateDirTest {

    @TempDir
    lateinit var tempDir: Path

    private val private = PosixFilePermissions.fromString("rwx------")

    @Test
    fun `parse expands home and refuses relative or empty values`() {
        assertEquals(tempDir.resolve("h/s"), StateDir.parse("~/s", home = tempDir.resolve("h").toString()))
        assertEquals(tempDir.resolve("x"), StateDir.parse("$tempDir/y/../x"))
        for (bad in listOf("state", "./state", "~user/state", "", " ", null)) {
            assertThrows(IllegalArgumentException::class.java, { StateDir.parse(bad) }, "accepted '$bad'")
        }
    }

    @Test
    fun `ensurePrivate creates 0700 and tightens an existing directory`() {
        val dir = StateDir.ensurePrivate(tempDir.resolve("a/b/state"))
        assertEquals(private, Files.getPosixFilePermissions(dir))
        Files.setPosixFilePermissions(dir, PosixFilePermissions.fromString("rwxr-xr-x"))
        StateDir.ensurePrivate(dir)
        assertEquals(private, Files.getPosixFilePermissions(dir))
    }

    private fun environment(vararg layers: Map<String, Any>): StandardEnvironment {
        val env = StandardEnvironment()
        layers.forEachIndexed { i, layer -> env.propertySources.addFirst(MapPropertySource("layer$i", layer)) }
        return env
    }

    private fun process(env: StandardEnvironment) = StateDirEnvironmentPostProcessor().postProcessEnvironment(env, SpringApplication())

    @Test
    fun `the effective value is made private and pinned, not a lower-priority one`() {
        val yml = mapOf(StateDir.PROPERTY to "${tempDir}/from-env", "logging.file.name" to "\${adb-mcp.state-dir}/logs/x.log",
            "artifacts.base-dir" to "\${adb-mcp.state-dir}/artifacts", "scrcpy.recording-dir" to "\${adb-mcp.state-dir}/artifacts/videos")
        val commandLine = mapOf(StateDir.PROPERTY to "${tempDir}/from-arg/../from-arg")
        val env = environment(yml, commandLine)
        process(env)
        assertEquals(tempDir.resolve("from-arg").toString(), env.getProperty(StateDir.PROPERTY))
        assertEquals(tempDir.resolve("from-arg/logs/x.log").toString(), env.getProperty("logging.file.name"))
        assertEquals(private, Files.getPosixFilePermissions(tempDir.resolve("from-arg")))
        assertFalse(Files.exists(tempDir.resolve("from-env")))
    }

    @Test
    fun `realTarget follows symlinks and applies dot-dot to the real parent`() {
        val outside = Files.createDirectories(tempDir.resolve("outside"))
        val state = Files.createDirectories(tempDir.resolve("state"))
        Files.createSymbolicLink(state.resolve("link"), outside)
        assertEquals(outside.toRealPath().resolve("new/x"), StateDir.realTarget(state.resolve("link/new/x")))
        assertFalse(StateDir.isInside(state.resolve("link/x"), state))
        assertFalse(StateDir.isInside(state.resolve("a/../../outside"), state))
        // `..` after a symlink goes to the link target's parent, as the OS does, not back into state/
        assertEquals(tempDir.toRealPath().resolve("x"), StateDir.realTarget(state.resolve("link/../x")))
        assertTrue(StateDir.isInside(state.resolve("new/deeper/../file"), state))
        Files.createSymbolicLink(state.resolve("dangling"), tempDir.resolve("missing"))
        assertThrows(IllegalArgumentException::class.java) { StateDir.realTarget(state.resolve("dangling/x")) }
    }

    @Test
    fun `write locations redirected outside the state directory are refused`() {
        val inside = mapOf(StateDir.PROPERTY to "$tempDir/state", "artifacts.base-dir" to "$tempDir/state/artifacts",
            "scrcpy.recording-dir" to "$tempDir/state/artifacts/videos")
        process(environment(inside))   // the reference configuration is accepted
        for (key in StateDirEnvironmentPostProcessor.WRITTEN) {
            val env = environment(inside + (key to "$tempDir/elsewhere/x"))
            assertThrows(IllegalStateException::class.java, { process(env) }, key)
        }
        assertFalse(Files.exists(tempDir.resolve("elsewhere")), "a refused target must not be created")
        for (fallback in listOf("./artifacts", "")) {   // relative or blank base dir = the working directory
            assertThrows(IllegalStateException::class.java) { process(environment(inside + ("artifacts.base-dir" to fallback))) }
        }
        // unset keys use the property classes' relative defaults, which are refused as well
        assertThrows(IllegalStateException::class.java) { process(environment(mapOf(StateDir.PROPERTY to "$tempDir/state"))) }
        assertEquals(com.adbmcp.scrcpy.ScrcpyProperties().recordingDir, StateDirEnvironmentPostProcessor.SCRCPY_RECORDING_DEFAULT)
        assertThrows(IllegalArgumentException::class.java) { process(environment(mapOf(StateDir.PROPERTY to "rel"))) }
    }

    @Test
    fun `artifact subdirectories are checked on their final resolved path`() {
        val state = "$tempDir/state"
        val base = mapOf(StateDir.PROPERTY to state, "artifacts.base-dir" to "$state/artifacts",
            "scrcpy.recording-dir" to "$state/artifacts/videos")
        for ((key, _) in StateDirEnvironmentPostProcessor.ARTIFACT_SUBDIRS) {
            for (escape in listOf("$tempDir/abs-out", "../../dotdot-out", "sub/../../../dotdot-out")) {
                assertThrows(IllegalStateException::class.java, { process(environment(base + (key to escape))) }, "$key=$escape")
            }
        }
        // a symlink already inside the state directory that points outside is caught too
        val outside = Files.createDirectories(tempDir.resolve("link-target"))
        Files.createDirectories(Path.of(state, "artifacts"))
        Files.createSymbolicLink(Path.of(state, "artifacts", "screenshots"), outside)
        assertThrows(IllegalStateException::class.java) { process(environment(base)) }
        Files.createSymbolicLink(Path.of(state, "artifacts", "ui-dumps"), tempDir.resolve("nowhere"))   // dangling
        Files.delete(Path.of(state, "artifacts", "screenshots"))
        assertThrows(IllegalStateException::class.java) { process(environment(base)) }
        Files.delete(Path.of(state, "artifacts", "ui-dumps"))
        process(environment(base + ("artifacts.videos-dir" to "rec/../clips")))   // stays inside: accepted
        for (name in listOf("abs-out", "dotdot-out", "nowhere")) {
            assertFalse(Files.exists(tempDir.resolve(name)), "$name must not be created")
        }
        assertEquals(emptyList<Path>(), Files.list(outside).use { it.toList() })
    }
}
