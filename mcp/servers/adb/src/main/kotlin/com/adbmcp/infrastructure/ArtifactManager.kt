package com.adbmcp.infrastructure

import jakarta.annotation.PostConstruct
import org.springframework.stereotype.Component
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.Paths
import java.time.Instant
import java.time.temporal.ChronoUnit
import java.util.Base64
import java.util.UUID

@Component
class ArtifactManager(private val artifactProperties: ArtifactProperties) {

    fun getBaseDir(): Path = Paths.get(artifactProperties.baseDir)
    fun getScreenshotsDir(): Path = getBaseDir().resolve(artifactProperties.screenshotsDir)
    fun getVideosDir(): Path = getBaseDir().resolve(artifactProperties.videosDir)
    fun getUiDumpsDir(): Path = getBaseDir().resolve(artifactProperties.uiDumpsDir)
    fun getPulledFilesDir(): Path = getBaseDir().resolve(artifactProperties.pulledFilesDir)

    fun allocateScreenshotPath(deviceSerial: String): Path {
        val timestamp = java.time.LocalDateTime.now()
            .format(java.time.format.DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss"))
        val sanitizedSerial = deviceSerial.replace(":", "_")
        return getScreenshotsDir().resolve("screenshot_${sanitizedSerial}_$timestamp.png")
    }

    fun allocateVideoPath(deviceSerial: String, recordingId: String): Path {
        val sanitizedSerial = deviceSerial.replace(":", "_")
        return getVideosDir().resolve("video_${sanitizedSerial}_$recordingId.mp4")
    }

    fun allocateUiDumpPath(deviceSerial: String): Path {
        val timestamp = java.time.LocalDateTime.now()
            .format(java.time.format.DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss"))
        val sanitizedSerial = deviceSerial.replace(":", "_")
        return getUiDumpsDir().resolve("uidump_${sanitizedSerial}_$timestamp.xml")
    }

    fun allocatePullPath(deviceSerial: String, remotePath: String): Path {
        val timestamp = java.time.LocalDateTime.now()
            .format(java.time.format.DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss_SSS"))
        val sanitizedSerial = sanitizeForFilename(deviceSerial)
        val filename = remotePath.substringAfterLast("/").ifBlank { "file" }
        val sanitizedFilename = sanitizeForFilename(filename)
        val uniqueId = UUID.randomUUID().toString().substring(0, 8)
        return getPulledFilesDir().resolve("pull_${sanitizedSerial}_${timestamp}_${uniqueId}_${sanitizedFilename}")
    }

    fun resolveArtifactPath(artifactPath: String): Path? {
        val resolved = getBaseDir().resolve(artifactPath).normalize().toAbsolutePath()
        val base = getBaseDir().normalize().toAbsolutePath()
        return if (resolved.startsWith(base) && Files.exists(resolved)) resolved else null
    }

    fun readArtifactAsBase64(path: Path, maxSizeMb: Int = 50): String {
        val sizeBytes = Files.size(path)
        val sizeMb = sizeBytes / (1024 * 1024)
        if (sizeMb > maxSizeMb) {
            throw ArtifactTooLargeException(path.toString(), sizeMb, maxSizeMb)
        }
        val bytes = Files.readAllBytes(path)
        return Base64.getEncoder().encodeToString(bytes)
    }

    fun cleanupByAge(protectedPaths: Set<Path> = emptySet()) {
        val maxAge = Instant.now().minus(artifactProperties.maxAgeHours.toLong(), ChronoUnit.HOURS)
        listAllArtifacts()
            .filter { it !in protectedPaths }
            .filter { Files.getLastModifiedTime(it).toInstant().isBefore(maxAge) }
            .forEach { Files.deleteIfExists(it) }
    }

    fun cleanupBySize(protectedPaths: Set<Path> = emptySet()) {
        val maxBytes = artifactProperties.maxTotalSizeMb * 1024 * 1024
        val allFiles = listAllArtifacts()
            .filter { it !in protectedPaths }
            .sortedBy { Files.getLastModifiedTime(it) }

        var totalSize = listAllArtifacts().sumOf { Files.size(it) }
        for (file in allFiles) {
            if (totalSize <= maxBytes) break
            val fileSize = Files.size(file)
            Files.deleteIfExists(file)
            totalSize -= fileSize
        }
    }

    fun deleteArtifactsByType(type: String): DeleteResult {
        val dir = when (type) {
            "screenshots" -> getScreenshotsDir()
            "videos" -> getVideosDir()
            "ui-dumps" -> getUiDumpsDir()
            "pulled" -> getPulledFilesDir()
            "all" -> return deleteAllArtifacts()
            else -> return DeleteResult(0, 0)
        }
        return deleteDirectory(dir)
    }

    private fun deleteAllArtifacts(): DeleteResult {
        var totalDeleted = 0
        var totalFreed = 0L
        listOf(getScreenshotsDir(), getVideosDir(), getUiDumpsDir(), getPulledFilesDir()).forEach { dir ->
            val result = deleteDirectory(dir)
            totalDeleted += result.deletedCount
            totalFreed += result.freedBytes
        }
        return DeleteResult(totalDeleted, totalFreed)
    }

    private fun deleteDirectory(dir: Path): DeleteResult {
        if (!Files.exists(dir)) return DeleteResult(0, 0)
        var count = 0
        var freed = 0L
        Files.list(dir).use { stream ->
            stream.filter { Files.isRegularFile(it) }.forEach { file ->
                freed += Files.size(file)
                Files.delete(file)
                count++
            }
        }
        return DeleteResult(count, freed)
    }

    private fun listAllArtifacts(): List<Path> {
        return listOf(getScreenshotsDir(), getVideosDir(), getUiDumpsDir(), getPulledFilesDir())
            .filter { Files.exists(it) }
            .flatMap { dir ->
                Files.list(dir).use { stream ->
                    stream.filter { Files.isRegularFile(it) }.toList()
                }
            }
    }

    @PostConstruct
    fun initDirectories() {
        listOf(getScreenshotsDir(), getVideosDir(), getUiDumpsDir(), getPulledFilesDir())
            .forEach { Files.createDirectories(it) }
        cleanupByAge()
        cleanupBySize()
    }

    private fun sanitizeForFilename(value: String): String {
        return value.replace(Regex("[^A-Za-z0-9._-]"), "_")
    }
}

data class DeleteResult(val deletedCount: Int, val freedBytes: Long)
