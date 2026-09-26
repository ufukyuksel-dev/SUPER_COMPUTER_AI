package com.adbmcp.file

import com.adbmcp.input.CommandResult

interface FileTransferPort {
    fun pushFile(deviceSerial: String, localPath: String, remotePath: String): CommandResult
    fun pullFile(deviceSerial: String, remotePath: String, localPath: String): CommandResult
}
