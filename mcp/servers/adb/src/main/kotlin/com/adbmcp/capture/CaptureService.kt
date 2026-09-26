package com.adbmcp.capture

import com.adbmcp.infrastructure.ArtifactManager
import com.adbmcp.infrastructure.DeviceResolver
import com.adbmcp.infrastructure.RecordingActiveException
import com.adbmcp.infrastructure.RecordingNotFoundException
import org.springframework.stereotype.Service
import java.time.Instant
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap

@Service
class CaptureService(
    private val screenCapturePort: ScreenCapturePort,
    private val videoRecordingPort: VideoRecordingPort,
    private val deviceResolver: DeviceResolver,
    private val artifactManager: ArtifactManager
) {
    private val activeRecordings = ConcurrentHashMap<String, AdbRecordingSession>()

    fun screenshot(scale: Float = 1.0f, deviceSerial: String? = null): ScreenshotResult {
        val serial = deviceResolver.resolve(deviceSerial)
        val result = screenCapturePort.captureScreen(serial, scale)
        val hostPath = artifactManager.allocateScreenshotPath(serial)
        java.nio.file.Files.createDirectories(hostPath.parent)
        java.nio.file.Files.write(hostPath, result.imageBytes)
        return result.copy(artifactPath = hostPath.toString())
    }

    fun startVideo(deviceSerial: String? = null): StartVideoResult {
        val serial = deviceResolver.resolve(deviceSerial)

        // Check if already recording on this device
        if (activeRecordings.values.any { it.deviceSerial == serial }) {
            throw RecordingActiveException(serial)
        }

        val recordingId = UUID.randomUUID().toString()
        val deviceFilePath = "/sdcard/recording_$recordingId.mp4"
        val process = videoRecordingPort.startScreenRecord(serial, deviceFilePath)

        activeRecordings[recordingId] = AdbRecordingSession(
            recordingId = recordingId,
            deviceSerial = serial,
            process = process,
            deviceFilePath = deviceFilePath,
            startedAt = Instant.now()
        )

        return StartVideoResult(success = true, recordingId = recordingId)
    }

    fun stopVideo(recordingId: String): StopVideoResult {
        val session = activeRecordings.remove(recordingId)
            ?: throw RecordingNotFoundException(recordingId)

        videoRecordingPort.killRecordingProcess(session.process)

        // Small delay for file finalization on device
        Thread.sleep(1000)

        val hostPath = artifactManager.allocateVideoPath(session.deviceSerial, recordingId)
        java.nio.file.Files.createDirectories(hostPath.parent)
        val pulled = videoRecordingPort.pullRecording(session.deviceSerial, session.deviceFilePath, hostPath.toString())

        videoRecordingPort.deleteDeviceFile(session.deviceSerial, session.deviceFilePath)

        val durationSeconds = java.time.Duration.between(session.startedAt, Instant.now()).seconds

        return if (pulled) {
            StopVideoResult(success = true, artifactPath = hostPath.toString(), durationSeconds = durationSeconds)
        } else {
            StopVideoResult(success = false, error = "Failed to pull recording from device")
        }
    }

    fun getActiveRecordingIds(): Set<String> = activeRecordings.keys.toSet()

    fun getActiveRecordingPaths(): Set<java.nio.file.Path> {
        return activeRecordings.values.mapNotNull { session ->
            artifactManager.allocateVideoPath(session.deviceSerial, session.recordingId)
        }.toSet()
    }
}
