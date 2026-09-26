package com.adbmcp.mcp

import org.springframework.ai.tool.ToolCallbackProvider
import org.springframework.ai.tool.method.MethodToolCallbackProvider
import org.springframework.context.annotation.Bean
import org.springframework.context.annotation.Configuration

@Configuration
class McpToolRegistration {

    @Bean
    fun toolCallbackProvider(
        deviceTools: DeviceTools,
        captureTools: CaptureTools,
        inputTools: InputTools,
        intentTools: IntentTools,
        inspectionTools: InspectionTools,
        reliabilityTools: ReliabilityTools,
        fileTools: FileTools,
        artifactTools: ArtifactTools,
        scrcpyTools: ScrcpyTools
    ): ToolCallbackProvider {
        return MethodToolCallbackProvider.builder()
            .toolObjects(
                deviceTools, captureTools, inputTools, intentTools,
                inspectionTools, reliabilityTools, fileTools,
                artifactTools, scrcpyTools
            )
            .build()
    }
}
