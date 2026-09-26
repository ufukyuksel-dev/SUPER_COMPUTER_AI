package com.adbmcp.input

interface InputPort {
    fun tap(serial: String, x: Int, y: Int): CommandResult
    fun swipe(serial: String, x1: Int, y1: Int, x2: Int, y2: Int, durationMs: Int = 300): CommandResult
    fun longPress(serial: String, x: Int, y: Int, durationMs: Int = 1000): CommandResult
    fun typeText(serial: String, text: String, useAdbKeyboard: Boolean = false): CommandResult
    fun keyEvent(serial: String, keycode: String): CommandResult
    fun imeList(serial: String): List<String>
    fun imeSet(serial: String, imeId: String): CommandResult
    fun imeCurrent(serial: String): String
}
