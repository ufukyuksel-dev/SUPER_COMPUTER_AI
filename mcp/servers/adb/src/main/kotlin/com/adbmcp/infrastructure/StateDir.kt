package com.adbmcp.infrastructure

import java.nio.file.FileSystems
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.Paths
import java.nio.file.attribute.PosixFilePermissions

/**
 * Where the server keeps screenshots, videos, UI dumps, pulled files and logs — never in the client's working
 * directory (MCP clients start the server from whatever project is open). Configured by the Spring property
 * `adb-mcp.state-dir` (any source: `--adb-mcp.state-dir=`, `-Dadb-mcp.state-dir=`, env `ADB_MCP_STATE_DIR`, default
 * `~/.local/state/super-computer-ai/adb`); [StateDirEnvironmentPostProcessor] applies it before logging starts.
 * The directory is private (0700): captures and pulled files can hold personal data.
 */
object StateDir {
    const val PROPERTY = "adb-mcp.state-dir"

    /** The configured value as an absolute, normalised path; `~/` is expanded, anything relative is refused. */
    fun parse(value: String?, home: String = System.getProperty("user.home")): Path {
        require(!value.isNullOrBlank()) { "$PROPERTY is empty; unset it to use the default or give an absolute path" }
        val expanded = if (value == "~" || value.startsWith("~/")) home + value.substring(1) else value
        val path = Paths.get(expanded)
        require(path.isAbsolute) {
            "$PROPERTY must be an absolute path (or start with ~/), got '$value': a relative path would follow the " +
                "MCP client's working directory"
        }
        return path.normalize()
    }

    /**
     * Where [path] really points: every existing component is resolved with its symlinks, `..` is applied to the
     * real parent, and components that do not exist yet are appended as they are. A dangling symlink is refused
     * because creating through it would land wherever it points.
     */
    fun realTarget(path: Path): Path {
        val absolute = path.toAbsolutePath()
        var current: Path = absolute.root.toRealPath()
        var exists = true
        for (name in absolute) {
            val part = name.toString()
            when {
                part == "." -> Unit
                part == ".." -> current = current.parent ?: current
                else -> {
                    val next = current.resolve(part)
                    if (exists && Files.exists(next)) {
                        current = next.toRealPath()
                    } else {
                        require(!Files.isSymbolicLink(next)) { "dangling symbolic link: $next" }
                        exists = false
                        current = next
                    }
                }
            }
        }
        return current
    }

    /** True when [path] really lies inside [root] (both resolved with [realTarget]; symlinks cannot escape). */
    fun isInside(path: Path, root: Path): Boolean = realTarget(path).startsWith(realTarget(root))

    fun ensurePrivate(dir: Path): Path {
        Files.createDirectories(dir)
        if ("posix" in FileSystems.getDefault().supportedFileAttributeViews()) {
            Files.setPosixFilePermissions(dir, PosixFilePermissions.fromString("rwx------"))
        }
        return dir
    }
}
