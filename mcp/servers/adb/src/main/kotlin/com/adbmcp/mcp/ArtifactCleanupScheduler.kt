package com.adbmcp.mcp

import com.adbmcp.capture.CaptureService
import com.adbmcp.infrastructure.ArtifactManager
import com.adbmcp.scrcpy.ScrcpyService
import org.springframework.scheduling.annotation.Scheduled
import org.springframework.stereotype.Component

@Component
class ArtifactCleanupScheduler(
    private val artifactManager: ArtifactManager,
    private val captureService: CaptureService,
    private val scrcpyService: ScrcpyService
) {
    @Scheduled(fixedRate = 3600000) // Every hour
    fun scheduledCleanup() {
        val protectedPaths = captureService.getActiveRecordingPaths() +
                scrcpyService.getActiveSessionPaths()
        artifactManager.cleanupByAge(protectedPaths)
        artifactManager.cleanupBySize(protectedPaths)
    }
}
