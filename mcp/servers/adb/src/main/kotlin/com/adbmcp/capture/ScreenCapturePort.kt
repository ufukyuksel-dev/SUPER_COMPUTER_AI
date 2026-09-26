package com.adbmcp.capture

interface ScreenCapturePort {
    fun captureScreen(serial: String, scale: Float = 1.0f): ScreenshotResult
}
