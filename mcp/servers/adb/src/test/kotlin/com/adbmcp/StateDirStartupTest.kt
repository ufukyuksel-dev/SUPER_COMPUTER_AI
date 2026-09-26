package com.adbmcp

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertNotEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.Paths
import java.nio.file.attribute.PosixFilePermissions
import java.util.concurrent.TimeUnit

/** Real start-up of the stdio server in a separate JVM (the order main() -> Spring -> logging is not simulated). */
class StateDirStartupTest {

    @TempDir
    lateinit var tempDir: Path

    private fun start(vararg args: String, env: Map<String, String> = emptyMap()): Process {
        val cwd = Files.createDirectories(tempDir.resolve("cwd"))
        val java = Paths.get(System.getProperty("java.home"), "bin", "java").toString()
        val command = listOf(java, "-Duser.home=${tempDir.resolve("home")}", "-cp", System.getProperty("java.class.path"),
            "com.adbmcp.AdbMcpServerApplicationKt", *args)
        val pb = ProcessBuilder(command).directory(cwd.toFile())
            .redirectOutput(ProcessBuilder.Redirect.DISCARD)
            .redirectError(tempDir.resolve("stderr.txt").toFile())
        pb.environment().remove("ADB_MCP_STATE_DIR")
        pb.environment().putAll(env)
        return pb.start()
    }

    private fun await(path: Path, process: Process) {
        val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(60)
        while (!Files.exists(path) && process.isAlive && System.nanoTime() < deadline) Thread.sleep(100)
        assertTrue(Files.exists(path), "no $path; stderr: ${Files.readString(tempDir.resolve("stderr.txt")).takeLast(3000)}")
    }

    @Test
    fun `a command-line state dir that differs from the environment is the one used and made private`() {
        val envDir = tempDir.resolve("env-state")
        val argDir = tempDir.resolve("arg-state")
        val process = start("--adb-mcp.state-dir=$argDir", env = mapOf("ADB_MCP_STATE_DIR" to envDir.toString()))
        try {
            await(argDir.resolve("logs/adb-mcp-server.log"), process)   // written by logging
            await(argDir.resolve("artifacts/screenshots"), process)     // created by ArtifactManager
        } finally {
            process.destroy(); process.waitFor(20, TimeUnit.SECONDS)
        }
        assertEquals(PosixFilePermissions.fromString("rwx------"), Files.getPosixFilePermissions(argDir))
        assertFalse(Files.exists(envDir), "the lower-priority environment value must not be created")
        assertEquals(emptyList<Path>(), Files.list(tempDir.resolve("cwd")).use { it.toList() })
    }

    @Test
    fun `a relative state dir or a redirected log file stops start-up before anything is written`() {
        val s = tempDir.resolve("s")
        for (args in listOf(arrayOf("--adb-mcp.state-dir=relative-state"),
                            arrayOf("--adb-mcp.state-dir=$s", "--logging.file.name=${tempDir.resolve("open.log")}"),
                            arrayOf("--adb-mcp.state-dir=$s", "--artifacts.screenshots-dir=${tempDir.resolve("open-shots")}"),
                            arrayOf("--adb-mcp.state-dir=$s", "--artifacts.pulled-files-dir=../../open-pulled"))) {
            val process = start(*args)
            assertTrue(process.waitFor(60, TimeUnit.SECONDS), "start-up did not stop for ${args.toList()}")
            assertNotEquals(0, process.exitValue())
            assertEquals(emptyList<Path>(), Files.list(tempDir.resolve("cwd")).use { it.toList() })
            for (name in listOf("open.log", "open-shots", "open-pulled")) assertFalse(Files.exists(tempDir.resolve(name)), name)
        }
    }
}
