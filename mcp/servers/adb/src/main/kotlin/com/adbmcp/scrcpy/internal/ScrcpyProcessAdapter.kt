package com.adbmcp.scrcpy.internal

import com.adbmcp.infrastructure.AdbExecutor
import com.adbmcp.scrcpy.ScrcpyConnectResult
import com.adbmcp.scrcpy.ScrcpyPort
import com.adbmcp.scrcpy.ScrcpyProperties
import org.springframework.stereotype.Component

@Component
class ScrcpyProcessAdapter(
    private val scrcpyProperties: ScrcpyProperties,
    private val adbExecutor: AdbExecutor
) : ScrcpyPort {

    private val scrcpyPath: String by lazy { resolveScrcpyPath() }

    override fun startMirror(deviceSerial: String, maxSize: Int?): Process {
        val args = mutableListOf(scrcpyPath, "-s", deviceSerial)
        val size = maxSize ?: scrcpyProperties.defaultMaxSize
        args.addAll(listOf("--max-size", "$size"))
        return ProcessBuilder(args).redirectErrorStream(false).start()
    }

    override fun startRecord(
        deviceSerial: String,
        outputPath: String,
        audioEnabled: Boolean,
        maxSize: Int?,
        videoBitRate: String?
    ): Process {
        val args = mutableListOf(scrcpyPath, "-s", deviceSerial, "--no-window")
        args.addAll(listOf("--record", outputPath))
        val size = maxSize ?: scrcpyProperties.defaultMaxSize
        args.addAll(listOf("--max-size", "$size"))
        val bitRate = videoBitRate ?: scrcpyProperties.defaultVideoBitRate
        args.addAll(listOf("--video-bit-rate", bitRate))
        if (!audioEnabled) args.add("--no-audio")
        return ProcessBuilder(args).redirectErrorStream(false).start()
    }

    override fun stopSession(process: Process) {
        if (!process.isAlive) return
        try {
            // Send SIGINT for graceful shutdown (scrcpy needs this for file finalization)
            val pid = process.pid()
            Runtime.getRuntime().exec(arrayOf("kill", "-2", "$pid"))
            process.waitFor(5, java.util.concurrent.TimeUnit.SECONDS)
        } catch (_: Exception) {
            // Fallback to destroy
        }
        if (process.isAlive) {
            process.destroy()
            process.waitFor(3, java.util.concurrent.TimeUnit.SECONDS)
        }
        if (process.isAlive) {
            process.destroyForcibly()
        }
    }

    override fun connectTcpip(deviceSerial: String, deviceIp: String, port: Int): ScrcpyConnectResult {
        val tcpipResult = adbExecutor.execute(deviceSerial, "tcpip", "$port")
        if (!tcpipResult.isSuccess) {
            val error = tcpipResult.stderr.ifBlank { tcpipResult.stdout.ifBlank { "Failed to enable TCP/IP mode" } }
            return ScrcpyConnectResult(success = false, error = error)
        }

        Thread.sleep(1000)
        val address = "$deviceIp:$port"
        val result = adbExecutor.executeRaw("connect", address)
        val output = listOf(result.stdout, result.stderr)
            .filter { it.isNotBlank() }
            .joinToString("\n")

        val connected = result.isSuccess && (
                output.contains("connected to", ignoreCase = true) ||
                        output.contains("already connected to", ignoreCase = true)
                )

        return if (connected) {
            ScrcpyConnectResult(success = true, deviceSerial = address)
        } else {
            ScrcpyConnectResult(
                success = false,
                error = output.ifBlank { "Failed to connect to $address" }
            )
        }
    }

    override fun isProcessAlive(process: Process): Boolean = process.isAlive

    override fun isScrcpyAvailable(): Boolean {
        return try {
            val process = ProcessBuilder(scrcpyPath, "--version")
                .redirectErrorStream(true)
                .start()
            process.waitFor(5, java.util.concurrent.TimeUnit.SECONDS)
            process.exitValue() == 0
        } catch (_: Exception) {
            false
        }
    }

    private fun resolveScrcpyPath(): String {
        if (scrcpyProperties.path != "auto") return scrcpyProperties.path
        return try {
            val result = ProcessBuilder("which", "scrcpy")
                .redirectErrorStream(true)
                .start()
            result.waitFor(5, java.util.concurrent.TimeUnit.SECONDS)
            result.inputStream.bufferedReader().readText().trim().ifEmpty { "scrcpy" }
        } catch (_: Exception) {
            "scrcpy"
        }
    }
}
