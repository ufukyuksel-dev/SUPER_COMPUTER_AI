package com.adbmcp.capture.internal

import com.adbmcp.capture.VideoRecordingPort
import com.adbmcp.infrastructure.AdbExecutor
import org.springframework.stereotype.Component

@Component
class AdbVideoAdapter(private val adbExecutor: AdbExecutor) : VideoRecordingPort {

    override fun startScreenRecord(deviceSerial: String, deviceFilePath: String, maxDurationSeconds: Int): Process {
        return adbExecutor.executeForProcess(
            deviceSerial, "shell", "screenrecord",
            "--time-limit", "$maxDurationSeconds",
            deviceFilePath
        )
    }

    override fun pullRecording(deviceSerial: String, devicePath: String, hostPath: String): Boolean {
        val result = adbExecutor.execute(deviceSerial, "pull", devicePath, hostPath, timeoutMs = 60000)
        return result.isSuccess
    }

    override fun killRecordingProcess(process: Process) {
        if (process.isAlive) {
            process.destroy()
            process.waitFor(5, java.util.concurrent.TimeUnit.SECONDS)
            if (process.isAlive) {
                process.destroyForcibly()
            }
        }
    }

    override fun deleteDeviceFile(deviceSerial: String, path: String) {
        adbExecutor.execute(deviceSerial, "shell", "rm", "-f", path)
    }
}
