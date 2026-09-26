package com.adbmcp.input

import com.adbmcp.infrastructure.DeviceResolver
import org.springframework.stereotype.Service

@Service
class AutomationService(
    private val inputPort: InputPort,
    private val deviceResolver: DeviceResolver
) {
    fun tap(x: Int, y: Int, deviceSerial: String? = null): TapResult {
        val serial = deviceResolver.resolve(deviceSerial)
        val result = inputPort.tap(serial, x, y)
        return TapResult(success = result.success, x = x, y = y, error = result.error)
    }

    fun swipe(
        x1: Int, y1: Int, x2: Int, y2: Int,
        durationMs: Int = 300, deviceSerial: String? = null
    ): SwipeResult {
        val serial = deviceResolver.resolve(deviceSerial)
        val result = inputPort.swipe(serial, x1, y1, x2, y2, durationMs)
        return SwipeResult(
            success = result.success, x1 = x1, y1 = y1,
            x2 = x2, y2 = y2, durationMs = durationMs, error = result.error
        )
    }

    fun longPress(x: Int, y: Int, durationMs: Int = 1000, deviceSerial: String? = null): TapResult {
        val serial = deviceResolver.resolve(deviceSerial)
        val result = inputPort.longPress(serial, x, y, durationMs)
        return TapResult(success = result.success, x = x, y = y, error = result.error)
    }

    fun typeText(text: String, useAdbKeyboard: Boolean = false, deviceSerial: String? = null): CommandResult {
        val serial = deviceResolver.resolve(deviceSerial)
        return inputPort.typeText(serial, text, useAdbKeyboard)
    }

    fun keyEvent(keycode: String, deviceSerial: String? = null): CommandResult {
        val serial = deviceResolver.resolve(deviceSerial)
        return inputPort.keyEvent(serial, keycode)
    }

    fun imeList(deviceSerial: String? = null): List<String> {
        val serial = deviceResolver.resolve(deviceSerial)
        return inputPort.imeList(serial)
    }

    fun imeSet(imeId: String, deviceSerial: String? = null): CommandResult {
        val serial = deviceResolver.resolve(deviceSerial)
        return inputPort.imeSet(serial, imeId)
    }

    fun imeCurrent(deviceSerial: String? = null): String {
        val serial = deviceResolver.resolve(deviceSerial)
        return inputPort.imeCurrent(serial)
    }
}
