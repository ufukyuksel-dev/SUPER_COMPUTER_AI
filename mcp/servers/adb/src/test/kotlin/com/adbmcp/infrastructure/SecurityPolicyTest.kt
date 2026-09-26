package com.adbmcp.infrastructure

import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.Paths

class SecurityPolicyTest {

    private fun createPolicy(
        hostAllowedPaths: List<String> = listOf("./transfers"),
        deviceAllowedPaths: List<String> = listOf("/sdcard/", "/data/local/tmp/"),
        dangerousTools: Map<String, ToolConfig> = mapOf("push-file" to ToolConfig(true)),
        intentAllowlist: IntentAllowlistConfig = IntentAllowlistConfig(false)
    ): SecurityPolicy {
        return SecurityPolicy(
            SecurityProperties(
                dangerousTools = dangerousTools,
                fileTransfer = FileTransferConfig(hostAllowedPaths, deviceAllowedPaths),
                intentAllowlist = intentAllowlist
            )
        )
    }

    @Test
    fun `tool enabled by default`() {
        val policy = createPolicy()
        assertTrue(policy.isToolEnabled("unknown-tool"))
    }

    @Test
    fun `tool disabled returns false`() {
        val policy = createPolicy(dangerousTools = mapOf("push-file" to ToolConfig(false)))
        assertFalse(policy.isToolEnabled("push-file"))
    }

    @Test
    fun `host path validation allows valid path`() {
        val policy = createPolicy()
        val result = policy.validateHostPath("./transfers/file.txt")
        assertTrue(result.valid)
    }

    @Test
    fun `host path validation allows absolute path inside relative allowlist`() {
        val allowedDir = Path.of("build", "tmp", "security-policy-test", "transfers").toAbsolutePath()
        Files.createDirectories(allowedDir)
        val file = allowedDir.resolve("file.txt")
        Files.writeString(file, "ok")

        val relativeAllowedDir = Path.of("").toAbsolutePath().relativize(allowedDir).toString()
        val policy = createPolicy(hostAllowedPaths = listOf(relativeAllowedDir))

        val result = policy.validateHostPath(file.toString())

        assertTrue(result.valid)
    }

    @Test
    fun `host path validation blocks traversal`() {
        val policy = createPolicy()
        val result = policy.validateHostPath("./transfers/../etc/passwd")
        assertFalse(result.valid)
        assertEquals(ErrorCode.PATH_BLOCKED, result.errorCode)
    }

    @Test
    fun `device path validation allows sdcard`() {
        val policy = createPolicy()
        val result = policy.validateDevicePath("/sdcard/Download/file.txt")
        assertTrue(result.valid)
    }

    @Test
    fun `device path validation blocks system`() {
        val policy = createPolicy()
        val result = policy.validateDevicePath("/system/build.prop")
        assertFalse(result.valid)
    }

    @Test
    fun `device path validation blocks traversal`() {
        val policy = createPolicy()
        val result = policy.validateDevicePath("/sdcard/../system/build.prop")
        assertFalse(result.valid)
    }

    @Test
    fun `artifact path validation blocks traversal`() {
        val policy = createPolicy()
        val baseDir = Paths.get("./artifacts")
        val result = policy.validateArtifactPath("../../etc/passwd", baseDir)
        assertFalse(result.valid)
    }

    @Test
    fun `intent allowed when allowlist disabled`() {
        val policy = createPolicy()
        assertTrue(policy.isIntentAllowed("any.action", "any.package"))
    }

    @Test
    fun `intent blocked when allowlist enabled and action not in list`() {
        val policy = createPolicy(
            intentAllowlist = IntentAllowlistConfig(
                enabled = true,
                allowedActions = listOf("android.intent.action.VIEW"),
                allowedPackages = emptyList()
            )
        )
        assertFalse(policy.isIntentAllowed("android.intent.action.DELETE", null))
    }

    @Test
    fun `intent allowed when action in allowlist`() {
        val policy = createPolicy(
            intentAllowlist = IntentAllowlistConfig(
                enabled = true,
                allowedActions = listOf("android.intent.action.VIEW"),
                allowedPackages = emptyList()
            )
        )
        assertTrue(policy.isIntentAllowed("android.intent.action.VIEW", null))
    }

    @Test
    fun `intent package wildcard match`() {
        val policy = createPolicy(
            intentAllowlist = IntentAllowlistConfig(
                enabled = true,
                allowedActions = emptyList(),
                allowedPackages = listOf("com.myapp.*")
            )
        )
        assertTrue(policy.isIntentAllowed(null, "com.myapp.feature"))
        assertFalse(policy.isIntentAllowed(null, "com.other.app"))
    }
}
