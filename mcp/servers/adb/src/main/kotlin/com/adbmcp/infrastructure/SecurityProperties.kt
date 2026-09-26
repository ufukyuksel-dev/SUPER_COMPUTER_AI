package com.adbmcp.infrastructure

import org.springframework.boot.context.properties.ConfigurationProperties

@ConfigurationProperties(prefix = "security")
data class SecurityProperties(
    val dangerousTools: Map<String, ToolConfig> = emptyMap(),
    val fileTransfer: FileTransferConfig = FileTransferConfig(),
    val intentAllowlist: IntentAllowlistConfig = IntentAllowlistConfig()
)

data class ToolConfig(
    val enabled: Boolean = true
)

data class FileTransferConfig(
    val hostAllowedPaths: List<String> = listOf("./transfers"),
    val deviceAllowedPaths: List<String> = listOf("/sdcard/", "/data/local/tmp/")
)

data class IntentAllowlistConfig(
    val enabled: Boolean = false,
    val allowedActions: List<String> = emptyList(),
    val allowedPackages: List<String> = emptyList()
)
