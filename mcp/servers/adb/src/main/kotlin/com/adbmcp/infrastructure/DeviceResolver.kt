package com.adbmcp.infrastructure

import org.springframework.stereotype.Component

@Component
class DeviceResolver(private val adbExecutor: AdbExecutor) {

    fun resolve(deviceSerial: String?): String {
        val result = adbExecutor.executeRaw("devices")
        val devices = parseDeviceSerials(result.stdout)

        if (deviceSerial != null) {
            return if (devices.contains(deviceSerial)) deviceSerial
            else throw DeviceNotFoundException(devices)
        }

        return when {
            devices.isEmpty() -> throw DeviceNotFoundException(devices)
            devices.size == 1 -> devices[0]
            else -> throw AmbiguousDeviceException(devices)
        }
    }

    private fun parseDeviceSerials(output: String): List<String> {
        return output.lines()
            .drop(1) // skip "List of devices attached" header
            .filter { it.isNotBlank() }
            .mapNotNull { line ->
                val parts = line.split("\\s+".toRegex())
                if (parts.size >= 2 && parts[1] == "device") parts[0] else null
            }
    }
}
