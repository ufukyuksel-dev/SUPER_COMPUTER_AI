package com.adbmcp.file.internal

import com.adbmcp.file.FileTransferPort
import com.adbmcp.infrastructure.AdbExecutor
import com.adbmcp.input.CommandResult
import org.springframework.stereotype.Component

@Component
class AdbFileAdapter(private val adbExecutor: AdbExecutor) : FileTransferPort {

    override fun pushFile(deviceSerial: String, localPath: String, remotePath: String): CommandResult {
        val result = adbExecutor.execute(deviceSerial, "push", localPath, remotePath, timeoutMs = 120000)
        return CommandResult(success = result.isSuccess, error = result.stderr.ifEmpty { null })
    }

    override fun pullFile(deviceSerial: String, remotePath: String, localPath: String): CommandResult {
        val result = adbExecutor.execute(deviceSerial, "pull", remotePath, localPath, timeoutMs = 120000)
        return CommandResult(success = result.isSuccess, error = result.stderr.ifEmpty { null })
    }
}
