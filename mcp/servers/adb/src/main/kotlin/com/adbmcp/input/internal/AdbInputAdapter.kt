package com.adbmcp.input.internal

import com.adbmcp.infrastructure.AdbExecutor
import com.adbmcp.infrastructure.TextEscaper
import com.adbmcp.input.CommandResult
import com.adbmcp.input.InputPort
import org.springframework.stereotype.Component

@Component
class AdbInputAdapter(
    private val adbExecutor: AdbExecutor,
    private val textEscaper: TextEscaper
) : InputPort {

    override fun tap(serial: String, x: Int, y: Int): CommandResult {
        val result = adbExecutor.execute(serial, "shell", "input", "tap", "$x", "$y")
        return CommandResult(success = result.isSuccess, error = result.stderr.ifEmpty { null })
    }

    override fun swipe(serial: String, x1: Int, y1: Int, x2: Int, y2: Int, durationMs: Int): CommandResult {
        val result = adbExecutor.execute(
            serial, "shell", "input", "swipe",
            "$x1", "$y1", "$x2", "$y2", "$durationMs"
        )
        return CommandResult(success = result.isSuccess, error = result.stderr.ifEmpty { null })
    }

    override fun longPress(serial: String, x: Int, y: Int, durationMs: Int): CommandResult {
        // Long press = zero-distance swipe
        val result = adbExecutor.execute(
            serial, "shell", "input", "swipe",
            "$x", "$y", "$x", "$y", "$durationMs"
        )
        return CommandResult(success = result.isSuccess, error = result.stderr.ifEmpty { null })
    }

    override fun typeText(serial: String, text: String, useAdbKeyboard: Boolean): CommandResult {
        return if (useAdbKeyboard) {
            typeViaAdbKeyboard(serial, text)
        } else {
            typeViaInput(serial, text)
        }
    }

    override fun keyEvent(serial: String, keycode: String): CommandResult {
        val code = if (keycode.startsWith("KEYCODE_")) keycode else "KEYCODE_$keycode"
        val result = adbExecutor.execute(serial, "shell", "input", "keyevent", code)
        return CommandResult(success = result.isSuccess, error = result.stderr.ifEmpty { null })
    }

    override fun imeList(serial: String): List<String> {
        val result = adbExecutor.execute(serial, "shell", "ime", "list", "-s")
        return result.stdout.lines().filter { it.isNotBlank() }
    }

    override fun imeSet(serial: String, imeId: String): CommandResult {
        val result = adbExecutor.execute(serial, "shell", "ime", "set", imeId)
        return CommandResult(success = result.isSuccess, error = result.stderr.ifEmpty { null })
    }

    override fun imeCurrent(serial: String): String {
        val result = adbExecutor.execute(
            serial, "shell", "settings", "get", "secure", "default_input_method"
        )
        return result.stdout.trim()
    }

    private fun typeViaInput(serial: String, text: String): CommandResult {
        val escaped = textEscaper.escapeForShell(text)
        val result = adbExecutor.execute(serial, "shell", "input", "text", escaped)
        return CommandResult(success = result.isSuccess, error = result.stderr.ifEmpty { null })
    }

    private fun typeViaAdbKeyboard(serial: String, text: String): CommandResult {
        val result = adbExecutor.execute(
            serial, "shell", "am", "broadcast",
            "-a", "ADB_INPUT_TEXT",
            "--es", "msg", text
        )
        return CommandResult(success = result.isSuccess, error = result.stderr.ifEmpty { null })
    }
}
