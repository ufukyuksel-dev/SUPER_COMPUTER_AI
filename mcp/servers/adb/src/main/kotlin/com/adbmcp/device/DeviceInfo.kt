package com.adbmcp.device

data class DeviceInfo(
    val serial: String,
    val model: String? = null,
    val product: String? = null,
    val device: String? = null,
    val transportId: String? = null,
    val state: String = "device",
    val androidVersion: String? = null,
    val sdkVersion: Int? = null,
    val resolution: String? = null,
    val density: Int? = null,
    val rotation: Int? = null
)
