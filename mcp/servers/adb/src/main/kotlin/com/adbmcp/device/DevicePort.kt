package com.adbmcp.device

interface DevicePort {
    fun listDevices(): List<DeviceInfo>
    fun getDeviceInfo(serial: String): DeviceInfo
    fun getScreenSize(serial: String): ScreenSizeInfo
}
