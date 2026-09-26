package com.adbmcp.capture

interface VideoRecordingPort {
    fun startScreenRecord(deviceSerial: String, deviceFilePath: String, maxDurationSeconds: Int = 180): Process
    fun pullRecording(deviceSerial: String, devicePath: String, hostPath: String): Boolean
    fun killRecordingProcess(process: Process)
    fun deleteDeviceFile(deviceSerial: String, path: String)
}
