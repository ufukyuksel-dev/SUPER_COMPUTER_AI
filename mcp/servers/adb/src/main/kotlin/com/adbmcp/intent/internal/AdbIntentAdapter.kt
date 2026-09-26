package com.adbmcp.intent.internal

import com.adbmcp.infrastructure.AdbExecutor
import com.adbmcp.input.CommandResult
import com.adbmcp.intent.IntentExtra
import com.adbmcp.intent.IntentPort
import com.adbmcp.intent.IntentResult
import org.springframework.stereotype.Component

@Component
class AdbIntentAdapter(private val adbExecutor: AdbExecutor) : IntentPort {

    override fun amStart(
        serial: String,
        action: String?,
        data: String?,
        component: String?,
        extras: List<IntentExtra>,
        flags: List<String>,
        categories: List<String>
    ): IntentResult {
        val args = mutableListOf("shell", "am", "start")
        args.addAll(buildIntentArgs(action, data, component, extras, flags, categories))
        val result = adbExecutor.execute(serial, *args.toTypedArray())
        return IntentResult(success = result.isSuccess, output = result.stdout, error = result.stderr.ifEmpty { null })
    }

    override fun amBroadcast(
        serial: String,
        action: String?,
        data: String?,
        component: String?,
        extras: List<IntentExtra>,
        flags: List<String>,
        categories: List<String>
    ): IntentResult {
        val args = mutableListOf("shell", "am", "broadcast")
        args.addAll(buildIntentArgs(action, data, component, extras, flags, categories))
        val result = adbExecutor.execute(serial, *args.toTypedArray())
        return IntentResult(success = result.isSuccess, output = result.stdout, error = result.stderr.ifEmpty { null })
    }

    override fun forceStop(serial: String, packageName: String): CommandResult {
        val result = adbExecutor.execute(serial, "shell", "am", "force-stop", packageName)
        return CommandResult(success = result.isSuccess, error = result.stderr.ifEmpty { null })
    }

    override fun listPackages(serial: String, filter: String?): List<String> {
        val args = mutableListOf("shell", "pm", "list", "packages")
        filter?.let(args::add)
        val result = adbExecutor.execute(serial, *args.toTypedArray())
        return result.stdout.lines()
            .filter { it.startsWith("package:") }
            .map { it.removePrefix("package:").substringAfterLast("=").trim() }
    }

    override fun currentActivity(serial: String): String {
        val result = adbExecutor.execute(serial, "shell", "dumpsys", "activity", "activities",
            timeoutMs = 10000)
        val line = result.stdout.lines()
            .firstOrNull { it.contains("mResumedActivity") || it.contains("mCurrentFocus") }
        return if (line != null) {
            val regex = "\\{[^}]*\\s([\\w./]+)\\s".toRegex()
            val match = regex.find(line)
            match?.groupValues?.get(1) ?: line.trim()
        } else {
            "unknown"
        }
    }

    private fun buildIntentArgs(
        action: String?,
        data: String?,
        component: String?,
        extras: List<IntentExtra>,
        flags: List<String>,
        categories: List<String>
    ): List<String> {
        val args = mutableListOf<String>()
        action?.let { args.addAll(listOf("-a", it)) }
        data?.let { args.addAll(listOf("-d", it)) }
        component?.let { args.addAll(listOf("-n", it)) }
        categories.forEach { args.addAll(listOf("-c", it)) }
        flags.forEach { args.add(it) }
        extras.forEach { extra ->
            args.addAll(listOf(extra.type.adbFlag, extra.key, extra.value))
        }
        return args
    }
}
