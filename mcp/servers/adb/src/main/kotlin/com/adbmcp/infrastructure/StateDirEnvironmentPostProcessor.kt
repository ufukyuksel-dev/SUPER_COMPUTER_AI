package com.adbmcp.infrastructure

import org.springframework.boot.SpringApplication
import org.springframework.boot.env.EnvironmentPostProcessor
import org.springframework.core.Ordered
import org.springframework.core.env.ConfigurableEnvironment
import org.springframework.core.env.MapPropertySource
import java.nio.file.Path
import java.nio.file.Paths

/**
 * Runs after application.yml is loaded and before logging is initialised, on the *effective* value of
 * `adb-mcp.state-dir` (command line, system property, environment or default alike): makes that directory
 * private, pins the normalised path, and refuses write locations that were redirected outside it.
 */
class StateDirEnvironmentPostProcessor : EnvironmentPostProcessor, Ordered {

    override fun getOrder(): Int = Ordered.LOWEST_PRECEDENCE

    override fun postProcessEnvironment(environment: ConfigurableEnvironment, application: SpringApplication) {
        val dir = StateDir.ensurePrivate(StateDir.parse(environment.getProperty(StateDir.PROPERTY)))
        environment.propertySources.addFirst(MapPropertySource(SOURCE, mapOf(StateDir.PROPERTY to dir.toString())))
        for ((key, path) in writtenLocations(environment)) {
            val inside = try {
                StateDir.isInside(path, dir)
            } catch (e: IllegalArgumentException) {
                false
            }
            check(inside) {
                "$key resolves to $path, outside ${StateDir.PROPERTY} ($dir); set ${StateDir.PROPERTY} instead so " +
                    "the location stays private"
            }
        }
    }

    /** The final paths the server writes to on its own, resolved the way the code resolves them. */
    private fun writtenLocations(environment: ConfigurableEnvironment): List<Pair<String, Path>> {
        // unset keys fall back to the property classes' defaults (relative, i.e. the working directory), exactly as
        // the code would use them; blank values are taken as they are (Paths.get("") is the working directory)
        val defaults = ArtifactProperties()
        val basePath = Paths.get(environment.getProperty("artifacts.base-dir") ?: defaults.baseDir)
        val out = mutableListOf("artifacts.base-dir" to basePath)
        for ((key, default) in ARTIFACT_SUBDIRS) {
            out += key to basePath.resolve(environment.getProperty(key) ?: default)   // ArtifactManager.get*Dir()
        }
        out += "scrcpy.recording-dir" to Paths.get(environment.getProperty("scrcpy.recording-dir") ?: SCRCPY_RECORDING_DEFAULT)
        for (key in listOf("logging.file.name", "logging.file.path")) {       // unset: no log file
            environment.getProperty(key)?.takeIf { it.isNotBlank() }?.let { out += key to Paths.get(it) }
        }
        return out
    }

    companion object {
        const val SOURCE = "adbMcpStateDir"
        /** Artifact subdirectories and their defaults (from ArtifactProperties). */
        val ARTIFACT_SUBDIRS = ArtifactProperties().let {
            listOf(
                "artifacts.screenshots-dir" to it.screenshotsDir,
                "artifacts.videos-dir" to it.videosDir,
                "artifacts.ui-dumps-dir" to it.uiDumpsDir,
                "artifacts.pulled-files-dir" to it.pulledFilesDir
            )
        }
        /** ScrcpyProperties.recordingDir default (another module; kept in sync by StateDirTest). */
        const val SCRCPY_RECORDING_DEFAULT = "./artifacts/videos"
        /** Every setting that decides where the server writes on its own. */
        val WRITTEN = listOf("artifacts.base-dir") + ARTIFACT_SUBDIRS.map { it.first } +
            listOf("scrcpy.recording-dir", "logging.file.name", "logging.file.path")
    }
}
