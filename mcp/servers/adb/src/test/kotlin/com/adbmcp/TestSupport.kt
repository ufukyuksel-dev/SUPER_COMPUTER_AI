package com.adbmcp

import java.nio.file.Files
import java.nio.file.Path

fun writeExecutableScript(directory: Path, name: String, body: String): String {
    val script = directory.resolve(name)
    Files.writeString(script, body.trimIndent() + "\n")
    script.toFile().setExecutable(true)
    return script.toString()
}
