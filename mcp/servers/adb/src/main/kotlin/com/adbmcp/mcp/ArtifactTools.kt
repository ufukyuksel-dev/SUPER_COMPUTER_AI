package com.adbmcp.mcp

import com.adbmcp.infrastructure.AdbException
import com.adbmcp.infrastructure.ArtifactManager
import com.adbmcp.infrastructure.AuditLogger
import com.adbmcp.infrastructure.SecurityPolicy
import com.adbmcp.infrastructure.ArtifactNotFoundException
import org.springframework.ai.tool.annotation.Tool
import org.springframework.ai.tool.annotation.ToolParam
import org.springframework.stereotype.Service
import java.nio.file.Path

@Service
class ArtifactTools(
    private val artifactManager: ArtifactManager,
    private val securityPolicy: SecurityPolicy,
    private val auditLogger: AuditLogger
) {
    @Tool(description = "Delete stored artifacts by type (screenshots, videos, ui-dumps, pulled, all)")
    fun delete_artifacts(
        @ToolParam(description = "Artifact type: screenshots | videos | ui-dumps | pulled | all (default: all)") type: String? = null
    ): String {
        val start = System.currentTimeMillis()
        val artifactType = type ?: "all"
        val result = artifactManager.deleteArtifactsByType(artifactType)
        auditLogger.log("delete_artifacts", null, mapOf("type" to artifactType), "success", System.currentTimeMillis() - start)
        return ToolResponse.success(mapOf(
            "success" to true,
            "deletedCount" to result.deletedCount,
            "freedBytes" to result.freedBytes
        ))
    }

    @Tool(description = "Fetch artifact as base64 for remote SSE clients. Sandboxed to artifacts directory only.")
    fun download_artifact(
        @ToolParam(description = "Artifact path (relative to artifacts base dir)") artifactPath: String,
        @ToolParam(description = "Max size in MB (default 50)") maxSizeMb: Int? = null
    ): String {
        val start = System.currentTimeMillis()
        return try {
            val validation = securityPolicy.validateArtifactPath(artifactPath, artifactManager.getBaseDir())
            if (!validation.valid) {
                return ToolResponse.error(validation.error ?: "Path blocked", validation.errorCode?.name)
            }

            val resolved = artifactManager.resolveArtifactPath(artifactPath)
                ?: throw ArtifactNotFoundException(artifactPath)

            val base64 = artifactManager.readArtifactAsBase64(resolved, maxSizeMb ?: 50)
            val sizeBytes = java.nio.file.Files.size(resolved)

            auditLogger.log("download_artifact", null, mapOf("path" to artifactPath), "success", System.currentTimeMillis() - start)
            ToolResponse.success(mapOf(
                "success" to true,
                "base64" to base64,
                "sizeBytes" to sizeBytes
            ))
        } catch (e: AdbException) {
            auditLogger.log("download_artifact", null, mapOf("path" to artifactPath), "error", System.currentTimeMillis() - start)
            ToolResponse.error(e)
        }
    }
}
