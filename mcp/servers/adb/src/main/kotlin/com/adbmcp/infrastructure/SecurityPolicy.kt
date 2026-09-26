package com.adbmcp.infrastructure

import org.springframework.stereotype.Component
import java.nio.file.Path
import java.nio.file.Paths

@Component
class SecurityPolicy(private val securityProperties: SecurityProperties) {

    fun isToolEnabled(toolName: String): Boolean {
        val config = securityProperties.dangerousTools[toolName]
        return config?.enabled ?: true
    }

    fun validateHostPath(path: String): PathValidation {
        if (containsTraversal(path)) {
            return PathValidation(false, "Path traversal detected", ErrorCode.PATH_BLOCKED)
        }
        val normalizedPath = canonicalize(Paths.get(path))
        val allowed = securityProperties.fileTransfer.hostAllowedPaths.any { allowedPath ->
            normalizedPath.startsWith(canonicalize(Paths.get(allowedPath)))
        }
        return if (allowed) PathValidation(true)
        else PathValidation(false, "Path outside allowed host paths: $path", ErrorCode.PATH_BLOCKED)
    }

    fun validateDevicePath(path: String): PathValidation {
        if (containsTraversal(path)) {
            return PathValidation(false, "Path traversal detected", ErrorCode.PATH_BLOCKED)
        }
        val allowed = securityProperties.fileTransfer.deviceAllowedPaths.any { path.startsWith(it) }
        return if (allowed) PathValidation(true)
        else PathValidation(false, "Path outside allowed device paths: $path", ErrorCode.PATH_BLOCKED)
    }

    fun validateArtifactPath(artifactPath: String, baseDir: Path): PathValidation {
        if (containsTraversal(artifactPath)) {
            return PathValidation(false, "Path traversal detected", ErrorCode.PATH_BLOCKED)
        }
        val resolved = baseDir.resolve(artifactPath).normalize().toAbsolutePath()
        val base = baseDir.normalize().toAbsolutePath()
        return if (resolved.startsWith(base)) PathValidation(true)
        else PathValidation(false, "Path outside artifact directory", ErrorCode.PATH_BLOCKED)
    }

    fun isIntentAllowed(action: String?, packageName: String?): Boolean {
        if (!securityProperties.intentAllowlist.enabled) return true

        val actionAllowed = action == null ||
                securityProperties.intentAllowlist.allowedActions.isEmpty() ||
                securityProperties.intentAllowlist.allowedActions.contains(action)

        val packageAllowed = packageName == null ||
                securityProperties.intentAllowlist.allowedPackages.isEmpty() ||
                securityProperties.intentAllowlist.allowedPackages.any { pattern ->
                    if (pattern.endsWith("*")) packageName.startsWith(pattern.dropLast(1))
                    else packageName == pattern
                }

        return actionAllowed && packageAllowed
    }

    private fun containsTraversal(path: String): Boolean {
        val normalized = path.replace("\\", "/")
        return normalized.contains("../") || normalized.contains("/..")
                || normalized == ".." || normalized.startsWith("../")
    }

    private fun canonicalize(path: Path): Path {
        val absolute = path.toAbsolutePath().normalize()
        return try {
            absolute.toRealPath()
        } catch (_: Exception) {
            absolute
        }
    }
}

data class PathValidation(
    val valid: Boolean,
    val error: String? = null,
    val errorCode: ErrorCode? = null
)
