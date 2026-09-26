package com.adbmcp.intent

import com.adbmcp.input.CommandResult

interface IntentPort {
    fun amStart(
        serial: String,
        action: String? = null,
        data: String? = null,
        component: String? = null,
        extras: List<IntentExtra> = emptyList(),
        flags: List<String> = emptyList(),
        categories: List<String> = emptyList()
    ): IntentResult

    fun amBroadcast(
        serial: String,
        action: String? = null,
        data: String? = null,
        component: String? = null,
        extras: List<IntentExtra> = emptyList(),
        flags: List<String> = emptyList(),
        categories: List<String> = emptyList()
    ): IntentResult

    fun forceStop(serial: String, packageName: String): CommandResult
    fun listPackages(serial: String, filter: String? = null): List<String>
    fun currentActivity(serial: String): String
}
