package com.adbmcp.infrastructure

sealed class AdbException(
    val errorCode: ErrorCode,
    message: String
) : RuntimeException(message)

class DeviceNotFoundException(availableDevices: List<String>) : AdbException(
    ErrorCode.DEVICE_NOT_FOUND,
    "Device not found. Available devices: ${availableDevices.joinToString(", ").ifEmpty { "none" }}"
)

class AmbiguousDeviceException(availableDevices: List<String>) : AdbException(
    ErrorCode.AMBIGUOUS_DEVICE,
    "Multiple devices connected, deviceSerial required. Available: ${availableDevices.joinToString(", ")}"
)

class AdbTimeoutException(command: String, timeoutMs: Long) : AdbException(
    ErrorCode.TIMEOUT,
    "Command timed out after ${timeoutMs}ms: $command"
)

class PermissionDeniedException(detail: String) : AdbException(
    ErrorCode.PERMISSION_DENIED,
    "Permission denied: $detail"
)

class ToolDisabledException(toolName: String) : AdbException(
    ErrorCode.TOOL_DISABLED,
    "Tool disabled by security policy: $toolName"
)

class PathBlockedException(path: String) : AdbException(
    ErrorCode.PATH_BLOCKED,
    "Path outside sandbox boundary: $path"
)

class ScrcpyNotFoundException : AdbException(
    ErrorCode.SCRCPY_NOT_FOUND,
    "scrcpy binary not found in PATH"
)

class ElementNotFoundException(criteria: String) : AdbException(
    ErrorCode.ELEMENT_NOT_FOUND,
    "No UI element matching criteria: $criteria"
)

class RecordingActiveException(deviceSerial: String) : AdbException(
    ErrorCode.RECORDING_ACTIVE,
    "Recording already in progress on device: $deviceSerial"
)

class SessionNotFoundException(sessionId: String) : AdbException(
    ErrorCode.SESSION_NOT_FOUND,
    "Session not found: $sessionId"
)

class RecordingNotFoundException(recordingId: String) : AdbException(
    ErrorCode.RECORDING_NOT_FOUND,
    "Recording not found: $recordingId"
)

class ArtifactNotFoundException(path: String) : AdbException(
    ErrorCode.ARTIFACT_NOT_FOUND,
    "Artifact not found: $path"
)

class ArtifactTooLargeException(path: String, sizeMb: Long, maxMb: Int) : AdbException(
    ErrorCode.ARTIFACT_TOO_LARGE,
    "Artifact $path is ${sizeMb}MB, exceeds max ${maxMb}MB"
)
