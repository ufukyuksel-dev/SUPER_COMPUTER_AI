package com.adbmcp.scrcpy

interface ScrcpyPort {
    fun startMirror(deviceSerial: String, maxSize: Int? = null): Process
    fun startRecord(
        deviceSerial: String,
        outputPath: String,
        audioEnabled: Boolean = true,
        maxSize: Int? = null,
        videoBitRate: String? = null
    ): Process

    fun stopSession(process: Process)
    fun connectTcpip(deviceSerial: String, deviceIp: String, port: Int = 5555): ScrcpyConnectResult
    fun isProcessAlive(process: Process): Boolean
    fun isScrcpyAvailable(): Boolean
}
