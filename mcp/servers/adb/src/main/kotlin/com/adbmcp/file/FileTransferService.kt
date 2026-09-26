package com.adbmcp.file

import com.adbmcp.infrastructure.ArtifactManager
import com.adbmcp.infrastructure.DeviceResolver
import com.adbmcp.infrastructure.PathBlockedException
import com.adbmcp.infrastructure.SecurityPolicy
import com.adbmcp.infrastructure.ToolDisabledException
import org.springframework.stereotype.Service

@Service
class FileTransferService(
    private val fileTransferPort: FileTransferPort,
    private val deviceResolver: DeviceResolver,
    private val securityPolicy: SecurityPolicy,
    private val artifactManager: ArtifactManager
) {
    fun pushFile(localPath: String, remotePath: String, deviceSerial: String? = null): PushFileResult {
        if (!securityPolicy.isToolEnabled("push-file")) {
            throw ToolDisabledException("push-file")
        }

        val hostValidation = securityPolicy.validateHostPath(localPath)
        if (!hostValidation.valid) throw PathBlockedException(localPath)

        val deviceValidation = securityPolicy.validateDevicePath(remotePath)
        if (!deviceValidation.valid) throw PathBlockedException(remotePath)

        val serial = deviceResolver.resolve(deviceSerial)
        val result = fileTransferPort.pushFile(serial, localPath, remotePath)

        return PushFileResult(success = result.success, devicePath = remotePath, error = result.error)
    }

    fun pullFile(remotePath: String, deviceSerial: String? = null): PullFileResult {
        val deviceValidation = securityPolicy.validateDevicePath(remotePath)
        if (!deviceValidation.valid) throw PathBlockedException(remotePath)

        val serial = deviceResolver.resolve(deviceSerial)
        val hostPath = artifactManager.allocatePullPath(serial, remotePath)
        java.nio.file.Files.createDirectories(hostPath.parent)

        val result = fileTransferPort.pullFile(serial, remotePath, hostPath.toString())

        return PullFileResult(success = result.success, artifactPath = hostPath.toString(), error = result.error)
    }
}
