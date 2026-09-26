package com.adbmcp.scrcpy

import com.adbmcp.infrastructure.ArtifactManager
import com.adbmcp.infrastructure.DeviceResolver
import com.adbmcp.infrastructure.PathBlockedException
import com.adbmcp.infrastructure.ScrcpyNotFoundException
import com.adbmcp.infrastructure.SecurityPolicy
import com.adbmcp.infrastructure.SessionNotFoundException
import com.adbmcp.infrastructure.StateDir
import com.adbmcp.infrastructure.ToolDisabledException
import jakarta.annotation.PreDestroy
import org.slf4j.LoggerFactory
import org.springframework.scheduling.annotation.Scheduled
import org.springframework.stereotype.Service
import java.nio.file.Path
import java.time.Duration
import java.time.Instant
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap

@Service
class ScrcpyService(
    private val scrcpyPort: ScrcpyPort,
    private val deviceResolver: DeviceResolver,
    private val artifactManager: ArtifactManager,
    private val securityPolicy: SecurityPolicy
) {
    private val logger = LoggerFactory.getLogger(ScrcpyService::class.java)
    private val activeSessions = ConcurrentHashMap<String, ScrcpySession>()

    fun startMirror(deviceSerial: String? = null): ScrcpyStartResult {
        if (!scrcpyPort.isScrcpyAvailable()) throw ScrcpyNotFoundException()
        val serial = deviceResolver.resolve(deviceSerial)
        val sessionId = UUID.randomUUID().toString()
        val process = scrcpyPort.startMirror(serial)
        activeSessions[sessionId] = ScrcpySession(sessionId, serial, SessionType.MIRROR, process, Instant.now())
        return ScrcpyStartResult(success = true, sessionId = sessionId)
    }

    fun stopMirror(sessionId: String): ScrcpyStopResult {
        val session = activeSessions.remove(sessionId) ?: throw SessionNotFoundException(sessionId)
        scrcpyPort.stopSession(session.process)
        val duration = Duration.between(session.startedAt, Instant.now()).seconds
        return ScrcpyStopResult(success = true, durationSeconds = duration)
    }

    fun startRecord(
        outputPath: String? = null,
        audioEnabled: Boolean = true,
        deviceSerial: String? = null
    ): ScrcpyStartResult {
        if (!scrcpyPort.isScrcpyAvailable()) throw ScrcpyNotFoundException()
        val serial = deviceResolver.resolve(deviceSerial)
        val sessionId = UUID.randomUUID().toString()

        // an agent-supplied output path must stay inside the private artifact directory (symlinks included)
        if (outputPath != null && !runCatching { StateDir.isInside(Path.of(outputPath), artifactManager.getBaseDir()) }
                .getOrDefault(false)) {
            throw PathBlockedException(outputPath)
        }
        val finalPath = outputPath
            ?: artifactManager.allocateVideoPath(serial, sessionId).toString()

        java.nio.file.Files.createDirectories(java.nio.file.Path.of(finalPath).parent)
        val process = scrcpyPort.startRecord(serial, finalPath, audioEnabled)
        activeSessions[sessionId] = ScrcpySession(sessionId, serial, SessionType.RECORD, process, Instant.now(), finalPath)
        return ScrcpyStartResult(success = true, sessionId = sessionId)
    }

    fun stopRecord(sessionId: String): ScrcpyStopResult {
        val session = activeSessions.remove(sessionId) ?: throw SessionNotFoundException(sessionId)
        scrcpyPort.stopSession(session.process)
        val duration = Duration.between(session.startedAt, Instant.now()).seconds
        return ScrcpyStopResult(success = true, outputPath = session.outputPath, durationSeconds = duration)
    }

    fun connectTcpip(deviceIp: String, port: Int = 5555, deviceSerial: String): ScrcpyConnectResult {
        if (!securityPolicy.isToolEnabled("scrcpy-connect-tcpip")) {
            throw ToolDisabledException("scrcpy-connect-tcpip")
        }
        return scrcpyPort.connectTcpip(deviceSerial, deviceIp, port)
    }

    fun getStatus(sessionId: String? = null): ScrcpyStatusResult {
        cleanDeadSessions()
        if (sessionId != null) {
            val session = activeSessions[sessionId] ?: throw SessionNotFoundException(sessionId)
            return ScrcpyStatusResult(success = true, session = toSessionInfo(session))
        }
        val allSessions = activeSessions.values.map { toSessionInfo(it) }
        return ScrcpyStatusResult(success = true, sessions = allSessions)
    }

    fun getActiveSessionIds(): Set<String> = activeSessions.keys.toSet()

    fun getActiveSessionPaths(): Set<java.nio.file.Path> {
        return activeSessions.values
            .filter { it.sessionType == SessionType.RECORD && it.outputPath != null }
            .map { java.nio.file.Path.of(it.outputPath!!) }
            .toSet()
    }

    @Scheduled(fixedRate = 30000)
    fun cleanDeadSessions() {
        val dead = activeSessions.entries.filter { !scrcpyPort.isProcessAlive(it.value.process) }
        dead.forEach { (id, session) ->
            logger.info("Removing dead scrcpy session: {} ({})", id, session.sessionType)
            activeSessions.remove(id)
        }
    }

    @PreDestroy
    fun shutdown() {
        logger.info("Shutting down {} active scrcpy sessions", activeSessions.size)
        activeSessions.values.forEach { session ->
            try {
                scrcpyPort.stopSession(session.process)
            } catch (e: Exception) {
                logger.warn("Failed to stop scrcpy session {}: {}", session.sessionId, e.message)
            }
        }
        activeSessions.clear()
    }

    private fun toSessionInfo(session: ScrcpySession): ScrcpySessionInfo {
        return ScrcpySessionInfo(
            sessionId = session.sessionId,
            deviceSerial = session.deviceSerial,
            sessionType = session.sessionType,
            startedAt = session.startedAt,
            durationSeconds = Duration.between(session.startedAt, Instant.now()).seconds,
            outputPath = session.outputPath
        )
    }
}
