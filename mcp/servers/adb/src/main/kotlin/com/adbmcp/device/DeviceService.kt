package com.adbmcp.device

import com.adbmcp.infrastructure.DeviceResolver
import org.springframework.stereotype.Service

@Service
class DeviceService(
    private val devicePort: DevicePort,
    private val deviceResolver: DeviceResolver
) {
    @Volatile
    private var sessionDevice: String? = null

    fun listDevices(): List<DeviceInfo> = devicePort.listDevices()

    fun getDeviceInfo(deviceSerial: String? = null): DeviceInfo {
        val serial = resolveWithSessionHint(deviceSerial)
        return devicePort.getDeviceInfo(serial)
    }

    fun getScreenSize(deviceSerial: String? = null): ScreenSizeInfo {
        val serial = resolveWithSessionHint(deviceSerial)
        return devicePort.getScreenSize(serial)
    }

    fun setDevice(deviceSerial: String) {
        val serial = deviceResolver.resolve(deviceSerial)
        sessionDevice = serial
    }

    fun resolveWithSessionHint(deviceSerial: String?): String {
        return deviceResolver.resolve(deviceSerial ?: sessionDevice)
    }
}
