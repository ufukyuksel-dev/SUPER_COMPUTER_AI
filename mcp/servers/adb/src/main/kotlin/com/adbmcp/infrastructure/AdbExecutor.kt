package com.adbmcp.infrastructure

import org.springframework.stereotype.Component

@Component
class AdbExecutor(private val adbProperties: AdbProperties) {

    private val adbPath: String by lazy { resolveAdbPath() }

    fun execute(deviceSerial: String, vararg args: String, timeoutMs: Long = adbProperties.defaultTimeoutMs): ProcessResult {
        val command = listOf(adbPath, "-s", deviceSerial) + args.toList()
        return runProcess(command, timeoutMs)
    }

    fun executeRaw(vararg args: String, timeoutMs: Long = adbProperties.defaultTimeoutMs): ProcessResult {
        val command = listOf(adbPath) + args.toList()
        return runProcess(command, timeoutMs)
    }

    fun executeForProcess(deviceSerial: String, vararg args: String): Process {
        val command = listOf(adbPath, "-s", deviceSerial) + args.toList()
        return ProcessBuilder(command)
            .redirectErrorStream(false)
            .start()
    }

    private fun runProcess(command: List<String>, timeoutMs: Long): ProcessResult {
        val startTime = System.currentTimeMillis()
        val process = ProcessBuilder(command)
            .redirectErrorStream(false)
            .start()

        val completed = process.waitFor(timeoutMs, java.util.concurrent.TimeUnit.MILLISECONDS)
        val durationMs = System.currentTimeMillis() - startTime

        if (!completed) {
            process.destroyForcibly()
            throw AdbTimeoutException(command.joinToString(" "), timeoutMs)
        }

        return ProcessResult(
            exitCode = process.exitValue(),
            stdout = process.inputStream.bufferedReader().readText().trim(),
            stderr = process.errorStream.bufferedReader().readText().trim(),
            durationMs = durationMs
        )
    }

    private fun resolveAdbPath(): String {
        if (adbProperties.path != "auto") return adbProperties.path
        return try {
            val result = ProcessBuilder("which", "adb")
                .redirectErrorStream(true)
                .start()
            result.waitFor(5, java.util.concurrent.TimeUnit.SECONDS)
            result.inputStream.bufferedReader().readText().trim().ifEmpty { "adb" }
        } catch (_: Exception) {
            "adb"
        }
    }
}
