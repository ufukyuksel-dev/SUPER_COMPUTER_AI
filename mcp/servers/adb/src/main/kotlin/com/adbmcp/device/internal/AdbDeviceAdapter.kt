package com.adbmcp.device.internal

import com.adbmcp.device.DeviceInfo
import com.adbmcp.device.DevicePort
import com.adbmcp.device.ScreenSizeInfo
import com.adbmcp.infrastructure.AdbExecutor
import org.springframework.stereotype.Component

@Component
class AdbDeviceAdapter(private val adbExecutor: AdbExecutor) : DevicePort {

    override fun listDevices(): List<DeviceInfo> {
        val result = adbExecutor.executeRaw("devices", "-l")
        return parseDeviceList(result.stdout)
    }

    override fun getDeviceInfo(serial: String): DeviceInfo {
        val basic = getBasicInfo(serial)
        val props = getProperties(serial)
        val displayInfo = getDisplayInfo(serial)

        return basic.copy(
            androidVersion = props["ro.build.version.release"],
            sdkVersion = props["ro.build.version.sdk"]?.toIntOrNull(),
            resolution = displayInfo.resolution,
            density = displayInfo.density,
            rotation = displayInfo.rotation
        )
    }

    override fun getScreenSize(serial: String): ScreenSizeInfo {
        val result = adbExecutor.execute(serial, "shell", "wm", "size")
        return parseScreenSize(result.stdout)
    }

    private fun getBasicInfo(serial: String): DeviceInfo {
        val result = adbExecutor.executeRaw("devices", "-l")
        val devices = parseDeviceList(result.stdout)
        return devices.find { it.serial == serial }
            ?: DeviceInfo(serial = serial)
    }

    private fun getProperties(serial: String): Map<String, String> {
        val result = adbExecutor.execute(serial, "shell", "getprop")
        val props = mutableMapOf<String, String>()
        val regex = "\\[(.+?)]: \\[(.+?)]".toRegex()
        for (line in result.stdout.lines()) {
            val match = regex.find(line)
            if (match != null) {
                props[match.groupValues[1]] = match.groupValues[2]
            }
        }
        return props
    }

    private fun getDisplayInfo(serial: String): DisplayInfo {
        val sizeResult = adbExecutor.execute(serial, "shell", "wm", "size")
        val densityResult = adbExecutor.execute(serial, "shell", "wm", "density")
        val rotationResult = adbExecutor.execute(serial, "shell", "dumpsys", "input",
            timeoutMs = 5000)
        val screenSize = parseScreenSize(sizeResult.stdout)

        val resolution = screenSize.activeSize
        val density = densityResult.stdout.substringAfter("Physical density: ", "").trim().toIntOrNull()

        val rotationLine = rotationResult.stdout.lines()
            .firstOrNull { it.contains("SurfaceOrientation") }
        val rotation = rotationLine?.substringAfterLast(":")?.trim()?.toIntOrNull()?.times(90)

        return DisplayInfo(resolution, density, rotation)
    }

    private fun parseScreenSize(output: String): ScreenSizeInfo {
        val physicalSize = output.lines()
            .firstOrNull { it.startsWith("Physical size:") }
            ?.substringAfter(":")
            ?.trim()
            ?.ifEmpty { null }
        val overrideSize = output.lines()
            .firstOrNull { it.startsWith("Override size:") }
            ?.substringAfter(":")
            ?.trim()
            ?.ifEmpty { null }
        val activeSize = overrideSize ?: physicalSize
        val (width, height) = parseDimensions(activeSize)
        return ScreenSizeInfo(
            width = width,
            height = height,
            activeSize = activeSize,
            physicalSize = physicalSize,
            overrideSize = overrideSize
        )
    }

    private fun parseDimensions(size: String?): Pair<Int?, Int?> {
        if (size == null || !size.contains("x")) return null to null
        val parts = size.split("x", limit = 2)
        return parts[0].trim().toIntOrNull() to parts[1].trim().toIntOrNull()
    }

    private fun parseDeviceList(output: String): List<DeviceInfo> {
        return output.lines()
            .drop(1)
            .filter { it.isNotBlank() }
            .mapNotNull { line ->
                val parts = line.split("\\s+".toRegex())
                if (parts.size < 2) return@mapNotNull null

                val serial = parts[0]
                val state = parts[1]

                val propMap = parts.drop(2).associate { prop ->
                    val kv = prop.split(":", limit = 2)
                    if (kv.size == 2) kv[0] to kv[1] else prop to ""
                }

                DeviceInfo(
                    serial = serial,
                    state = state,
                    model = propMap["model"],
                    product = propMap["product"],
                    device = propMap["device"],
                    transportId = propMap["transport_id"]
                )
            }
    }

    private data class DisplayInfo(
        val resolution: String?,
        val density: Int?,
        val rotation: Int?
    )
}
