package com.adbmcp.capture.internal

import com.adbmcp.capture.ScreenCapturePort
import com.adbmcp.capture.ScreenshotResult
import com.adbmcp.infrastructure.AdbExecutor
import org.springframework.stereotype.Component
import java.awt.image.BufferedImage
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import javax.imageio.ImageIO

@Component
class AdbCaptureAdapter(private val adbExecutor: AdbExecutor) : ScreenCapturePort {

    override fun captureScreen(serial: String, scale: Float): ScreenshotResult {
        val process = adbExecutor.executeForProcess(serial, "shell", "screencap", "-p")

        val pngBytes = process.inputStream.readAllBytes()
        process.waitFor(30, java.util.concurrent.TimeUnit.SECONDS)

        var image = ImageIO.read(ByteArrayInputStream(pngBytes))
        val originalWidth = image.width
        val originalHeight = image.height

        if (scale < 1.0f) {
            val newWidth = (originalWidth * scale).toInt()
            val newHeight = (originalHeight * scale).toInt()
            val scaled = BufferedImage(newWidth, newHeight, BufferedImage.TYPE_INT_ARGB)
            val g = scaled.createGraphics()
            g.drawImage(image, 0, 0, newWidth, newHeight, null)
            g.dispose()
            image = scaled
        }

        val outputStream = ByteArrayOutputStream()
        ImageIO.write(image, "png", outputStream)
        val imageBytes = outputStream.toByteArray()

        val rotation = getRotation(serial)

        return ScreenshotResult(
            imageBytes = imageBytes,
            width = originalWidth,
            height = originalHeight,
            rotation = rotation,
            timestamp = System.currentTimeMillis()
        )
    }

    private fun getRotation(serial: String): Int {
        return try {
            val result = adbExecutor.execute(serial, "shell", "dumpsys", "input", timeoutMs = 5000)
            val line = result.stdout.lines()
                .firstOrNull { it.contains("SurfaceOrientation") }
            val value = line?.substringAfterLast(":")?.trim()?.toIntOrNull() ?: 0
            value * 90
        } catch (_: Exception) {
            0
        }
    }
}
